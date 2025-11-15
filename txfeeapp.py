# app.py
import os
import sys
import time
from web3 import Web3

# Default RPC configuration
RPC_URL = os.getenv("RPC_URL", "https://mainnet.infura.io/v3/your_api_key")

def get_network_name(chain_id: int) -> str:
    networks = {
        1: "Ethereum Mainnet",
        11155111: "Sepolia Testnet",
        137: "Polygon",
        10: "Optimism",
        42161: "Arbitrum One",
    }
    return networks.get(chain_id, f"Unknown (chain ID {chain_id})")

def wei_to_eth(value: int) -> float:
    return Web3.from_wei(value, "ether")

def main():
    if len(sys.argv) != 2:
        print("Usage: python app.py <tx_hash>")
        sys.exit(1)

    tx_hash = sys.argv[1]
    if not tx_hash.startswith("0x") or len(tx_hash) != 66:
        print("❌ Invalid transaction hash format.")
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("❌ Failed to connect to RPC endpoint.")
        sys.exit(1)

    print(f"🌐 Connected to {get_network_name(w3.eth.chain_id)} (chainId {w3.eth.chain_id})")
    start_time = time.time()

    try:
        tx = w3.eth.get_transaction(tx_hash)
        if tx and tx.blockNumber is None:
            print("⏳ Transaction is still pending and not yet mined.")
            sys.exit(0)
        rcpt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception as e:
        print(f"❌ Error fetching transaction: {e}")
        sys.exit(2)

    # Extract info
    block_number = rcpt.blockNumber
    block = w3.eth.get_block(block_number)
    status = rcpt.status
    gas_used = rcpt.gasUsed
    gas_price = getattr(rcpt, "effectiveGasPrice", None) or getattr(rcpt, "gasPrice", None)
    total_fee_eth = wei_to_eth(gas_used * gas_price) if gas_price else 0.0
        confirmations = w3.eth.block_number - block_number
    if confirmations < 0:
        confirmations = 0

    print(f"🔗 Tx Hash: {tx_hash}")
    print(f"👤 From: {tx['from']}")
    print(f"🎯 To: {tx['to']}")
    print(f"🔢 Block: {block_number}")
    print(f"🕒 Block Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(block.timestamp))} UTC")
    print(f"📦 Status: {'✅ Success' if status == 1 else '❌ Failed'}")
    print(f"⛽ Gas Used: {gas_used}")
    print(f"⛽ Gas Price: {Web3.from_wei(gas_price, 'gwei'):.2f} Gwei")
    print(f"💰 Total Fee: {total_fee_eth:.6f} ETH")
    print(f"✅ Confirmations: {confirmations}")
    print(f"⏱️  Elapsed: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    main()
