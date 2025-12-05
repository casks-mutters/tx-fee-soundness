# txfee/__init__.py

"""
txfee: tiny library to inspect an Ethereum transaction's economic footprint.

Main features:
- Connect to an Ethereum-compatible JSON-RPC endpoint
- Fetch transaction + receipt
- Compute total fee
- Check confirmations
- Provide reusable Python API + CLI wrapper
"""

from .core import (
    TxFeeConfig,
    TxFeeResult,
    inspect_transaction,
)
