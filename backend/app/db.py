"""MongoDB connection and index creation."""
import os
from motor.motor_asyncio import AsyncIOMotorClient

import asyncio

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _client is None:
        uri = os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URI") or "mongodb://localhost:27017"
        _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=2000)
    elif current_loop and hasattr(_client, "io_loop") and getattr(_client.io_loop, "is_closed", lambda: False)():
        uri = os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URI") or "mongodb://localhost:27017"
        _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=2000)

    return _client


def get_db():
    db_name = os.environ.get("DB_NAME", "proofledger")
    return get_client()[db_name]


async def ensure_indexes():
    db = get_db()
    await db.users.create_index("email", unique=True)
    await db.users.create_index("organization_id")
    for coll in [
        "customers", "products", "orders", "payments", "refunds",
        "settlements", "invoices", "fees", "investigations", "decisions",
        "scenarios", "audit_logs", "data_imports", "integration_connections",
        "evaluation_results",
    ]:
        await db[coll].create_index("organization_id")
    await db.payments.create_index([("organization_id", 1), ("created_at", 1)])
    await db.payments.create_index([("organization_id", 1), ("order_id", 1)])
    await db.payments.create_index([("organization_id", 1), ("settlement_id", 1)])
    await db.refunds.create_index([("organization_id", 1), ("payment_id", 1)])
    await db.orders.create_index([("organization_id", 1), ("customer_id", 1)])
    await db.invoices.create_index([("organization_id", 1), ("customer_id", 1)])
    await db.settlements.create_index([("organization_id", 1), ("status", 1)])
    await db.audit_logs.create_index([("organization_id", 1), ("created_at", -1)])
    await db.login_attempts.create_index("identifier")
    await db.sync_runs.create_index([("organization_id", 1), ("started_at", -1)])
    for coll in ["payments", "refunds", "settlements", "invoices", "orders", "customers", "products"]:
        await db[coll].create_index([("organization_id", 1), ("source", 1)])
        await db[coll].create_index([("organization_id", 1), ("source", 1), ("external_id", 1)])


async def migrate_sources():
    """Stamp legacy records lacking a source as DEMO and default org active_source."""
    db = get_db()
    for coll in ["payments", "refunds", "settlements", "invoices", "orders", "customers", "products"]:
        await db[coll].update_many({"source": {"$exists": False}}, {"$set": {"source": "DEMO"}})
    await db.organizations.update_many({"active_source": {"$exists": False}},
                                       {"$set": {"active_source": "DEMO"}})
