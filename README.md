# README.md
# tx-fee-soundness

## Overview
This repository contains a simple Python script that verifies the soundness of an Ethereum transaction by fetching its receipt, displaying execution details, and computing the **total transaction fee**.  
It provides a minimal but clear way to inspect a transaction’s **economic footprint** and confirm that its state matches across RPC endpoints.

## Features
- Connects to any Ethereum-compatible RPC endpoint
- Displays key transaction info: from, to, block, status
- Calculates gas price, gas used, and total fee in ETH
- Shows confirmations and timestamp
- Detects pending transactions
- Useful for developers verifying transaction finality and consistency

## Installation
1. Install Python 3.10 or higher.
2. Install dependency:

   ### CLI options

Some useful flags:

- `--rpc`: HTTP RPC endpoint (required)
- `--timeout`: RPC request timeout in seconds (default: 10)
- `--min-confirmations`: Require at least N confirmations
- `--short`: Print a single-line summary
- `--no-emoji`: Disable emoji in the output

   pip install web3

## Example Output

Connected to Ethereum Mainnet (chainId 1)
Tx Hash: 0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
From:    0x742d35Cc6634C0532925a3b844Bc454e4438f44e
To:      0x00000000219ab540356cBB839Cbe05303d7705Fa
Block:   18945023
Block Time: 2025-11-09 15:41:32 UTC
Status:  ✅ Success
⛽ Gas Used: 64231
⛽ Gas Price: 24.31 Gwei
💰 Total Fee: 0.001562 ETH
✅ Confirmations: 8
⏱️ Elapsed: 2.45s



---

## Supported networks

The script uses only standard JSON-RPC calls, so it works on:

- Ethereum Mainnet
- Testnets like Sepolia / Goerli
- L2s such as Optimism, Base, Arbitrum
- Sidechains like Polygon

As long as your RPC endpoint is Ethereum-compatible, you can point `--rpc` at it.

## Notes

Works on Mainnet, Sepolia, and other EVM networks.
If the transaction is still pending, the script will exit gracefully.
Gas price may vary depending on EIP-1559 vs legacy type.
The fee and confirmation count are live data points; they can change slightly as new blocks are mined.
For cross-checking soundness across providers, rerun the script with a second RPC and compare output values.

### Exit codes

- `0` – script ran successfully (even if the transaction failed on-chain)
- `1` – an error occurred (invalid RPC, invalid tx hash, tx not found, etc.)

You can use this in shell scripts or CI to fail builds when checks are not satisfied.

