#!/usr/bin/env python3
import os
import sys
import time
import requests
from web3 import Web3
from web3.middleware import geth_poa_middleware

# Config: set your RPC_URL and ETHERSCAN_API_KEY env vars
RPC_URL = os.getenv("RPC_URL", "https://mainnet.infura.io/v3/YOUR_PROJECT_ID")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")

def fetch_via_rpc(tx_hash):
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    # if you use a PoA/testnet, uncomment next:
    # w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    receipt = w3.eth.get_transaction_receipt(tx_hash)
    tx = w3.eth.get_transaction(tx_hash)
    return {
        "status": receipt["status"],
        "gasUsed": receipt["gasUsed"],
        "gasPrice": tx.get("gasPrice", None) or receipt.get("effectiveGasPrice"),
        "feeETH": w3.from_wei(receipt["gasUsed"] * (tx.get("gasPrice", 0) or receipt.get("effectiveGasPrice", 0)), "ether"),
    }

def fetch_via_etherscan(tx_hash, chain="mainnet"):
    if not ETHERSCAN_API_KEY:
        raise RuntimeError("Set ETHERSCAN_API_KEY env variable to use Etherscan API")
  base = {
    "mainnet": "https://api.etherscan.io/api",
    "goerli": "https://api-goerli.etherscan.io/api",
    "sepolia": "https://api-sepolia.etherscan.io/api",
}.get(chain, "https://api.etherscan.io/api")

    params = {
        "module": "proxy",
        "action": "eth_getTransactionReceipt",
        "txhash": tx_hash,
        "apikey": ETHERSCAN_API_KEY
    }
    resp = requests.get(base, params=params)
    data = resp.json()
    if data.get("result") is None:
        raise RuntimeError("Etherscan API error: %s" % data)
    res = data["result"]
    return {
        "status": int(res.get("status", "0x0"), 16),
        "gasUsed": int(res.get("gasUsed", "0x0"), 16),
        "gasPrice": int(res.get("effectiveGasPrice", res.get("gasPrice", "0x0")), 16),
        "feeETH": Web3.from_wei(int(res.get("gasUsed", "0x0"), 16) * (int(res.get("effectiveGasPrice", res.get("gasPrice", "0x0")), 16)), "ether"),
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python compare_etherscan_vs_rpc.py <tx_hash> [chain]")
        sys.exit(1)
    tx_hash = sys.argv[1]
    chain = sys.argv[2] if len(sys.argv) >= 3 else "mainnet"

    print("Fetching via RPC:", RPC_URL)
    rpc = fetch_via_rpc(tx_hash)
    print("RPC  ->", rpc)

    print("Fetching via Etherscan (chain=%s)" % chain)
    try:
        es = fetch_via_etherscan(tx_hash, chain)
        print("Etherscan ->", es)
    except Exception as e:
        print("Failed to fetch via Etherscan:", e)
        sys.exit(1)

    diffs = []
    for key in ("status", "gasUsed", "gasPrice", "feeETH"):
        if rpc.get(key) != es.get(key):
            diffs.append(key)
    if diffs:
        print("⚠️  Discrepancies detected:", diffs)
    else:
        print("✅  RPC and Etherscan values match.")

if __name__ == "__main__":
    main()
