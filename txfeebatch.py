#!/usr/bin/env python3
"""
Profile recent gas behavior on an EVM network.

Samples recent blocks and computes percentiles for:
- base fee (Gwei)
- effective gas price (Gwei)
- approximate priority tip (Gwei)
"""

# Example:
#   python fee_profile.py \
#       --rpc https://mainnet.infura.io/v3/YOUR_KEY \
#       --blocks 300 --step 3 --json

import argparse
import json
import os
import sys
import time
from statistics import median
from typing import Dict, List, Optional, Tuple

from web3 import Web3


__version__ = "0.1.0"

DEFAULT_RPC = os.getenv("RPC_URL", "https://mainnet.infura.io/v3/YOUR_API_KEY")
DEFAULT_BLOCKS = int(os.getenv("FEE_PROFILE_BLOCKS", "300"))
DEFAULT_STEP = int(os.getenv("FEE_PROFILE_STEP", "3"))
DEFAULT_TIMEOUT = int(os.getenv("FEE_PROFILE_TIMEOUT", "30"))

# Re-use the same kind of mapping as tx_fee_compare
NETWORKS: Dict[int, str] = {
    1: "Ethereum Mainnet",
    11155111: "Sepolia Testnet",
    10: "Optimism",
    137: "Polygon",
    42161: "Arbitrum One",
    8453: "Base",
    59144: "Linea",
    324: "zkSync Era",
}


def network_name(cid: Optional[int]) -> str:
    """Map a chain ID to a human-readable network name."""
    if cid is None:
        return "Unknown"
    return NETWORKS.get(cid, f"Unknown (chainId {cid})")


def connect(rpc: str, timeout: int) -> Web3:
    """Connect to an RPC endpoint and print a short banner."""
    start = time.time()
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": timeout}))

    if not w3.is_connected():
        print(f"❌ Failed to connect to RPC endpoint: {rpc}", file=sys.stderr)
        sys.exit(1)

    # Optional PoA middleware for some L2s/testnets
    try:
        from web3.middleware import geth_poa_middleware

        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    except Exception:
        # Best-effort; ignore if unavailable
        pass

    latest = w3.eth.block_number
    try:
        cid = int(w3.eth.chain_id)
    except Exception:
        cid = None

    latency = time.time() - start
    print(
        f"🌐 chainId={cid} ({network_name(cid)}) tip={latest}",
        file=sys.stderr,
    )
    print(f"⚡ RPC connected in {latency:.2f}s", file=sys.stderr)
    return w3


def pct(values: List[float], q: float) -> float:
    """Return the q-th percentile (0..1) of a list of floats."""
    if not values:
        return 0.0
    q = max(0.0, min(1.0, q))
    sorted_vals = sorted(values)
    idx = int(round(q * (len(sorted_vals) - 1)))
    return sorted_vals[idx]


def sample_block_fees(block, base_fee_wei: int) -> Tuple[List[float], List[float]]:
    """
    Returns (effective_prices_gwei, tip_gwei_approx) for txs in the block.

    Approximation:
      - EIP-1559: effective ~= min(maxFeePerGas, baseFee + maxPriorityFeePerGas)
                  tip ~= maxPriorityFeePerGas
      - Legacy:   effective = gasPrice
                  tip ~= max(0, gasPrice - baseFee)
    """
    eff: List[float] = []
    tip: List[float] = []
    bf = int(base_fee_wei) if base_fee_wei is not None else 0

    for tx in block.transactions:
        # web3.py may return AttributeDict or dict
        if isinstance(tx, dict):
            ttype = tx.get("type", 0)
            mpp = tx.get("maxPriorityFeePerGas", 0)
            mfp = tx.get("maxFeePerGas", 0)
            gp = tx.get("gasPrice", 0)
        else:
            ttype = getattr(tx, "type", 0)
            mpp = getattr(tx, "maxPriorityFeePerGas", 0)
            mfp = getattr(tx, "maxFeePerGas", 0)
            gp = getattr(tx, "gasPrice", 0)

        if ttype == 2:  # EIP-1559
            mpp = int(mpp or 0)
            mfp = int(mfp or 0)
            effective = min(mfp, bf + mpp)
            eff.append(float(Web3.from_wei(effective, "gwei")))
            tip.append(float(Web3.from_wei(mpp, "gwei")))
        else:
            gp = int(gp or 0)
            eff.append(float(Web3.from_wei(gp, "gwei")))
            tip.append(float(Web3.from_wei(max(0, gp - bf), "gwei")))

    return eff, tip


def analyze(
    w3: Web3,
    blocks: int,
    step: int,
    head_override: Optional[int] = None,
) -> Dict[str, object]:
    """
    Scan recent blocks and compute gas fee statistics.

    Returns a dict with:
      - chainId, network, head, sampledBlocks, blockSpan, step, timingSec
      - avgBlockTimeSec
      - baseFeeGwei      {p50, p95, min, max}
      - effectivePriceGwei {p50, p95, min, max, count}
      - tipGweiApprox      {p50, p95, min, max, count, countZero}
    """
    head = int(head_override) if head_override is not None else int(w3.eth.block_number)
    start = max(0, head - blocks + 1)
    t0 = time.time()

    basefees: List[float] = []
    eff_prices: List[float] = []
    tips: List[float] = []

    print(
        f"🔍 Scanning the last {blocks} blocks (every {step}th block)...",
        file=sys.stderr,
    )

    # Iterate backwards in steps for speed
    for n in range(head, start - 1, -step):
        blk = w3.eth.get_block(n, full_transactions=True)
        # EIP-1559 base fee may be under different attribute names
        bf = getattr(blk, "baseFeePerGas", None)
        if bf is None:
            bf = getattr(blk, "base_fee_per_gas", 0) or 0
        bf = int(bf)

        basefees.append(float(Web3.from_wei(bf, "gwei")))
        eff_gwei, tip_gwei = sample_block_fees(blk, bf)
        eff_prices.extend(eff_gwei)
        tips.extend(tip_gwei)

        # Show progress every 20 sampled blocks
        if len(basefees) % 20 == 0:
            print(
                f"🔍 Sampled {len(basefees)} blocks so far (latest={n})",
                file=sys.stderr,
            )

    elapsed = time.time() - t0

    # Estimate average block time using endpoints of the span
    if len(basefees) >= 2 and head > start:
        first_block = w3.eth.get_block(head)
        last_block = w3.eth.get_block(start)
        time_diff = int(first_block.timestamp) - int(last_block.timestamp)
        block_time_avg = max(0.0, time_diff / float(head - start))
    else:
        block_time_avg = 0.0

    zero_tip_count = sum(1 for x in tips if x == 0.0)

    try:
        cid = int(w3.eth.chain_id)
    except Exception:
        cid = None

    return {
        "chainId": cid,
        "network": network_name(cid),
        "avgBlockTimeSec": round(block_time_avg, 2),
        "head": head,
        "sampledBlocks": len(range(head, start - 1, -step)),
        "blockSpan": blocks,
        "step": step,
        "timingSec": round(elapsed, 2),
        "baseFeeGwei": {
            "p50": round(median(basefees), 3) if basefees else 0.0,
            "p95": round(pct(basefees, 0.95), 3) if basefees else 0.0,
            "min": round(min(basefees), 3) if basefees else 0.0,
            "max": round(max(basefees), 3) if basefees else 0.0,
        },
        "effectivePriceGwei": {
            "p50": round(median(eff_prices), 3) if eff_prices else 0.0,
            "p95": round(pct(eff_prices, 0.95), 3) if eff_prices else 0.0,
            "min": round(min(eff_prices), 3) if eff_prices else 0.0,
            "max": round(max(eff_prices), 3) if eff_prices else 0.0,
            "count": len(eff_prices),
        },
        "tipGweiApprox": {
            "p50": round(median(tips), 3) if tips else 0.0,
            "p95": round(pct(tips, 0.95), 3) if tips else 0.0,
            "min": round(min(tips), 3) if tips else 0.0,
            "max": round(max(tips), 3) if tips else 0.0,
            "count": len(tips),
            "countZero": zero_tip_count,
        },
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(
            "Profile recent gas: base fee, effective price, "
            "and priority tip percentiles."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument(
        "--rpc",
        default=DEFAULT_RPC,
        help="RPC URL (default from RPC_URL env).",
    )
    ap.add_argument(
        "-b",
        "--blocks",
        type=int,
        default=DEFAULT_BLOCKS,
        help="How many recent blocks to scan.",
    )
    ap.add_argument(
        "-s",
        "--step",
        type=int,
        default=DEFAULT_STEP,
        help="Sample every Nth block for speed.",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="HTTP RPC timeout in seconds.",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable text.",
    )
    ap.add_argument(
        "--head",
        type=int,
        help="Use this block number as the head instead of the latest.",
    )
    ap.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    # High-level run info → stderr
    print(
        f"📅 Fee profile run started at UTC: "
        f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}",
        file=sys.stderr,
    )
    print(f"⚙️ Using RPC endpoint: {args.rpc}", file=sys.stderr)

    if args.blocks <= 0 or args.step <= 0:
        print("❌ --blocks and --step must be > 0", file=sys.stderr)
        return 1

    # Hard guardrail to avoid accidental abuse
    if args.blocks > 100_000:
        print(
            "❌ --blocks is extremely large (> 100000); refusing to run.",
            file=sys.stderr,
        )
        return 1

    # Soft cap to keep scans cheap
    if args.blocks > 5_000:
        print(
            "⚠️  Limiting --blocks to 5000 to avoid excessive RPC load.",
            file=sys.stderr,
        )
        args.blocks = 5_000

    w3 = connect(args.rpc, timeout=args.timeout)
    result = analyze(w3, args.blocks, args.step, args.head)

    if result["sampledBlocks"] == 0:
        print(
            "⚠️  No blocks were sampled. Check --blocks/--step and head range.",
            file=sys.stderr,
        )

    if args.json:
        payload = {
            "mode": "fee_profile",
            "network": result["network"],
            "chainId": result["chainId"],
            "generatedAtUtc": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.gmtime()
            ),
            "data": result,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    # Human-readable summary
    bf = result["baseFeeGwei"]
    ep = result["effectivePriceGwei"]
    tp = result["tipGweiApprox"]

    print(
        f"🌐 {result['network']} (chainId {result['chainId']})  head={result['head']}"
    )
    print(
        f"📦 Scanned ~{result['sampledBlocks']} blocks over last "
        f"{result['blockSpan']} (step={result['step']}) "
        f"in {result['timingSec']}s"
    )
    print(f"🕒 Average block time: {result['avgBlockTimeSec']} seconds")
    print(
        f"⛽ Base Fee (Gwei):   "
        f"p50={bf['p50']}  p95={bf['p95']}  "
        f"min={bf['min']}  max={bf['max']}"
    )
    print(
        f"💵 Effective Price:   "
        f"p50={ep['p50']}  p95={ep['p95']}  "
        f"min={ep['min']}  max={ep['max']}  (n={ep['count']})"
    )
    print(
        f"🎁 Priority Tip ~:    "
        f"p50={tp['p50']}  p95={tp['p95']}  "
        f"min={tp['min']}  max={tp['max']}  "
        f"(n={tp['count']}, zero={tp.get('countZero', 0)})"
    )

    if tp["count"] > 0:
        zero_tip_pct = tp.get("countZero", 0) / tp["count"] * 100.0
        print(f"🎯 Zero-tip share: {zero_tip_pct:.1f}% of sampled txs")

    print(
        "ℹ️  Tip for EIP-1559 uses tx.maxPriorityFeePerGas; "
        "legacy approximates tip = gasPrice - baseFee."
    )

    print(
        f"\n🕒 Completed at: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} UTC"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        sys.exit(1)
