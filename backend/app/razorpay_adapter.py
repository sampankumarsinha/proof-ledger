"""Razorpay TEST integration adapter.

Fetches real Razorpay TEST-mode entities and normalizes them into the EXISTING
ProofLedger models so the SAME FinancialEngine / ReconciliationEngine /
EvidenceEngine operate on them. Records are stamped source="RAZORPAY_TEST" and
external_id=<razorpay id>. Nothing is fabricated. Credentials are read
server-side from env only.
"""
import os
import logging
from datetime import datetime, timezone

from .db import get_db
from .auth import new_id, now_iso

logger = logging.getLogger("proofledger.razorpay")
SOURCE = "RAZORPAY_TEST"
PAGE = 100


def credentials_present() -> bool:
    return bool(os.environ.get("RAZORPAY_KEY_ID") and os.environ.get("RAZORPAY_KEY_SECRET"))


def _client():
    import razorpay
    return razorpay.Client(auth=(os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"]))


def test_connection() -> dict:
    if not credentials_present():
        return {"connected": False, "detail": "No Razorpay credentials configured. Running on DEMO DATA."}
    try:
        c = _client()
        c.payment.all({"count": 1})
        return {"connected": True, "detail": "Connected to Razorpay TEST mode (server-side credentials)."}
    except Exception as e:
        return {"connected": False, "detail": f"Connection failed: {str(e)[:160]}"}


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    if not (secret and signature):
        return False
    try:
        _client().utility.verify_webhook_signature(body.decode(), signature, secret)
        return True
    except Exception:
        return False


def _iso(epoch) -> str:
    if not epoch:
        return now_iso()
    return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()


def _fetch_all(entity_api, options):
    """Paginate a Razorpay collection endpoint with count/skip."""
    items, skip = [], 0
    while True:
        opts = dict(options)
        opts.update({"count": PAGE, "skip": skip})
        resp = entity_api.all(opts)
        batch = resp.get("items", []) if isinstance(resp, dict) else []
        items.extend(batch)
        if len(batch) < PAGE:
            break
        skip += PAGE
        if skip > 5000:  # safety cap
            break
    return items


async def _upsert(coll, org_id, external_id, doc):
    """Idempotent upsert keyed by (organization_id, source, external_id)."""
    db = get_db()
    existing = await db[coll].find_one(
        {"organization_id": org_id, "source": SOURCE, "external_id": external_id}, {"_id": 0, "id": 1})
    doc_id = existing["id"] if existing else new_id()
    doc.update({"organization_id": org_id, "source": SOURCE, "external_id": external_id,
                "id": doc_id, "deleted_at": None})
    await db[coll].update_one(
        {"organization_id": org_id, "source": SOURCE, "external_id": external_id},
        {"$set": doc}, upsert=True)
    return doc_id, (existing is None)


async def _customer_for(org_id, email, contact):
    db = get_db()
    key = email or contact or "unknown@razorpay.test"
    doc_id, _ = await _upsert("customers", org_id, f"rzp_cust::{key}", {
        "name": (email or contact or "Razorpay Customer"), "email": email or "",
        "created_at": now_iso()})
    return doc_id


async def sync(org_id: str, incremental: bool = False) -> dict:
    """Initial or incremental sync. Returns a sync-run summary (also stored)."""
    db = get_db()
    run = {"id": new_id(), "organization_id": org_id, "source": SOURCE,
           "type": "incremental" if incremental else "initial", "started_at": now_iso(),
           "counts": {"orders": 0, "payments": 0, "refunds": 0, "settlements": 0},
           "new": {"orders": 0, "payments": 0, "refunds": 0, "settlements": 0},
           "errors": [], "status": "running"}
    if not credentials_present():
        run.update({"status": "skipped", "finished_at": now_iso(),
                    "errors": ["No Razorpay credentials configured."]})
        await db.sync_runs.insert_one(dict(run)); run.pop("_id", None)
        return run

    options = {}
    if incremental:
        org = await db.organizations.find_one({"id": org_id}, {"_id": 0, "razorpay_last_sync": 1})
        last = (org or {}).get("razorpay_last_sync")
        if last:
            options["from"] = int(datetime.fromisoformat(last).timestamp())

    c = _client()
    order_map, payment_map = {}, {}

    try:
        orders = _fetch_all(c.order, options)
        for o in orders:
            oid, is_new = await _upsert("orders", org_id, o["id"], {
                "customer_id": None, "product_id": None,
                "amount_paise": int(o.get("amount") or 0),
                "status": "paid" if o.get("amount_paid") and o["amount_paid"] >= o.get("amount", 0) else "attempted",
                "created_at": _iso(o.get("created_at"))})
            order_map[o["id"]] = oid
            run["counts"]["orders"] += 1; run["new"]["orders"] += int(is_new)
    except Exception as e:
        run["errors"].append(f"orders: {str(e)[:140]}")

    try:
        payments = _fetch_all(c.payment, options)
        for p in payments:
            status = "captured" if p.get("status") == "captured" else (
                "failed" if p.get("status") == "failed" else "authorized")
            cust_id = await _customer_for(org_id, p.get("email"), p.get("contact"))
            pid, is_new = await _upsert("payments", org_id, p["id"], {
                "order_id": order_map.get(p.get("order_id")), "customer_id": cust_id, "product_id": None,
                "amount_paise": int(p.get("amount") or 0),
                "fee_paise": int(p.get("fee") or 0) - int(p.get("tax") or 0) if p.get("fee") else 0,
                "tax_paise": int(p.get("tax") or 0),
                "status": status, "method": p.get("method", "unknown"),
                "settlement_id": None, "created_at": _iso(p.get("created_at"))})
            payment_map[p["id"]] = pid
            run["counts"]["payments"] += 1; run["new"]["payments"] += int(is_new)
    except Exception as e:
        run["errors"].append(f"payments: {str(e)[:140]}")

    try:
        refunds = _fetch_all(c.refund, options)
        for r in refunds:
            await _upsert("refunds", org_id, r["id"], {
                "payment_id": payment_map.get(r.get("payment_id")), "order_id": None, "customer_id": None,
                "product_id": None, "amount_paise": int(r.get("amount") or 0),
                "status": r.get("status", "processed"),
                "reason": (r.get("notes") or {}).get("reason") if isinstance(r.get("notes"), dict) else "Refund",
                "created_at": _iso(r.get("created_at"))})
            run["counts"]["refunds"] += 1
    except Exception as e:
        run["errors"].append(f"refunds: {str(e)[:140]}")

    try:
        settlements = _fetch_all(c.settlement, options)
        for s in settlements:
            await _upsert("settlements", org_id, s["id"], {
                "amount_paise": int(s.get("amount") or 0), "fee_paise": int(s.get("fees") or 0),
                "tax_paise": int(s.get("tax") or 0),
                "status": "processed" if s.get("status") == "processed" else "pending",
                "utr": s.get("utr"), "settled_at": _iso(s.get("created_at")) if s.get("status") == "processed" else None,
                "expected_at": _iso(s.get("created_at")), "adjustment_paise": 0,
                "created_at": _iso(s.get("created_at"))})
            run["counts"]["settlements"] += 1
    except Exception as e:
        run["errors"].append(f"settlements: {str(e)[:140]}")

    run["status"] = "completed" if not run["errors"] else "completed_with_errors"
    run["finished_at"] = now_iso()
    await db.sync_runs.insert_one(dict(run)); run.pop("_id", None)
    # activate the razorpay source and record sync time
    await db.organizations.update_one({"id": org_id},
                                      {"$set": {"active_source": SOURCE, "razorpay_last_sync": run["finished_at"]}})
    logger.info("razorpay sync org=%s counts=%s errors=%s", org_id, run["counts"], len(run["errors"]))
    return run


async def sync_history(org_id: str, limit: int = 20):
    docs = await get_db().sync_runs.find({"organization_id": org_id}, {"_id": 0}) \
        .sort("started_at", -1).to_list(limit)
    return docs
