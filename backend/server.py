"""ProofLedger API — FastAPI. All routes under /api/v1. Financial truth is
computed deterministically by app.engine; the LLM only explains verified facts.
"""
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import os
import io
import time
import uuid
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from app.db import get_db, ensure_indexes
from app.auth import (hash_password, verify_password, create_access_token,
                      get_current_user, require_role, new_id, now_iso)
from app.seed import seed_admin_and_org
from app.engine import (FinancialEngine, resolve_period, run_tool, TOOL_SPECS,
                        get_record, top_customers, top_products, get_active_source)
from app.reconciliation import reconcile
from app.autopsy import cash_autopsy
from app.scenarios import simulate, counterfactual, baseline
from app.analyst import investigate
from app.evaluation import run_evaluation, BENCHMARK
from app.money import format_inr, rupees
from app import razorpay_adapter as rzp
from app.analytics import baselines as calc_baselines, attention as calc_attention

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("proofledger")

app = FastAPI(title="ProofLedger API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")


# ---------------- observability middleware ----------------
@app.middleware("http")
async def observability(request: Request, call_next):
    rid = str(uuid.uuid4())[:8]
    start = time.time()
    request.state.request_id = rid
    try:
        response = await call_next(request)
    except Exception as e:  # structured error, never leak internals
        logger.exception("rid=%s unhandled error", rid)
        return JSONResponse(status_code=500, content={
            "error": "internal_error", "request_id": rid,
            "message": "Something went wrong while processing your request.",
            "what_you_can_do": "Please retry. Your financial data is unaffected.",
        })
    dur = round((time.time() - start) * 1000, 1)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Response-Time-ms"] = str(dur)
    logger.info("rid=%s %s %s -> %s %sms", rid, request.method, request.url.path,
                response.status_code, dur)
    return response


async def audit(org_id, user, action, payload=None):
    try:
        await get_db().audit_logs.insert_one({
            "id": new_id(), "organization_id": org_id, "user_id": user.get("id"),
            "user_email": user.get("email"), "action": action, "payload": payload or {},
            "created_at": now_iso(),
        })
    except Exception:
        logger.warning("audit write failed")


api = APIRouter(prefix="/api/v1")


# ===================== health =====================
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "proofledger", "time": now_iso()}


@app.get("/api/ready")
async def ready():
    checks = {}
    try:
        await get_db().command("ping")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = "down"
    checks["ai"] = "configured" if os.environ.get("OPENAI_API_KEY") else "demo_fallback"
    checks["integration"] = "razorpay_test" if os.environ.get("RAZORPAY_KEY_ID") else "demo_data"
    ok = checks["database"] == "ok"
    return JSONResponse(status_code=200 if ok else 503,
                        content={"ready": ok, "checks": checks, "time": now_iso()})


# ===================== auth =====================
class LoginBody(BaseModel):
    email: EmailStr
    password: str


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    organization_name: str


@api.post("/auth/register")
async def register(body: RegisterBody):
    db = get_db()
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    org_id = new_id()
    await db.organizations.insert_one({"id": org_id, "name": body.organization_name, "created_at": now_iso()})
    uid = new_id()
    await db.users.insert_one({
        "id": uid, "organization_id": org_id, "email": email,
        "password_hash": hash_password(body.password), "name": body.name,
        "role": "OWNER", "created_at": now_iso(),
    })
    token = create_access_token(uid, email, org_id, "OWNER")
    return {"token": token, "user": {"id": uid, "email": email, "name": body.name,
                                     "role": "OWNER", "organization_id": org_id}}


@api.post("/auth/login")
async def login(body: LoginBody, request: Request):
    db = get_db()
    email = body.email.lower()
    xff = request.headers.get("X-Forwarded-For", "")
    client_ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")
    ident = f"{client_ip}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": ident})
    if attempt and attempt.get("count", 0) >= 5:
        locked_until = attempt.get("locked_until")
        if locked_until and locked_until > now_iso():
            raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        from datetime import timedelta
        await db.login_attempts.update_one(
            {"identifier": ident},
            {"$inc": {"count": 1}, "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}},
            upsert=True)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    await db.login_attempts.delete_one({"identifier": ident})
    token = create_access_token(user["id"], email, user["organization_id"], user["role"])
    return {"token": token, "user": {"id": user["id"], "email": email, "name": user["name"],
                                     "role": user["role"], "organization_id": user["organization_id"]}}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# ===================== dashboard / control tower =====================
@api.get("/dashboard")
async def dashboard(period: str = "current", user: dict = Depends(get_current_user)):
    org = user["organization_id"]
    src = await get_active_source(org)
    eng = FinancialEngine(org, src)
    cur = resolve_period(period)
    prior = resolve_period("prior")

    async def kpi(metric_fn_name, current_only=False):
        cmp = await eng.compare_periods(metric_fn_name, cur, prior)
        return cmp

    metrics = {}
    for m in ["gross_revenue", "net_revenue", "cash_received", "refunds", "fee_total",
              "successful_payments", "failed_payments", "average_payment_value"]:
        metrics[m] = await eng.compare_periods(m, cur, prior)
    # point-in-time metrics
    metrics["pending_settlements"] = {"current": await eng.pending_settlements(cur)}
    metrics["receivables_outstanding"] = {"current": await eng.receivables_outstanding()}
    metrics["overdue_receivables"] = {"current": await eng.overdue_receivables()}
    metrics["unreconciled_amount"] = {"current": await eng.unreconciled_amount()}
    metrics["refund_rate"] = {"current": await eng.refund_rate(cur), "prior": await eng.refund_rate(prior)}

    # attention items derived deterministically
    attention = []
    if metrics["pending_settlements"]["current"]["value"] > 0:
        attention.append({"severity": "high", "title": "Pending settlements",
                          "value": metrics["pending_settlements"]["current"]["value_display"],
                          "detail": "Captured funds not yet settled to your bank."})
    if metrics["overdue_receivables"]["current"]["value"] > 0:
        attention.append({"severity": "medium", "title": "Overdue receivables",
                          "value": metrics["overdue_receivables"]["current"]["value_display"],
                          "detail": "Invoices past their due date."})
    if metrics["unreconciled_amount"]["current"]["value"] > 0:
        attention.append({"severity": "high", "title": "Unreconciled payments",
                          "value": metrics["unreconciled_amount"]["current"]["value_display"],
                          "detail": "Captured payments with no matching settlement."})
    rr = metrics["refund_rate"]["current"]["value"]
    rrp = metrics["refund_rate"]["prior"]["value"]
    if rr > rrp:
        attention.append({"severity": "medium", "title": "Refund rate rising",
                          "value": f"{rr}% vs {rrp}%", "detail": "Refund rate increased vs prior period."})

    # health score (deterministic composite)
    health_score = 100
    if metrics["cash_received"]["change_pct"] < 0:
        health_score -= min(30, abs(metrics["cash_received"]["change_pct"]))
    if rr > 5:
        health_score -= min(20, rr)
    health_score = max(0, round(health_score))

    return {"period": cur, "metrics": metrics, "attention": attention,
            "health_score": health_score, "source": src,
            "environment": "RAZORPAY_TEST" if src == "RAZORPAY_TEST" else "DEMO_DATA"}


@api.get("/dashboard/trend")
async def dashboard_trend(metric: str = "cash_received", user: dict = Depends(get_current_user)):
    """Daily trend for the last 30 days for a given metric (payments/refunds)."""
    from datetime import timedelta
    org = user["organization_id"]
    src = await get_active_source(org)
    db = get_db()
    now = datetime.now(timezone.utc)
    days = []
    for i in range(29, -1, -1):
        day = (now - timedelta(days=i))
        start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        q = {"organization_id": org, "deleted_at": None, "source": src,
             "created_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}
        if metric == "refunds":
            docs = await db.refunds.find(q, {"amount_paise": 1}).to_list(100000)
        else:
            q["status"] = "captured"
            docs = await db.payments.find(q, {"amount_paise": 1}).to_list(100000)
        total = sum(d["amount_paise"] for d in docs)
        days.append({"date": start.strftime("%d %b"), "value": rupees(total), "value_paise": total})
    return {"metric": metric, "series": days}


# ===================== AI analyst / ask =====================
class AskBody(BaseModel):
    question: str


class DecisionBody(BaseModel):
    decision: str
    note: str = ""


class SimulateBody(BaseModel):
    refund_change_pct: float = 0
    settlement_clear_pct: float = 0
    payment_volume_change_pct: float = 0
    avg_payment_change_pct: float = 0
    receivables_collect_pct: float = 0
    fee_change_pct: float = 0


@api.get("/ai/suggestions")
async def suggestions(user: dict = Depends(get_current_user)):
    return {"suggestions": [
        "Why did cash decrease this month?", "Where is my cash stuck?",
        "Which products are driving refunds?", "Which customers owe me money?",
        "Which settlements are delayed?", "Compare this period with the prior period.",
        "Show me unreconciled payments.", "Why did refunds increase?",
    ], "tools": TOOL_SPECS}


@api.post("/ai/ask")
async def ask(body: AskBody, user: dict = Depends(get_current_user)):
    org = user["organization_id"]
    src = await get_active_source(org)
    result = await investigate(org, body.question, src)
    await audit(org, user, "ai_ask", {"question": body.question, "intent": result["intent"],
                                       "tools": [t["tool"] for t in result["tool_log"]],
                                       "confidence": result["confidence"]["band"],
                                       "explainer": result["explainer"]})
    return result


# ===================== autopsy =====================
@api.get("/autopsy/cash")
async def autopsy_cash(user: dict = Depends(get_current_user)):
    org = user["organization_id"]
    return await cash_autopsy(org, await get_active_source(org))


# ===================== evidence / claims =====================
@api.get("/evidence/metric/{metric}")
async def evidence_metric(metric: str, period: str = "current", user: dict = Depends(get_current_user)):
    org = user["organization_id"]
    src = await get_active_source(org)
    eng = FinancialEngine(org, src)
    p = resolve_period(period)
    prior = resolve_period("prior")
    fn = getattr(eng, metric, None)
    if not fn:
        raise HTTPException(status_code=404, detail=f"Unknown metric: {metric}")
    try:
        fact = await fn(p)
        prior_fact = await fn(prior)
    except TypeError:
        fact = await fn()
        prior_fact = None
    # fetch sample source records
    coll_map = {"gross_revenue": "payments", "net_revenue": "payments", "fee_total": "payments",
                "refunds": "refunds", "cash_received": "settlements", "pending_settlements": "settlements",
                "receivables_outstanding": "invoices", "overdue_receivables": "invoices",
                "unreconciled_amount": "payments", "failed_payments": "payments"}
    coll = coll_map.get(metric, "payments")
    all_ids = fact.get("source_records", [])
    ids = all_ids[:25]
    records = []
    if ids:
        records = await get_db()[coll].find({"organization_id": org, "id": {"$in": ids}}, {"_id": 0}).to_list(50)
        for r in records:
            for k in list(r.keys()):
                if k.endswith("_paise") and isinstance(r[k], int):
                    r[k.replace("_paise", "_display")] = format_inr(r[k])
    source_ids = [r.get("external_id") for r in records if r.get("external_id")]
    delta = None
    if prior_fact and isinstance(fact.get("value"), int) and isinstance(prior_fact.get("value"), int):
        d = fact["value"] - prior_fact["value"]
        delta = {"value": d, "display": format_inr(d) if isinstance(d, int) else d,
                 "change_pct": round(d / prior_fact["value"] * 100, 2) if prior_fact["value"] else 0}
    return {"fact": fact, "prior_fact": prior_fact, "delta": delta, "records": records,
            "record_collection": coll, "source": src,
            "evidence_coverage": round(len(records) / len(all_ids), 2) if all_ids else 1.0,
            "source_transaction_count": len(all_ids), "source_ids": source_ids[:25]}


@api.get("/evidence/graph/{customer_id}")
async def evidence_graph(customer_id: str, user: dict = Depends(get_current_user)):
    """Relationship graph: customer -> orders -> payments -> settlements/refunds."""
    org = user["organization_id"]
    src = await get_active_source(org)
    db = get_db()
    cust = await db.customers.find_one({"organization_id": org, "id": customer_id}, {"_id": 0})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    nodes = [{"id": customer_id, "label": cust["name"], "type": "customer"}]
    links = []
    payments = await db.payments.find({"organization_id": org, "customer_id": customer_id, "source": src}, {"_id": 0}).to_list(200)
    order_ids = list({p["order_id"] for p in payments if p.get("order_id")})
    for oid in order_ids:
        o = await db.orders.find_one({"id": oid}, {"_id": 0})
        if o:
            nodes.append({"id": oid, "label": o["external_id"], "type": "order",
                          "amount": format_inr(o["amount_paise"])})
            links.append({"source": customer_id, "target": oid})
    for p in payments:
        nodes.append({"id": p["id"], "label": p["external_id"], "type": "payment",
                      "amount": format_inr(p["amount_paise"]), "status": p["status"]})
        links.append({"source": p["order_id"], "target": p["id"]})
        if p.get("settlement_id"):
            s = await db.settlements.find_one({"id": p["settlement_id"]}, {"_id": 0})
            if s and not any(n["id"] == s["id"] for n in nodes):
                nodes.append({"id": s["id"], "label": s["external_id"], "type": "settlement",
                              "amount": format_inr(s["amount_paise"]), "status": s["status"]})
            links.append({"source": p["id"], "target": p["settlement_id"]})
        refs = await db.refunds.find({"payment_id": p["id"]}, {"_id": 0}).to_list(20)
        for r in refs:
            nodes.append({"id": r["id"], "label": r["external_id"], "type": "refund",
                          "amount": format_inr(r["amount_paise"])})
            links.append({"source": p["id"], "target": r["id"]})
    return {"customer": cust, "nodes": nodes, "links": links}


# ===================== data explorer =====================
def _paginate(items, page, size):
    return items[(page - 1) * size: page * size]


@api.get("/data/{collection}")
async def list_records(collection: str, page: int = 1, size: int = 25, q: str = None,
                       user: dict = Depends(get_current_user)):
    allowed = {"payments", "refunds", "settlements", "invoices", "orders", "customers", "products"}
    if collection not in allowed:
        raise HTTPException(status_code=404, detail="Unknown collection")
    org = user["organization_id"]
    src = await get_active_source(org)
    db = get_db()
    query = {"organization_id": org, "deleted_at": None, "source": src}
    if q:
        query["external_id"] = {"$regex": q, "$options": "i"}
    total = await db[collection].count_documents(query)
    docs = await db[collection].find(query, {"_id": 0}).sort("created_at", -1) \
        .skip((page - 1) * size).limit(size).to_list(size)
    # decorate amounts
    for d in docs:
        for k in list(d.keys()):
            if k.endswith("_paise") and isinstance(d[k], int):
                d[k.replace("_paise", "_display")] = format_inr(d[k])
    return {"collection": collection, "total": total, "page": page, "size": size, "records": docs}


@api.get("/record/{collection}/{record_id}")
async def get_single(collection: str, record_id: str, user: dict = Depends(get_current_user)):
    doc = await get_record(user["organization_id"], collection, record_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Record not found")
    for k in list(doc.keys()):
        if k.endswith("_paise") and isinstance(doc[k], int):
            doc[k.replace("_paise", "_display")] = format_inr(doc[k])
    return doc


# ===================== reconciliation =====================
@api.get("/reconciliation")
async def reconciliation(user: dict = Depends(get_current_user)):
    org = user["organization_id"]
    return await reconcile(org, source=await get_active_source(org))


# ===================== settlements / receivables / refunds intelligence =====================
@api.get("/settlements/intelligence")
async def settlement_intel(user: dict = Depends(get_current_user)):
    org = user["organization_id"]
    src = await get_active_source(org)
    db = get_db()
    now = datetime.now(timezone.utc)
    settlements = await db.settlements.find({"organization_id": org, "deleted_at": None, "source": src}, {"_id": 0}).to_list(100000)
    pending, processed = [], []
    aging = {"0-2d": 0, "3-5d": 0, "6-10d": 0, "10+d": 0}
    for s in settlements:
        s["amount_display"] = format_inr(s["amount_paise"])
        s["fee_display"] = format_inr(s.get("fee_paise", 0) + s.get("tax_paise", 0))
        if s["status"] == "pending":
            created = datetime.fromisoformat(s["created_at"])
            days = (now - created).days
            s["age_days"] = days
            if days <= 2: aging["0-2d"] += s["amount_paise"]
            elif days <= 5: aging["3-5d"] += s["amount_paise"]
            elif days <= 10: aging["6-10d"] += s["amount_paise"]
            else: aging["10+d"] += s["amount_paise"]
            pending.append(s)
        else:
            processed.append(s)
    pending.sort(key=lambda x: x.get("age_days", 0), reverse=True)
    return {"pending": pending[:100], "processed_count": len(processed),
            "pending_total": format_inr(sum(s["amount_paise"] for s in pending)),
            "aging": {k: format_inr(v) for k, v in aging.items()},
            "aging_raw": aging}


@api.get("/receivables/intelligence")
async def receivables_intel(user: dict = Depends(get_current_user)):
    org = user["organization_id"]
    src = await get_active_source(org)
    db = get_db()
    eng = FinancialEngine(org, src)
    aging = await eng.receivables_aging()
    now = datetime.now(timezone.utc)
    invoices = await db.invoices.find({"organization_id": org, "status": {"$ne": "paid"}, "deleted_at": None, "source": src},
                                      {"_id": 0}).to_list(100000)
    rows = []
    for inv in invoices:
        cust = await db.customers.find_one({"id": inv["customer_id"]}, {"_id": 0, "name": 1})
        due = datetime.fromisoformat(inv["due_date"])
        age = (now - due).days
        outstanding = inv["amount_paise"] - inv.get("paid_amount_paise", 0)
        # transparent deterministic risk rule
        if age > 60:
            risk = "HIGH"
        elif age > 30:
            risk = "MEDIUM"
        elif age > 0:
            risk = "LOW"
        else:
            risk = "CURRENT"
        rows.append({"invoice_id": inv["id"], "external_id": inv["external_id"],
                     "customer": cust["name"] if cust else "Unknown", "customer_id": inv["customer_id"],
                     "amount": outstanding, "amount_display": format_inr(outstanding),
                     "due_date": inv["due_date"], "age_days": age, "risk": risk})
    rows.sort(key=lambda r: r["age_days"], reverse=True)
    return {"aging": aging, "rows": rows[:200],
            "risk_rule": "HIGH: >60 days overdue, MEDIUM: 31-60, LOW: 1-30, CURRENT: not yet due"}


@api.get("/refunds/intelligence")
async def refunds_intel(user: dict = Depends(get_current_user)):
    org = user["organization_id"]
    src = await get_active_source(org)
    eng = FinancialEngine(org, src)
    cur = resolve_period("current")
    prior = resolve_period("prior")
    rate = await eng.refund_rate(cur)
    cmp = await eng.compare_periods("refunds", cur, prior)
    products = await top_products(org, cur, source=src)
    db = get_db()
    # refund reasons breakdown
    pipeline = [{"$match": {"organization_id": org, "deleted_at": None, "source": src,
                            "created_at": {"$gte": cur["from"], "$lte": cur["to"]}}},
                {"$group": {"_id": "$reason", "total": {"$sum": "$amount_paise"}, "count": {"$sum": 1}}},
                {"$sort": {"total": -1}}]
    reasons = await db.refunds.aggregate(pipeline).to_list(50)
    reasons = [{"reason": r["_id"], "total": r["total"], "total_display": format_inr(r["total"]),
                "count": r["count"]} for r in reasons]
    return {"refund_rate": rate, "change": cmp, "by_product": products["rows"], "by_reason": reasons}


# ===================== investigations =====================
class InvestigationBody(BaseModel):
    title: str
    question: str


@api.post("/investigations")
async def create_investigation(body: InvestigationBody, user: dict = Depends(require_role("ANALYST"))):
    org = user["organization_id"]
    result = await investigate(org, body.question, await get_active_source(org))
    inv = {
        "id": new_id(), "organization_id": org, "title": body.title, "question": body.question,
        "status": "OPEN", "created_by": user["email"], "created_at": now_iso(),
        "findings": result["findings"], "summary": result["summary"],
        "confidence": result["confidence"], "facts": result["facts"],
        "recommendations": result["recommendations"], "tool_log": result["tool_log"],
        "autopsy": result["autopsy"], "decision": None,
    }
    await get_db().investigations.insert_one(dict(inv))
    await audit(org, user, "investigation_create", {"title": body.title})
    inv.pop("_id", None)
    return inv


@api.get("/investigations")
async def list_investigations(user: dict = Depends(get_current_user)):
    docs = await get_db().investigations.find({"organization_id": user["organization_id"]}, {"_id": 0}) \
        .sort("created_at", -1).to_list(200)
    return {"investigations": docs}


@api.get("/investigations/{inv_id}")
async def get_investigation(inv_id: str, user: dict = Depends(get_current_user)):
    doc = await get_db().investigations.find_one({"organization_id": user["organization_id"], "id": inv_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return doc


@api.post("/investigations/{inv_id}/decision")
async def investigation_decision(inv_id: str, body: DecisionBody, user: dict = Depends(require_role("ANALYST"))):
    decision = body.decision
    if decision not in {"APPROVE", "REVIEW", "DISMISS"}:
        raise HTTPException(status_code=400, detail="decision must be APPROVE, REVIEW or DISMISS")
    await get_db().investigations.update_one(
        {"organization_id": user["organization_id"], "id": inv_id},
        {"$set": {"decision": {"decision": decision, "by": user["email"], "note": body.note,
                               "at": now_iso()}, "status": "CLOSED" if decision != "REVIEW" else "OPEN"}})
    await audit(user["organization_id"], user, "investigation_decision", {"inv_id": inv_id, "decision": decision})
    return {"ok": True, "decision": decision}


@api.get("/investigations/{inv_id}/report")
async def investigation_report(inv_id: str, fmt: str = "json", user: dict = Depends(get_current_user)):
    doc = await get_db().investigations.find_one({"organization_id": user["organization_id"], "id": inv_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Investigation not found")
    report = {
        "title": doc["title"], "question": doc["question"], "generated_at": now_iso(),
        "executive_summary": doc.get("summary"), "findings": doc.get("findings"),
        "recommendations": doc.get("recommendations"), "confidence": doc.get("confidence"),
        "facts": doc.get("facts"), "decision": doc.get("decision"),
        "disclaimer": "Facts and derived metrics are deterministic. Inferences and recommendations are advisory.",
    }
    if fmt == "csv":
        buf = io.StringIO()
        buf.write("type,statement\n")
        for f in doc.get("findings", []):
            buf.write(f"\"{f.get('type')}\",\"{f.get('statement')}\"\n")
        return StreamingResponse(io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
                                 headers={"Content-Disposition": f"attachment; filename=investigation_{inv_id}.csv"})
    return report


@api.get("/investigations/{inv_id}/report.pdf")
async def investigation_report_pdf(inv_id: str, user: dict = Depends(get_current_user)):
    doc = await get_db().investigations.find_one({"organization_id": user["organization_id"], "id": inv_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Investigation not found")
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0A1128")
    h = ParagraphStyle("h", parent=styles["Title"], textColor=navy, fontSize=20, spaceAfter=4)
    sub = ParagraphStyle("sub", parent=styles["Normal"], textColor=colors.HexColor("#475569"), fontSize=9)
    sec = ParagraphStyle("sec", parent=styles["Heading2"], textColor=navy, fontSize=12, spaceBefore=12, spaceAfter=4)
    body = styles["Normal"]
    el = [Paragraph("ProofLedger — Investigation Report", h),
          Paragraph(f"Generated {now_iso()} · Source of truth: deterministic financial engine", sub),
          Spacer(1, 8)]
    el.append(Paragraph("Question", sec)); el.append(Paragraph(doc.get("question", ""), body))
    el.append(Paragraph("Executive summary", sec)); el.append(Paragraph(doc.get("summary", ""), body))
    conf = doc.get("confidence") or {}
    el.append(Paragraph("Confidence", sec))
    el.append(Paragraph(f"{conf.get('band','—')} ({int((conf.get('score') or 0)*100)}%) — {conf.get('explanation','')}", body))
    el.append(Paragraph("Verified facts & findings", sec))
    rows = [["Type", "Statement"]] + [[f.get("type", ""), f.get("statement", "")] for f in doc.get("findings", [])]
    t = Table(rows, colWidths=[35 * mm, 130 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")])]))
    el.append(t)
    if doc.get("recommendations"):
        el.append(Paragraph("Recommendations (advisory)", sec))
        for r in doc["recommendations"]:
            el.append(Paragraph(f"• {r}", body))
    el.append(Spacer(1, 10))
    el.append(Paragraph("Facts and derived metrics are deterministic and traceable to source transactions. "
                        "Inferences and recommendations are advisory. No numbers were generated by an LLM.", sub))
    pdf.build(el)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="investigation_{inv_id}.pdf"'})


# ===================== scenarios / counterfactuals =====================
@api.post("/scenarios/simulate")
async def scenario_simulate(body: SimulateBody, user: dict = Depends(get_current_user)):
    org = user["organization_id"]
    return await simulate(org, body.model_dump(), await get_active_source(org))


@api.get("/scenarios/counterfactual/{kind}")
async def scenario_counterfactual(kind: str, user: dict = Depends(get_current_user)):
    org = user["organization_id"]
    return await counterfactual(org, kind, await get_active_source(org))


@api.get("/scenarios/baseline")
async def scenario_baseline(user: dict = Depends(get_current_user)):
    org = user["organization_id"]
    b = await baseline(org, await get_active_source(org))
    return {k: {"value": v, "display": format_inr(v)} for k, v in b.items()}


# ===================== decisions =====================
@api.get("/decisions")
async def decisions_center(user: dict = Depends(get_current_user)):
    """Evidence-backed recommendations derived from deterministic signals."""
    org = user["organization_id"]
    eng = FinancialEngine(org, await get_active_source(org))
    cur = resolve_period("current")
    db = get_db()
    items = []
    pending = await eng.pending_settlements(cur)
    if pending["value"] > 0:
        items.append({"id": "pending_settlement", "issue": f"{pending['value_display']} pending settlement",
                      "evidence": "HIGH", "evidence_records": pending["source_count"],
                      "suggested_action": "Review settlement schedule with payment provider",
                      "financial_impact": pending["value_display"]})
    overdue = await eng.overdue_receivables()
    if overdue["value"] > 0:
        items.append({"id": "overdue_recv", "issue": f"{overdue['value_display']} overdue receivables",
                      "evidence": "HIGH", "evidence_records": overdue["source_count"],
                      "suggested_action": "Trigger collection follow-up on overdue invoices",
                      "financial_impact": overdue["value_display"]})
    unrec = await eng.unreconciled_amount()
    if unrec["value"] > 0:
        items.append({"id": "unreconciled", "issue": f"{unrec['value_display']} unreconciled payments",
                      "evidence": "HIGH", "evidence_records": unrec["source_count"],
                      "suggested_action": "Investigate payments with no matching settlement",
                      "financial_impact": unrec["value_display"]})
    # attach any saved decisions
    saved = {d["item_id"]: d for d in await db.decisions.find({"organization_id": org}, {"_id": 0}).to_list(200)}
    for it in items:
        it["decision"] = saved.get(it["id"], {}).get("decision")
    return {"items": items, "note": "No autonomous movement of money. All actions require human approval."}


@api.post("/decisions/{item_id}")
async def make_decision(item_id: str, body: DecisionBody, user: dict = Depends(require_role("ANALYST"))):
    decision = body.decision
    if decision not in {"APPROVE", "REVIEW", "DISMISS"}:
        raise HTTPException(status_code=400, detail="Invalid decision")
    await get_db().decisions.update_one(
        {"organization_id": user["organization_id"], "item_id": item_id},
        {"$set": {"item_id": item_id, "organization_id": user["organization_id"],
                  "decision": decision, "by": user["email"], "at": now_iso()}}, upsert=True)
    await audit(user["organization_id"], user, "decision", {"item": item_id, "decision": decision})
    return {"ok": True}


# ===================== evaluation lab =====================
@api.post("/evaluations/run")
async def eval_run(user: dict = Depends(require_role("ANALYST"))):
    org = user["organization_id"]
    result = await run_evaluation(org, await get_active_source(org))
    await audit(org, user, "evaluation_run", {"score": result["score_pct"]})
    return result


@api.get("/evaluations/latest")
async def eval_latest(user: dict = Depends(get_current_user)):
    doc = await get_db().evaluation_results.find_one(
        {"organization_id": user["organization_id"]}, {"_id": 0}, sort=[("run_at", -1)])
    return doc or {"message": "No evaluation runs yet.", "benchmark_size": len(BENCHMARK)}


# ===================== audit =====================
@api.get("/audit")
async def audit_list(page: int = 1, size: int = 50, user: dict = Depends(get_current_user)):
    db = get_db()
    org = user["organization_id"]
    total = await db.audit_logs.count_documents({"organization_id": org})
    docs = await db.audit_logs.find({"organization_id": org}, {"_id": 0}) \
        .sort("created_at", -1).skip((page - 1) * size).limit(size).to_list(size)
    return {"total": total, "page": page, "logs": docs}


# ===================== integrations (Razorpay) =====================
@api.get("/integrations/status")
async def integrations_status(user: dict = Depends(get_current_user)):
    org = user["organization_id"]
    active = await get_active_source(org)
    conn = rzp.test_connection()
    last = await get_db().sync_runs.find_one({"organization_id": org}, {"_id": 0}, sort=[("started_at", -1)])
    return {"mode": active, "active_source": active,
            "credentials_present": rzp.credentials_present(),
            "connected": conn["connected"], "detail": conn["detail"],
            "webhook_secret_present": bool(os.environ.get("RAZORPAY_WEBHOOK_SECRET")),
            "entities": ["orders", "payments", "refunds", "settlements", "customers"],
            "last_sync": last}


@api.post("/integrations/razorpay/test")
async def razorpay_test(user: dict = Depends(require_role("ANALYST"))):
    return rzp.test_connection()


@api.post("/integrations/razorpay/sync")
async def razorpay_sync(incremental: bool = False, user: dict = Depends(require_role("ANALYST"))):
    org = user["organization_id"]
    if not rzp.credentials_present():
        raise HTTPException(status_code=400,
                            detail="No Razorpay credentials configured on the server. Add RAZORPAY_KEY_ID/SECRET to backend/.env.")
    run = await rzp.sync(org, incremental=incremental)
    await audit(org, user, "razorpay_sync", {"type": run["type"], "counts": run["counts"], "errors": len(run["errors"])})
    return run


@api.get("/integrations/razorpay/history")
async def razorpay_history(user: dict = Depends(get_current_user)):
    return {"runs": await rzp.sync_history(user["organization_id"])}


@api.post("/integrations/source")
async def set_source(body: dict, user: dict = Depends(require_role("ANALYST"))):
    src = body.get("source")
    if src not in {"DEMO", "RAZORPAY_TEST"}:
        raise HTTPException(status_code=400, detail="source must be DEMO or RAZORPAY_TEST")
    if src == "RAZORPAY_TEST" and not rzp.credentials_present():
        raise HTTPException(status_code=400, detail="Cannot switch to RAZORPAY_TEST without server credentials.")
    await get_db().organizations.update_one({"id": user["organization_id"]}, {"$set": {"active_source": src}})
    await audit(user["organization_id"], user, "source_switch", {"source": src})
    return {"ok": True, "active_source": src}


@api.post("/integrations/webhook")
async def razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    verified = rzp.verify_webhook_signature(body, signature)
    logger.info("razorpay webhook verified=%s", verified)
    return {"received": True, "verified": verified}


# ===================== analytics: baselines + attention =====================
@api.get("/analytics/baselines")
async def analytics_baselines(user: dict = Depends(get_current_user)):
    org = user["organization_id"]
    return await calc_baselines(org, await get_active_source(org))


@api.get("/analytics/attention")
async def analytics_attention(user: dict = Depends(get_current_user)):
    org = user["organization_id"]
    return await calc_attention(org, await get_active_source(org))


# ===================== imports =====================
@api.post("/imports/csv")
async def import_csv(entity: str = "payments", file: UploadFile = File(...),
                     user: dict = Depends(require_role("ANALYST"))):
    import pandas as pd
    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not parse CSV. Check the file format.")
    required = {"payments": ["external_id", "amount", "status"],
                "invoices": ["external_id", "amount", "due_date"]}.get(entity, ["external_id", "amount"])
    imported = rejected = duplicates = 0
    warnings = []
    org = user["organization_id"]
    db = get_db()
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {missing}")
    for _, row in df.iterrows():
        try:
            ext = str(row["external_id"])
            amt = int(round(float(row["amount"]) * 100))
            if amt <= 0:
                rejected += 1; warnings.append(f"{ext}: non-positive amount"); continue
            exists = await db[entity].find_one({"organization_id": org, "external_id": ext, "source": "DEMO"})
            if exists:
                duplicates += 1; continue
            doc = {"id": new_id(), "organization_id": org, "external_id": ext, "source": "DEMO",
                   "amount_paise": amt, "created_at": now_iso(), "deleted_at": None,
                   "status": str(row.get("status", "captured")), "imported": True}
            if entity == "invoices":
                doc["due_date"] = str(row["due_date"]); doc["paid_amount_paise"] = 0
                doc["customer_id"] = None
            await db[entity].insert_one(doc)
            imported += 1
        except Exception as e:
            rejected += 1; warnings.append(str(e)[:80])
    summary = {"entity": entity, "records_imported": imported, "records_rejected": rejected,
               "duplicates": duplicates, "warnings": warnings[:20]}
    await db.data_imports.insert_one({"id": new_id(), "organization_id": org, "created_at": now_iso(),
                                      "by": user["email"], **summary})
    await audit(org, user, "csv_import", summary)
    return summary


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time-ms"],
)


@app.on_event("startup")
async def startup():
    from app.db import migrate_sources
    await ensure_indexes()
    await seed_admin_and_org()
    await migrate_sources()
    logger.info("ProofLedger startup complete. AI=%s Integration=%s",
                "on" if os.environ.get("OPENAI_API_KEY") else "demo",
                "razorpay_test" if os.environ.get("RAZORPAY_KEY_ID") else "demo")


@app.on_event("shutdown")
async def shutdown():
    from app.db import get_client
    get_client().close()
