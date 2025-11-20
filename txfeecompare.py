import argparse
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from web3 import Web3
from web3.exceptions import TransactionNotFound

@dataclass
class EndpointResult:
    label: str
    rpc_url: str
    connected: bool
    chain_id: Optional[int]

    error: Optional[str]

    tx_found: bool
    pending: bool

    from_addr: Optional[str]
    to_addr: Optional[str]
    block_number: Optional[int]
    block_time: Optional[int]  # unix timestamp
    status: Optional[int]  # 1 success, 0 failure

    gas_used: Optional[int]
    gas_price_wei: Optional[int]
    total_fee_wei: Optional[int]
    confirmations: Optional[int]



def fmt_eth(wei: Optional[int]) -> str:
    if wei is None:
        return "-"
    return f"{Web3.from_wei(wei, 'ether'):.6f}"



def fmt_gwei(wei: int) -> str:
    return f"{Web3.from_wei(wei, 'gwei'):.2f}"


def fmt_ts(ts: Optional[int]) -> str:
    # Block timestamp is seconds since epoch (UTC)
    if ts is None:
        return "-"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")



def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Compare an Ethereum transaction across multiple RPC endpoints."
    )
 p.add_argument(
        "--no-emoji",
        action="store_true",
        help="Disable emoji in output",
    )
    
    p.add_argument(
        "--rpc",
        action="append",
        required=True,
        help="HTTP RPC endpoint URL. Can be specified multiple times.",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="RPC request timeout in seconds (default: 10)",
    )
        p.add_argument(
        "--min-confirmations",
        type=int,
        default=0,
        help="Minimum confirmation count required (default: 0)",
    )

    return p


def check_endpoint(
    label: str, rpc_url: str, tx_hash: str, timeout: int
) -> EndpointResult:
        try:
        w3 = Web3(Web3.HTTPProvider(args.rpc, request_kwargs={"timeout": args.timeout}))
    except Exception as exc:
        print(f"❌ Failed to create Web3 provider: {exc}", file=sys.stderr)
        return 1

    if not w3.is_connected():
        print(f"❌ Could not connect to RPC endpoint: {args.rpc}", file=sys.stderr)
        return 1

        return EndpointResult(
            label=label,
            rpc_url=rpc_url,
            connected=False,
            chain_id=None,
            error="could not connect",
            tx_found=False,
            pending=False,
            from_addr=None,
            to_addr=None,
            block_number=None,
            block_time=None,
            status=None,
            gas_used=None,
            gas_price_wei=None,
            total_fee_wei=None,
            confirmations=None,
        )

    try:
        chain_id = w3.eth.chain_id
    except Exception:
        chain_id = None

    # Normalize hash
        # Basic validation of tx hash
    tx_hash = Web3.to_hex(args.tx_hash)
    if not tx_hash.startswith("0x") or len(tx_hash) != 66:
        print(f"❌ Invalid transaction hash format: {tx_hash}", file=sys.stderr)
        return 1


    try:
       tx_type = tx.get("type", "0x0")
    print(f"Tx Type: {tx_type}")
        tx_found = True
    except TransactionNotFound:
        return EndpointResult(
            label=label,
            rpc_url=rpc_url,
            connected=True,
            chain_id=chain_id,
            error="transaction not found",
            tx_found=False,
            pending=False,
            from_addr=None,
            to_addr=None,
            block_number=None,
            block_time=None,
            status=None,
            gas_used=None,
            gas_price_wei=None,
            total_fee_wei=None,
            confirmations=None,
        )

    # Try to get receipt
     try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except TransactionNotFound:
        print(f"⏳ Transaction pending: {tx_hash}")
        print(f"From: {tx['from']}")
        print(f"To:   {tx['to']}")
        return 0

        # Present in mempool, but no receipt yet
        return EndpointResult(
            label=label,
            rpc_url=rpc_url,
            connected=True,
            chain_id=chain_id,
            error=None,
            tx_found=True,
            pending=True,
            from_addr=tx["from"],
            to_addr=tx["to"],
            block_number=None,
            block_time=None,
            status=None,
            gas_used=None,
            gas_price_wei=None,
            total_fee_wei=None,
            confirmations=None,
        )

    block_number = receipt.blockNumber
    if block_number is None:
        # Should be rare; treat as pending-ish
        return EndpointResult(
            label=label,
            rpc_url=rpc_url,
            connected=True,
            chain_id=chain_id,
            error=None,
            tx_found=True,
            pending=True,
            from_addr=tx["from"],
            to_addr=tx["to"],
            block_number=None,
            block_time=None,
            status=None,
            gas_used=None,
            gas_price_wei=None,
            total_fee_wei=None,
            confirmations=None,
        )

    block = w3.eth.get_block(block_number)
    latest_block = w3.eth.block_number

    status = receipt.status
    gas_used = receipt.gasUsed

    # EIP-1559 effectiveGasPrice preferred
    gas_price_wei = getattr(receipt, "effectiveGasPrice", None)
    if gas_price_wei is None:
        gas_price_wei = tx.get("gasPrice", None)

    total_fee_wei = (
        gas_used * gas_price_wei if gas_used is not None and gas_price_wei is not None else None
    )

       confirmations = max(0, latest_block - block_number + 1)

    if confirmations < args.min_confirmations:
        print(
            f"⚠️ Confirmations ({confirmations}) are below required minimum "
            f"({args.min_confirmations}).",
            file=sys.stderr,
        )


    return EndpointResult(
        label=label,
        rpc_url=rpc_url,
        connected=True,
        chain_id=chain_id,
        error=None,
        tx_found=True,
        pending=False,
        from_addr=tx["from"],
        to_addr=tx["to"],
        block_number=block_number,
        block_time=block.timestamp,
        status=status,
        gas_used=gas_used,
        gas_price_wei=gas_price_wei,
        total_fee_wei=total_fee_wei,
        confirmations=confirmations,
    )
    p.add_argument(
        "--short",
        action="store_true",
        help="Print a single-line summary instead of detailed output",
    )


def summarize_inconsistencies(results: List[EndpointResult]) -> List[str]:
    ok_results = [r for r in results if r.connected and r.tx_found and not r.pending]

    notes: List[str] = []
    if len(ok_results) < 2:
        return notes

    def collect(field: str) -> Dict[Any, List[str]]:
        values: Dict[Any, List[str]] = {}
        for r in ok_results:
            v = getattr(r, field)
            values.setdefault(v, []).append(r.label)
        return values
    if args.short:
        print(
            f"{tx_hash} | status={'success' if receipt.status == 1 else 'failed'} | "
            f"fee={fmt_eth(total_fee_wei)} ETH | "
            f"block={block_number} | conf={confirmations}"
        )
        return 0

    # ChainId
    chains = collect("chain_id")
    if len(chains) > 1:
        notes.append("⚠️ Mismatched chainId across endpoints.")

    # Status
    statuses = collect("status")
    if len(statuses) > 1:
        notes.append("⚠️ Mismatched transaction status across endpoints.")

    # Block number
    blocks = collect("block_number")
    if len(blocks) > 1:
        notes.append("⚠️ Mismatched block number across endpoints.")

    # Gas used
    gas_used = collect("gas_used")
    if len(gas_used) > 1:
        notes.append("⚠️ Mismatched gasUsed across endpoints.")

    # Gas price
    gas_price = collect("gas_price_wei")
    if len(gas_price) > 1:
        notes.append("⚠️ Mismatched gas price across endpoints (can happen with different EIP-1559 views).")

    # Total fee
    total_fee = collect("total_fee_wei")
    if len(total_fee) > 1:
        notes.append("⚠️ Mismatched total fee across endpoints.")

    if not notes:
        notes.append("✅ All checked fields are consistent across reachable endpoints.")
    gas_limit = tx.get("gas", None)

    print(f"⛽ Gas Used:   {gas_used}")
    if gas_limit is not None:
        print(f"⛽ Gas Limit:  {gas_limit}")

    return notes


def print_table(results: List[EndpointResult], tx_hash: str, elapsed: float) -> None:
    print(f"\n=== tx-fee-soundness comparison ===")
    print(f"Tx Hash: {tx_hash}\n")

    # Endpoint summary
    for i, r in enumerate(results, start=1):
        label = r.label
        chain_part = f"chainId {r.chain_id}" if r.chain_id is not None else "chainId ?"

        if not r.connected:
            print(f"[{i}] {label}: ❌ cannot connect ({r.error})")
            continue

        if not r.tx_found:
            print(f"[{i}] {label}: ⚠️ connected ({chain_part}), tx NOT FOUND ({r.error})")
            continue

        if r.pending:
            print(f"[{i}] {label}: ⏳ connected ({chain_part}), tx PENDING (no receipt yet)")
                gas_prefix = "⛽ " if use_emoji else ""
    fee_prefix = "💰 " if use_emoji else ""
    time_prefix = "⏱️ " if use_emoji else ""

    print(f"{gas_prefix}Gas Used:   {gas_used}")
    print(f"{fee_prefix}Total Fee:  {fmt_eth(total_fee_wei)} ETH")
    print(f"{time_prefix}Elapsed: {elapsed:.2f}s")

            continue

           status_emoji = "✅" if receipt.status == 1 else "❌"
    if not use_emoji:
        status_emoji = ""  # or set to plain text
        print(
            f"[{i}] {label}: {status_emoji} connected ({chain_part}), "
            f"block {r.block_number}, fee {fmt_eth(r.total_fee_wei)} ETH"
        )

    print("\n--- Detailed comparison ---\n")

    # Header row
    col_width = 26
    def col(text: str) -> str:
        return text.ljust(col_width)

    header = col("Field") + "".join(col(r.label) for r in results)
    print(header)
    print("-" * len(header))

    def row(field_name: str, values: List[str]) -> None:
        print(col(field_name) + "".join(col(v) for v in values))

    # Status row
    status_vals = []
    for r in results:
        if not r.connected:
            status_vals.append("offline")
        elif not r.tx_found:
            status_vals.append("not found")
        elif r.pending:
            status_vals.append("pending")
        else:
            status_vals.append("success" if r.status == 1 else "failed")
    row("status", status_vals)

    # ChainId row
    row("chainId", [str(r.chain_id) if r.chain_id is not None else "-" for r in results])

    # Block
    row("block", [str(r.block_number) if r.block_number is not None else "-" for r in results])

    # Block time
    row("block time", [fmt_ts(r.block_time) for r in results])

    # From / To
    row("from", [r.from_addr or "-" for r in results])
    row("to", [r.to_addr or "-" for r in results])

    # Gas used
    row("gasUsed", [str(r.gas_used) if r.gas_used is not None else "-" for r in results])

    # Gas price
    row("gasPrice (Gwei)", [fmt_gwei(r.gas_price_wei) for r in results])

    # Total fee
    row("total fee (ETH)", [fmt_eth(r.total_fee_wei) for r in results])

    # Confirmations
    row("confirmations", [str(r.confirmations) if r.confirmations is not None else "-" for r in results])

    print("\n--- Soundness notes ---")
    for note in summarize_inconsistencies(results):
        print(note)

       if elapsed < 1:
        print(f"⏱️ Elapsed: {elapsed * 1000:.0f}ms")
    else:
        print(f"⏱️ Elapsed: {elapsed:.2f}s")



def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    use_emoji = not getattr(args, "no_emoji", False)

    if len(args.rpc) < 2:
        print("You must provide at least two --rpc endpoints to compare.", file=sys.stderr)
        return 1

    tx_hash = args.tx_hash
    timeout = args.timeout
   
    print(f"Tx Type: {tx_type}")

    start = time.time()

    results: List[EndpointResult] = []
    for idx, rpc_url in enumerate(args.rpc, start=1):
        label = f"RPC {idx}"
        print(f"Connecting to {label}: {rpc_url}")
        res = check_endpoint(label, rpc_url, tx_hash, timeout)
        results.append(res)

    elapsed = time.time() - start
    print_table(results, Web3.to_hex(tx_hash), elapsed)

    # Exit with non-zero code if there are obvious inconsistencies
    notes = summarize_inconsistencies(results)
    has_warning = any(n.startswith("⚠️") for n in notes)
    return 1 if has_warning else 0


if __name__ == "__main__":
    raise SystemExit(main())
