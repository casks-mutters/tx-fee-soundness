"""
CLI tool to batch-check Ethereum-style transaction fees and confirmations
across multiple chains using a single RPC endpoint.
"""
import argparse
import sys
import time
from datetime import datetime, timezone
from typing import List, Optional

from web3 import Web3
from web3.exceptions import TransactionNotFound

CHAIN_NAMES = {
    1: "Ethereum Mainnet",
    5: "Goerli",
    11155111: "Sepolia",
    10: "Optimism",
    42161: "Arbitrum One",
    8453: "Base",
    137: "Polygon",
}
VERSION = "0.1.0"
def fmt_eth(wei: Optional[int]) -> str:
    if wei is None:
        return "-"
    return f"{Web3.from_wei(wei, 'ether'):.6f}"


def fmt_gwei(wei: Optional[int]) -> str:
    if wei is None:
        return "-"
    return f"{Web3.from_wei(wei, 'gwei'):.2f}"


def fmt_ts(ts: Optional[int]) -> str:
    if ts is None:
        return "-"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


Args = argparse.Namespace
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Batch-check transaction fee soundness for multiple tx hashes."
    )
    p.add_argument(
        "--min-confirmations",
        type=int,
        default=0,
        help="Minimum confirmation count required per transaction (must be >= 0).",
    )

    p.add_argument(
        "--rpc",
        required=True,
        help="HTTP RPC endpoint URL (e.g. https://mainnet.infura.io/v3/KEY)",
    )
    p.add_argument(
        "--tx",
        action="append",
        default=[],
        help="Transaction hash (0x...). Can be specified multiple times.",
    )
    p.add_argument(
        "--file",
        help="Optional path to a file with one transaction hash per line.",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="RPC request timeout in seconds (default: 10)",
    )
    p.add_argument(
        "--max-fee-eth",
        type=float,
        default=None,
        help="If set, mark and fail if any tx fee exceeds this threshold (in ETH).",
    )
    p.add_argument(
        "--no-emoji",
        action="store_true",
        help="Disable emoji in output (useful for CI logs).",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
        help="Show program version and exit.",
    )

    return p


def load_hashes(args: Args) -> List[str]:

    hashes: List[str] = []

    if args.tx:
        hashes.extend(args.tx)

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                for line in f:
               line = line.strip()
        except OSError as exc:
            print(f"❌ Failed to read file {args.file}: {exc}", file=sys.stderr)
            sys.exit(1)

    # Deduplicate while preserving order
    seen = set()
    unique_hashes: List[str] = []
    for h in hashes:
        if h not in seen:
            seen.add(h)
            unique_hashes.append(h)

    return unique_hashes


def normalize_hash(tx_hash: str) -> Optional[str]:
    tx_hash = tx_hash.strip()
    if not tx_hash:
        return None
    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash
    try:
        # Make sure it's interpreted as a hex string
        tx_hash = Web3.to_hex(hexstr=tx_hash)
    except Exception:
        return None
    if len(tx_hash) != 66:
        return None
    return tx_hash



def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.min_confirmations < 0:
        print("ERROR: --min-confirmations must be >= 0", file=sys.stderr)
        return 1

    start_time = time.time()

    use_emoji = not args.no_emoji
    warn_emoji = "⚠️ " if use_emoji else "WARN: "
    err_emoji = "❌ " if use_emoji else "ERROR: "
    ok_emoji = "✅ " if use_emoji else ""
    pending_emoji = "⏳ " if use_emoji else "PENDING: "

    hashes_raw = load_hashes(args)
    if not hashes_raw:
        print(f"{err_emoji}No transaction hashes provided (use --tx and/or --file).", file=sys.stderr)
        return 1

    # Connect to RPC
    try:
        w3 = Web3(Web3.HTTPProvider(args.rpc, request_kwargs={"timeout": args.timeout}))
    except Exception as exc:
        print(f"{err_emoji}Failed to create Web3 provider: {exc}", file=sys.stderr)
        return 1

    if not w3.is_connected():
        print(f"{err_emoji}Could not connect to RPC endpoint: {args.rpc}", file=sys.stderr)
        return 1

    try:
        chain_id = w3.eth.chain_id
    except Exception:
        chain_id = None

      # Basic intro line
    if chain_id is not None:
        network_name = CHAIN_NAMES.get(chain_id)
        if network_name is None:
            network_name = "Unknown network"
        print(f"Connected to RPC {args.rpc} (chainId {chain_id}, {network_name})")

    else:
        print(f"Connected to RPC {args.rpc}")
    if args.max_fee_eth is not None:
        print(
            f"Max fee threshold enabled: {args.max_fee_eth:.6f} ETH "
            "(transactions exceeding this will be flagged)."
        )
    if args.min_confirmations > 0:
        print(
            f"Minimum confirmations required per transaction: {args.min_confirmations}"
        )


    # Fetch latest block once for confirmation estimates; may be slightly stale but OK for batch
    try:
        latest_block = w3.eth.block_number
    except Exception as exc:
        print(f"{warn_emoji}Failed to fetch latest block number: {exc}", file=sys.stderr)
        latest_block = None

     any_error = False
    any_fee_violation = False

    print("\n# tx | status | block | time(UTC) | conf | fee(ETH) | gasUsed | gasPrice(Gwei)")
    print("# ------------------------------------------------------------------------------")


    for raw in hashes_raw:
        tx_hash = normalize_hash(raw)
        if tx_hash is None:
            print(f"{err_emoji}invalid-hash | {raw}")
            any_error = True
            continue

        try:
            tx = w3.eth.get_transaction(tx_hash)
           except TransactionNotFound:
            print(f"{err_emoji}{tx_hash} | not-found | - | - | - | - | -", file=sys.stderr)
            any_error = True
            continue
             except Exception as exc:
            print(f"{err_emoji}{tx_hash} | error-fetching-receipt: {exc}", file=sys.stderr)
            any_error = True
            continue



        # Try to get receipt
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
        except TransactionNotFound:
            # Pending tx
            print(
                f"{pending_emoji}{tx_hash} | pending | - | - | - | - | -"
            )
            continue
        except Exception as exc:
            print(f"{err_emoji}{tx_hash} | error-fetching-receipt: {exc}")
            any_error = True
            continue

        block_number = receipt.blockNumber
        status = receipt.status
        gas_used = receipt.gasUsed
        block_time_str = "-"
        if block_number is not None:
            try:
                block = w3.eth.get_block(block_number)
                block_time_str = fmt_ts(block.timestamp)
            except Exception:
                block_time_str = "-"

        gas_price_wei = getattr(receipt, "effectiveGasPrice", None)
        if gas_price_wei is None:
            gas_price_wei = tx.get("gasPrice")

        total_fee_wei: Optional[int]
        if gas_used is not None and gas_price_wei is not None:
            total_fee_wei = gas_used * gas_price_wei
        else:
            total_fee_wei = None

        # Confirmations
        if latest_block is not None and block_number is not None:
            confirmations = max(0, latest_block - block_number + 1)
        else:
            confirmations = None
        if confirmations is not None and confirmations < args.min_confirmations:
            any_error = True
            print(
                f"{warn_emoji}Confirmations {confirmations} below minimum "
                f"{args.min_confirmations} for tx {tx_hash}",
                file=sys.stderr,
            )

        fee_eth_str = fmt_eth(total_fee_wei)
        gas_price_gwei_str = fmt_gwei(gas_price_wei)

            status_str = "success" if status == 1 else "failed"
        icon = ok_emoji if status == 1 else err_emoji

        print(
            f"{icon}{tx_hash} | {status_str} | "
            f"{block_number if block_number is not None else '-'} | "
            f"{block_time_str} | "
            f"{confirmations if confirmations is not None else '-'} | "
            f"{fee_eth_str} | "
            f"{gas_used if gas_used is not None else '-'} | "
            f"{gas_price_gwei_str}"
        )

        # Check fee threshold if configured
        if args.max_fee_eth is not None and total_fee_wei is not None:
            fee_eth_float = float(Web3.from_wei(total_fee_wei, "ether"))
            if fee_eth_float > args.max_fee_eth:
                any_fee_violation = True
                print(
                    f"{warn_emoji}Fee {fee_eth_float:.6f} ETH exceeds threshold "
                    f"{args.max_fee_eth:.6f} ETH for tx {tx_hash}",
                    file=sys.stderr,
                )

    elapsed = time.time() - start_time
    if elapsed < 1:
        elapsed_str = f"{elapsed * 1000:.0f}ms"
    else:
        elapsed_str = f"{elapsed:.2f}s"

    print(f"\nProcessed {len(hashes_raw)} transaction(s) in {elapsed_str}.")

    # Exit codes:
    # - 0 if everything was fine and no fee violations
    # - 1 if any errors or fee violations occurred
    if any_error or any_fee_violation:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
