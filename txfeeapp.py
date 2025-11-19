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
    w3.eth.chain_id
    if not w3.is_connected():
        print("❌ Failed to connect to RPC endpoint.")
        sys.exit(1)

    print(f"🌐 Connected to {get_network_name(w3.eth.chain_id)} (chainId {w3.eth.chain_id})")
    start_time = time.time()

    try:
        tx = w3.eth.get_transaction(tx_hash)
        if tx is None:
    print("❌ Transaction not found on this network.")
    sys.exit(1)
        if tx and tx.blockNumber is None:
            print("⏳ Transaction is still pending and not yet mined.")
            sys.exit(0)
        rcpt = w3.eth.get_transaction_receipt(tx_hash)
        if rcpt is None:
    print("❌ Transaction receipt not available yet.")
    sys.exit(0)
    except Exception as e:
        print(f"❌ Error fetching transaction: {e}")
        sys.exit(2)

    # Extract info
    block_number = rcpt.blockNumber
    block = w3.eth.get_block(block_number)
    print(f"📊 Block Gas Used: {(block.gasUsed / block.gasLimit) * 100:.2f}%")
    status = rcpt.status
    if rcpt.contractAddress:
    print(f"🏗️ Contract Created: {rcpt.contractAddress}")
    gas_used = rcpt.gasUsed
    print(f"📊 Gas Limit vs Used: {tx['gas']} limit / {gas_used} used")
    gas_price = getattr(rcpt, "effectiveGasPrice", None) or getattr(rcpt, "gasPrice", None)
    if gas_price is None:
    gas_price = 0
    total_fee_eth = wei_to_eth(gas_used * gas_price) if gas_price else 0.0
    if tx['value'] > 0:
    print(f"💹 Fee/Value Ratio: { (total_fee_eth / wei_to_eth(tx['value'])) * 100:.4f}%")
    confirmations = w3.eth.block_number - block_number

    print(f"🔗 Tx Hash: {tx_hash}")
    print(f"🔢 Nonce: {tx['nonce']}")
    print(f"👤 From: {tx['from']}")
    print(f"🎯 To: {tx['to']}")
    print(f"💸 Value: {wei_to_eth(tx['value']):.6f} ETH")
    print(f"🔢 Block: {block_number}")
    print(f"🕒 Block Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(block.timestamp))} UTC")
    if block.timestamp > time.time() + 120:
    print("⚠️  Warning: RPC returned a future timestamp.")
    print(f"📦 Status: {'✅ Success' if status == 1 else '❌ Failed'}")
    print(f"⛽ Gas Used: {gas_used}")
    print(f"📏 Gas Limit: {tx['gas']}")
    print(f"⛽ Gas Price: {Web3.from_wei(gas_price, 'gwei'):.2f} Gwei")
    print(f"📉 Cost per gas: {wei_to_eth(gas_price):.12f} ETH/gas")
    print(f"💰 Total Fee: {total_fee_eth:.6f} ETH")
    print(f"✅ Confirmations: {confirmations}")
    if confirmations < 5:
    print("⚠️  Low confirmations — possible reorg risk.")
    print(f"⏱️  Elapsed: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    main()
