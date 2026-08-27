"""Deterministic demo-data seeder that builds INTERNALLY CONSISTENT financial
stories. Amounts are integer paise. Every payment ties to an order; captured
payments group into settlements (some pending); refunds attach to payments;
invoices drive receivables. Specific exceptions are injected so the
reconciliation and autopsy engines detect them deterministically.
"""
import random
from datetime import datetime, timezone, timedelta

from .db import get_db
from .auth import hash_password, new_id

FEE_BPS = 200          # 2.00% processing fee
GST_BPS = 1800         # 18% GST charged on the fee

CUSTOMER_NAMES = [
    "Meridian Retail", "Nova Textiles", "Aster Foods", "Kavery Electronics",
    "Blue Orchid Cafe", "Sunrise Pharma", "Peak Gear", "Lotus Interiors",
    "Vertex Logistics", "Harbour Books", "Indus Apparel", "Zenith Motors",
    "Coral Cosmetics", "Ironwood Furniture", "Saffron Kitchens", "Trailhead Sports",
    "Lumen Lighting", "Cedar Stationery", "Pallavi Jewels", "Monsoon Travels",
]
PRODUCT_NAMES = [
    ("Standard Plan", 299900), ("Pro Plan", 599900), ("Enterprise Plan", 1499900),
    ("Hardware Kit", 899900), ("Onboarding Service", 1999900), ("Add-on Seats", 149900),
    ("Analytics Module", 799900), ("Priority Support", 249900), ("Data Export Pack", 99900),
    ("Custom Integration", 3499900), ("Training Session", 449900), ("Storage Upgrade", 199900),
]
REFUND_REASONS = [
    "Customer requested cancellation", "Duplicate charge", "Product defect",
    "Service not delivered", "Downgrade / proration", "Fraudulent dispute",
]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


async def is_seeded(org_id: str) -> bool:
    db = get_db()
    return (await db.payments.count_documents({"organization_id": org_id})) > 0


async def seed_organization(org_id: str):
    """Idempotent per organization."""
    db = get_db()
    if await is_seeded(org_id):
        return

    rng = random.Random(42)
    now = datetime.now(timezone.utc)
    # Two 30-day windows.
    cur_start = now - timedelta(days=30)
    prior_start = now - timedelta(days=60)
    prior_end = cur_start

    # ---- Customers & products ----
    customers, products = [], []
    for i, name in enumerate(CUSTOMER_NAMES):
        customers.append({
            "id": new_id(), "organization_id": org_id, "external_id": f"cust_{i+1:03d}",
            "name": name, "email": f"ap@{name.lower().split()[0]}.example.com",
            "created_at": _iso(prior_start - timedelta(days=rng.randint(30, 300))),
            "deleted_at": None,
        })
    for i, (name, price) in enumerate(PRODUCT_NAMES):
        products.append({
            "id": new_id(), "organization_id": org_id, "external_id": f"prod_{i+1:03d}",
            "name": name, "price_paise": price,
            "created_at": _iso(prior_start - timedelta(days=200)), "deleted_at": None,
        })

    orders, payments, refunds, settlements, invoices, fees = [], [], [], [], [], []

    def make_payment(cust, prod, created, status, settlement=None, amount=None):
        amt = amount if amount is not None else prod["price_paise"]
        order = {
            "id": new_id(), "organization_id": org_id, "external_id": f"order_{len(orders)+1:05d}",
            "customer_id": cust["id"], "product_id": prod["id"], "amount_paise": amt,
            "status": "paid" if status == "captured" else "attempted",
            "created_at": _iso(created), "deleted_at": None,
        }
        orders.append(order)
        fee = amt * FEE_BPS // 10000
        tax = fee * GST_BPS // 10000
        pay = {
            "id": new_id(), "organization_id": org_id, "external_id": f"pay_{len(payments)+1:05d}",
            "order_id": order["id"], "customer_id": cust["id"], "product_id": prod["id"],
            "amount_paise": amt, "fee_paise": fee if status == "captured" else 0,
            "tax_paise": tax if status == "captured" else 0,
            "status": status, "method": rng.choice(["upi", "card", "netbanking", "wallet"]),
            "settlement_id": settlement["id"] if settlement else None,
            "created_at": _iso(created), "deleted_at": None,
        }
        payments.append(pay)
        return order, pay

    def make_settlement(created, status, settled_at=None, expected_at=None):
        s = {
            "id": new_id(), "organization_id": org_id, "external_id": f"setl_{len(settlements)+1:05d}",
            "amount_paise": 0, "fee_paise": 0, "tax_paise": 0, "status": status,
            "utr": f"UTR{rng.randint(10**9, 10**10-1)}" if status == "processed" else None,
            "created_at": _iso(created),
            "settled_at": _iso(settled_at) if settled_at else None,
            "expected_at": _iso(expected_at) if expected_at else None,
            "deleted_at": None, "adjustment_paise": 0,
        }
        settlements.append(s)
        return s

    def finalize_settlement(s, member_payments, shortfall=0):
        net = sum(p["amount_paise"] - p["fee_paise"] - p["tax_paise"] for p in member_payments)
        s["fee_paise"] = sum(p["fee_paise"] for p in member_payments)
        s["tax_paise"] = sum(p["tax_paise"] for p in member_payments)
        s["amount_paise"] = net - shortfall
        s["adjustment_paise"] = -shortfall

    def gen_period(start, end, n_success, n_failed, pending_ratio, settle_days):
        """Generate captured+failed payments; batch captured into settlements."""
        span = (end - start).total_seconds()
        captured = []
        for _ in range(n_success):
            cust = rng.choice(customers)
            prod = rng.choice(products)
            created = start + timedelta(seconds=rng.random() * span)
            _, pay = make_payment(cust, prod, created, "captured")
            captured.append(pay)
        for _ in range(n_failed):
            cust = rng.choice(customers)
            prod = rng.choice(products)
            created = start + timedelta(seconds=rng.random() * span)
            make_payment(cust, prod, created, "failed")
        # batch captured payments into settlements of 8-12
        captured.sort(key=lambda p: p["created_at"])
        i = 0
        while i < len(captured):
            batch = captured[i:i + rng.randint(8, 12)]
            i += len(batch)
            batch_created = datetime.fromisoformat(batch[-1]["created_at"])
            expected = batch_created + timedelta(days=settle_days)
            if rng.random() < pending_ratio or expected > now:
                s = make_settlement(batch_created, "pending", expected_at=expected)
            else:
                s = make_settlement(batch_created, "processed", settled_at=expected, expected_at=expected)
            for p in batch:
                p["settlement_id"] = s["id"]
            finalize_settlement(s, batch)
        return captured

    # PRIOR period: healthy — most settlements processed on time.
    prior_captured = gen_period(prior_start, prior_end, 150, 12, pending_ratio=0.12, settle_days=2)
    # CURRENT period: cash decline — many settlements still pending (delayed).
    cur_captured = gen_period(cur_start, now - timedelta(hours=6), 138, 13, pending_ratio=0.55, settle_days=2)

    # ---- Refunds: prior baseline, current spike ----
    def add_refunds(pool, total_target, when_start, when_end):
        added = 0
        rng.shuffle(pool)
        for p in pool:
            if added >= total_target:
                break
            amt = p["amount_paise"] if rng.random() < 0.4 else p["amount_paise"] // 2
            amt = min(amt, total_target - added)
            if amt < 5000:
                continue
            created = when_start + timedelta(seconds=rng.random() * (when_end - when_start).total_seconds())
            refunds.append({
                "id": new_id(), "organization_id": org_id, "external_id": f"rfnd_{len(refunds)+1:05d}",
                "payment_id": p["id"], "order_id": p["order_id"], "customer_id": p["customer_id"],
                "product_id": p["product_id"], "amount_paise": amt, "status": "processed",
                "reason": rng.choice(REFUND_REASONS), "created_at": _iso(created), "deleted_at": None,
            })
            added += amt
        return added

    add_refunds(list(prior_captured), 2_93_000_00, prior_start, prior_end)  # ₹2.93L
    add_refunds(list(cur_captured), 3_84_000_00, cur_start, now)            # ₹3.84L spike

    # ---- Invoices / receivables ----
    aging_targets = [(3, "current"), (6, "1-7"), (7, "8-30"), (5, "31-60"), (4, "60+")]
    for count, bucket in aging_targets:
        for _ in range(count):
            cust = rng.choice(customers)
            amt = rng.randint(50, 400) * 100_00
            if bucket == "current":
                due = now + timedelta(days=rng.randint(3, 20)); age_days = 0; paid = 0
            elif bucket == "1-7":
                due = now - timedelta(days=rng.randint(1, 7)); age_days = 4; paid = 0
            elif bucket == "8-30":
                due = now - timedelta(days=rng.randint(8, 30)); age_days = 18; paid = 0
            elif bucket == "31-60":
                due = now - timedelta(days=rng.randint(31, 60)); age_days = 45; paid = 0
            else:
                due = now - timedelta(days=rng.randint(61, 120)); age_days = 90; paid = 0
            created = due - timedelta(days=30)
            invoices.append({
                "id": new_id(), "organization_id": org_id, "external_id": f"inv_{len(invoices)+1:05d}",
                "customer_id": cust["id"], "amount_paise": amt, "paid_amount_paise": paid,
                "status": "unpaid", "due_date": _iso(due), "created_at": _iso(created), "deleted_at": None,
            })
    # some paid invoices for realism
    for _ in range(25):
        cust = rng.choice(customers)
        amt = rng.randint(50, 300) * 100_00
        created = now - timedelta(days=rng.randint(20, 90))
        invoices.append({
            "id": new_id(), "organization_id": org_id, "external_id": f"inv_{len(invoices)+1:05d}",
            "customer_id": cust["id"], "amount_paise": amt, "paid_amount_paise": amt,
            "status": "paid", "due_date": _iso(created + timedelta(days=15)),
            "created_at": _iso(created), "deleted_at": None,
        })

    # ================= INJECTED EXCEPTION STORIES =================
    story_cust = customers[0]
    story_prod = products[1]

    # 1. DUPLICATE payment: same order charged twice within minutes.
    dup_created = cur_start + timedelta(days=6, hours=10)
    dup_order, dup_pay1 = make_payment(story_cust, story_prod, dup_created, "captured")
    dup_pay2 = dict(dup_pay1)
    dup_pay2["id"] = new_id(); dup_pay2["external_id"] = f"pay_{len(payments)+1:05d}"
    dup_pay2["created_at"] = _iso(dup_created + timedelta(minutes=3)); dup_pay2["settlement_id"] = None
    payments.append(dup_pay2)

    # 2. MISSING SETTLEMENT: old captured payment never assigned to a settlement.
    miss_created = cur_start + timedelta(days=2)
    _, miss_pay = make_payment(customers[3], products[4], miss_created, "captured")
    miss_pay["settlement_id"] = None

    # 3. FEE DISCREPANCY: recorded fee higher than the contracted 2%+GST.
    fee_created = cur_start + timedelta(days=10)
    _, fee_pay = make_payment(customers[5], products[9], fee_created, "captured")
    fee_pay["fee_paise"] = fee_pay["fee_paise"] * 3  # overcharged fee
    fee_s = make_settlement(fee_created, "processed", settled_at=fee_created + timedelta(days=2),
                            expected_at=fee_created + timedelta(days=2))
    fee_pay["settlement_id"] = fee_s["id"]
    finalize_settlement(fee_s, [fee_pay])

    # 4. PARTIAL settlement: settled amount short of expected net.
    part_created = cur_start + timedelta(days=12)
    _, part_pay = make_payment(customers[6], products[2], part_created, "captured")
    part_s = make_settlement(part_created, "processed", settled_at=part_created + timedelta(days=3),
                             expected_at=part_created + timedelta(days=2))
    part_pay["settlement_id"] = part_s["id"]
    finalize_settlement(part_s, [part_pay], shortfall=part_pay["amount_paise"] // 5)

    # 5. DELAYED settlement: large pending settlement past its expected date.
    delay_created = cur_start + timedelta(days=4)
    delay_s = make_settlement(delay_created, "pending",
                              expected_at=delay_created + timedelta(days=2))
    delay_payments = []
    for _ in range(6):
        _, p = make_payment(rng.choice(customers), products[4], delay_created, "captured", settlement=delay_s)
        delay_payments.append(p)
    finalize_settlement(delay_s, delay_payments)

    # ---- persist ----
    for _lst in (orders, payments, refunds, settlements, invoices, customers, products):
        for _d in _lst:
            _d["source"] = "DEMO"
    if orders: await db.orders.insert_many(orders)
    if payments: await db.payments.insert_many(payments)
    if refunds: await db.refunds.insert_many(refunds)
    if settlements: await db.settlements.insert_many(settlements)
    if invoices: await db.invoices.insert_many(invoices)
    if customers: await db.customers.insert_many(customers)
    if products: await db.products.insert_many(products)


async def seed_admin_and_org():
    """Create the demo organization, users, and financial data."""
    import os
    db = get_db()
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    existing = await db.users.find_one({"email": admin_email})
    if existing:
        org_id = existing["organization_id"]
        await seed_organization(org_id)
        return

    org_id = new_id()
    await db.organizations.insert_one({
        "id": org_id, "name": "Meridian Commerce Pvt Ltd", "active_source": "DEMO",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    users = [
        (admin_email, os.environ["ADMIN_PASSWORD"], "Priya Nair", "OWNER"),
        ("admin@proofledger.com", "Demo123!", "Rahul Mehta", "ADMIN"),
        ("analyst@proofledger.com", "Demo123!", "Ana Verma", "ANALYST"),
        ("viewer@proofledger.com", "Demo123!", "Sam Rao", "VIEWER"),
    ]
    for email, pw, name, role in users:
        await db.users.insert_one({
            "id": new_id(), "organization_id": org_id, "email": email.lower(),
            "password_hash": hash_password(pw), "name": name, "role": role,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    await seed_organization(org_id)
