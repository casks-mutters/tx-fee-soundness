import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from web3 import Web3
from web3.exceptions import TransactionNotFound


DEFAULT_RPC1 = os.getenv("RPC_URL")
DEFAULT_RPC2 = os.getenv("RPC_URL_2")


@dataclass
class TxView:
    ok: bool
    error: Optional[str]
    rpc: str
    chain_id: Optional[int]
    block_number: Optional[int]
    status: Optional[int]
    gas_used: Optional[int]
    gas_price_wei: Optional[int]
    total_fee_wei: Optional[int]
    confirmations: Optional[int]


def fmt_eth(wei: Optional[int]) -> str:
    if wei is None:
        return "-"
    return f"{Web3.from_wei(wei, 'ether'):.6f}"


def fmt_gwei(wei: Optional[int]) -> str:
    if wei is None:
        return "-"
    return f"{Web3.from_wei(wei, 'gwei'):.2f}"


def normalize_hash(tx_hash: str) -> str:
    tx_hash = tx_hash.strip()
    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash
    if len(tx_hash) != 66:
        raise ValueError("tx hash must be 0x + 64 hex chars")
    int(tx_hash[2:], 16)  # validate hex
    return tx_hash.lower()


def connect(rpc: str, label: str, timeout: int) -> Web3:
    try:
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": timeout}))
    except Exception as exc:
        raise RuntimeError(f"Failed to create Web3 provider for {label}: {exc}") from exc

    if not w3.is_connected():
        raise RuntimeError(f"Could not connect to {label} RPC endpoint: {rpc}")

    # Optional PoA middleware for some L2/testnets
    try:
        from web3.middleware import geth_poa_middleware

        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    except Exception:
        pass

    return w3


def build_view(w3: Web3, rpc: str, tx_hash: str) -> TxView:
    try:
        chain_id = int(w3.eth.chain_id)
    except Exception:
        chain_id = None

    try:
        latest_block = w3.eth.block_number
    except Exception:
        latest_block = None

    try:
        tx = w3.eth.get_transaction(tx_hash)
    except TransactionNotFound:
        return TxView(
            ok=False,
            error="transaction-not-found",
            rpc=rpc,
            chain_id=chain_id,
            block_number=None,
            status=None,
            gas_used=None,
            gas_price_wei=None,
            total_fee_wei=None,
            confirmations=None,
        )
    except Exception as exc:
        return TxView(
            ok=False,
            error=f"error-fetching-tx: {exc}",
            rpc=rpc,
            chain_id=chain_id,
            block_number=None,
            status=None,
            gas_used=None,
            gas_price_wei=None,
            total_fee_wei=None,
            confirmations=None,
        )

    try:
        rcpt = w3.eth.get_transaction_receipt(tx_hash)
    except TransactionNotFound:
        return TxView(
            ok=False,
            error="pending",
            rpc=rpc,
            chain_id=chain_id,
            block_number=None,
            status=None,
            gas_used=None,
            gas_price_wei=None,
            total_fee_wei=None,
            confirmations=None,
        )
    except Exception as exc:
        return TxView(
            ok=False,
            error=f"error-fetching-receipt: {exc}",
            rpc=rpc,
            chain_id=chain_id,
            block_number=None,
            status=None,
            gas_used=None,
            gas_price_wei=None,
            total_fee_wei=None,
            confirmations=None,
        )

    block_number = int(rcpt.blockNumber) if rcpt.blockNumber is not None else None
    status = int(rcpt.status) if rcpt.status is not None else None
    gas_used = int(rcpt.gasUsed) if rcpt.gasUsed is not None else None

    gas_price_wei = getattr(rcpt, "effectiveGasPrice", None)
    if gas_price_wei is None:
        gas_price_wei = tx.get("gasPrice")

    if gas_used is not None and gas_price_wei is not None:
        total_fee_wei = gas_used * gas_price_wei
    else:
        total_fee_wei = None

    if latest_block is not None and block_number is not None:
        confirmations = max(0, latest_block - block_number + 1)
    else:
        confirmations = None

    return TxView(
        ok=True,
        error=None,
        rpc=rpc,
        chain_id=chain_id,
        block_number=block_number,
        status=status,
        gas_used=gas_used,
        gas_price_wei=gas_price_wei,
        total_fee_wei=total_fee_wei,
        confirmations=confirmations,
    )


def compare_views(v1: TxView, v2: TxView) -> Dict[str, bool]:
    """
    Compare key fields; return dict of field->True/False (match / mismatch).
    Only compares fields that are non-None on both sides.
    """
    fields = ["chain_id", "block_number", "status", "gas_used", "gas_price_wei", "total_fee_wei"]
    result: Dict[str, bool] = {}
    for f in fields:
        a = getattr(v1, f)
        b = getattr(v2, f)
        if a is None or b is None:
            result[f] = True  # treat as neutral (no comparison)
        else:
            result[f] = (a == b)
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Compare fee-related transaction fields across two RPC endpoints.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "tx_hash",
        help="Transaction hash (0x-prefixed, 32 bytes).",
    )
    p.add_argument(
        "--rpc1",
        default=DEFAULT_RPC1,
        help="Primary RPC URL (default: RPC_URL env var).",
    )
    p.add_argument(
        "--rpc2",
        default=DEFAULT_RPC2,
        help="Secondary RPC URL (default: RPC_URL_2 env var). Optional.",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="HTTP timeout in seconds for each RPC.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of human-readable output.",
    )
    p.add_argument(
        "--no-emoji",
        action="store_true",
        help="Disable emoji in text output (CI-friendly).",
    )
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.rpc1:
        parser.error("Primary RPC is required (use --rpc1 or set RPC_URL).")

    try:
        tx_hash = normalize_hash(args.tx_hash)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    use_emoji = not args.no_emoji
    ok_icon = "✅" if use_emoji else "[OK]"
    warn_icon = "⚠️" if use_emoji else "[WARN]"
    err_icon = "❌" if use_emoji else "[ERR]"

    start = time.monotonic()

    # Connect primary
    try:
        w3_1 = connect(args.rpc1, "primary", args.timeout)
    except Exception as exc:
        print(f"{err_icon} {exc}", file=sys.stderr)
        return 1

    # Connect secondary (optional)
    w3_2 = None
    if args.rpc2:
        try:
            w3_2 = connect(args.rpc2, "secondary", args.timeout)
        except Exception as exc:
            print(f"{warn_icon} Secondary RPC unavailable: {exc}", file=sys.stderr)
            w3_2 = None

    v1 = build_view(w3_1, args.rpc1, tx_hash)
    v2 = build_view(w3_2, args.rpc2, tx_hash) if w3_2 is not None else None

    elapsed = round(time.monotonic() - start, 3)

    if args.json:
        out: Dict[str, Any] = {
            "txHash": tx_hash,
            "primary": asdict(v1),
            "secondary": asdict(v2) if v2 is not None else None,
            "comparison": compare_views(v1, v2) if v1.ok and v2 and v2.ok else None,
            "timingSec": elapsed,
        }
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0 if (v1.ok and (v2 is None or v2.ok)) else 1

    # Human-readable
    print(f"Tx: {tx_hash}")
    print(f"Primary RPC  : {args.rpc1}")
    if args.rpc2:
        print(f"Secondary RPC: {args.rpc2}")
    print()

    def print_view(label: str, v: TxView) -> None:
        if not v.ok:
            print(f"{label}: {err_icon} {v.error}")
            return
        print(f"{label}: {ok_icon} chainId={v.chain_id} block={v.block_number} status={v.status}")
        print(
            f"  gasUsed={v.gas_used}  gasPrice={fmt_gwei(v.gas_price_wei)} Gwei  "
            f"fee={fmt_eth(v.total_fee_wei)} ETH  conf={v.confirmations}"
        )

    print_view("Primary", v1)
    if v2 is not None:
        print_view("Secondary", v2)

    if v2 is not None and v1.ok and v2.ok:
        cmp_res = compare_views(v1, v2)
        mismatches = [k for k, ok in cmp_res.items() if not ok]
        if mismatches:
            print(f"\n{warn_icon} Mismatched fields: {', '.join(mismatches)}")
            return 1
        else:
            print(f"\n{ok_icon} All comparable fields match across RPCs.")
    elif v2 is None:
        print(f"\n{warn_icon} Only primary RPC was available; no cross-check performed.")

    print(f"\nElapsed: {elapsed}s")
    return 0 if v1.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
