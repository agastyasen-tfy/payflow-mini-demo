"""PayFlow Transactions MCP Server.

A tiny FastMCP server with 3 tools over an in-memory fake transactions DB.
Register this on the TrueFoundry MCP Gateway (auth: API key / no-auth for demo).

Run:  python server.py   (serves streamable-http on :8001 at /mcp)
"""
import os
from datetime import datetime

from fastmcp import FastMCP

mcp = FastMCP("payflow-transactions")

TRANSACTIONS = {
    "txn_1001": {"transaction_id": "txn_1001", "customer_id": "cust_42", "amount": 129.99,
                 "currency": "USD", "status": "completed", "merchant": "Acme Subscriptions",
                 "created_at": "2026-01-28T10:12:00Z", "refunded": False},
    "txn_1002": {"transaction_id": "txn_1002", "customer_id": "cust_42", "amount": 24.50,
                 "currency": "USD", "status": "completed", "merchant": "CloudPrint Co",
                 "created_at": "2026-02-02T08:30:00Z", "refunded": False},
    "txn_1003": {"transaction_id": "txn_1003", "customer_id": "cust_7", "amount": 480.00,
                 "currency": "USD", "status": "disputed", "merchant": "JetSet Travel",
                 "created_at": "2026-02-10T17:45:00Z", "refunded": False},
}


@mcp.tool
def list_transactions(customer_id: str) -> list[dict]:
    """List all transactions for a customer by customer_id (e.g. cust_42)."""
    return [t for t in TRANSACTIONS.values() if t["customer_id"] == customer_id]


@mcp.tool
def get_transaction(transaction_id: str) -> dict:
    """Get full details of a single transaction by transaction_id (e.g. txn_1001)."""
    txn = TRANSACTIONS.get(transaction_id)
    if not txn:
        return {"error": f"transaction {transaction_id} not found"}
    return txn


@mcp.tool
def issue_refund(transaction_id: str, reason: str) -> dict:
    """Issue a full refund for a transaction. Requires a reason string."""
    txn = TRANSACTIONS.get(transaction_id)
    if not txn:
        return {"error": f"transaction {transaction_id} not found"}
    if txn["refunded"]:
        return {"error": f"transaction {transaction_id} is already refunded"}
    txn["refunded"] = True
    txn["status"] = "refunded"
    return {"ok": True, "transaction_id": transaction_id, "refunded_amount": txn["amount"],
            "currency": txn["currency"], "reason": reason,
            "refunded_at": datetime.utcnow().isoformat() + "Z"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8001"))
    mcp.run(transport="http", host="0.0.0.0", port=port)
