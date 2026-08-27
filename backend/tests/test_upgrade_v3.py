"""Iteration-3 tests: Razorpay adapter, source scoping, baselines/attention,
enhanced evidence, PDF export, RBAC. No Razorpay/OpenAI keys are configured (expected)."""
import os
import pytest
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE}/api/v1"
TIMEOUT = 60

CREDS = {
    "OWNER": ("cfo@proofledger.com", "Demo123!"),
    "ANALYST": ("analyst@proofledger.com", "Demo123!"),
    "VIEWER": ("viewer@proofledger.com", "Demo123!"),
}


def _login(role):
    email, pwd = CREDS[role]
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=TIMEOUT)
    if r.status_code != 200:
        pytest.fail(f"login failed for {role}: {r.status_code} {r.text[:300]}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def owner():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_login('OWNER')}"})
    return s


@pytest.fixture(scope="module")
def analyst():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_login('ANALYST')}"})
    return s


@pytest.fixture(scope="module")
def viewer():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_login('VIEWER')}"})
    return s


# ---------------- source scoping ----------------
class TestSourceScoping:
    def test_dashboard_source_demo(self, owner):
        r = owner.get(f"{API}/dashboard", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("source") == "DEMO", d.get("source")
        assert d.get("metrics"), "no metrics"
        assert d["metrics"]["gross_revenue"]["current"]["value_display"].startswith("₹")

    def test_switch_to_razorpay_rejected(self, owner):
        r = owner.post(f"{API}/integrations/source", json={"source": "RAZORPAY_TEST"}, timeout=TIMEOUT)
        assert r.status_code == 400, f"{r.status_code} {r.text[:300]}"
        assert "credential" in r.json()["detail"].lower()

    def test_switch_to_demo_ok(self, owner):
        r = owner.post(f"{API}/integrations/source", json={"source": "DEMO"}, timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["active_source"] == "DEMO"

    def test_invalid_source(self, owner):
        r = owner.post(f"{API}/integrations/source", json={"source": "NOPE"}, timeout=TIMEOUT)
        assert r.status_code == 400


# ---------------- razorpay adapter endpoints ----------------
class TestRazorpay:
    def test_status_no_credentials(self, owner):
        r = owner.get(f"{API}/integrations/status", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["credentials_present"] is False
        assert d["connected"] is False
        assert isinstance(d["detail"], str) and d["detail"]
        assert d["active_source"] == "DEMO"

    def test_test_connection(self, analyst):
        r = analyst.post(f"{API}/integrations/razorpay/test", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["connected"] is False
        assert "credential" in d["detail"].lower()

    def test_sync_returns_400_not_crash(self, analyst):
        r = analyst.post(f"{API}/integrations/razorpay/sync", timeout=TIMEOUT)
        assert r.status_code == 400, f"{r.status_code} {r.text[:300]}"
        assert "credential" in r.json()["detail"].lower()

    def test_sync_incremental_400(self, analyst):
        r = analyst.post(f"{API}/integrations/razorpay/sync?incremental=true", timeout=TIMEOUT)
        assert r.status_code == 400

    def test_sync_forbidden_for_viewer(self, viewer):
        r = viewer.post(f"{API}/integrations/razorpay/sync", timeout=TIMEOUT)
        assert r.status_code == 403, f"{r.status_code} {r.text[:200]}"

    def test_source_switch_forbidden_for_viewer(self, viewer):
        r = viewer.post(f"{API}/integrations/source", json={"source": "DEMO"}, timeout=TIMEOUT)
        assert r.status_code == 403

    def test_history(self, owner):
        r = owner.get(f"{API}/integrations/razorpay/history", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        assert isinstance(r.json()["runs"], list)

    def test_webhook_bad_signature(self):
        r = requests.post(f"{API}/integrations/webhook", data=b'{"event":"payment.captured"}',
                          headers={"X-Razorpay-Signature": "deadbeef",
                                   "Content-Type": "application/json"}, timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["received"] is True
        assert d["verified"] is False


# ---------------- analytics ----------------
class TestAnalytics:
    def test_baselines(self, owner):
        r = owner.get(f"{API}/analytics/baselines", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        bl = r.json()["baselines"]
        labels = [b["metric"] for b in bl]
        for expected in ["Payment volume", "Refund rate", "Settlement cash", "Processing fees"]:
            assert expected in labels, labels
        for b in bl:
            assert b["status"] in {"NORMAL", "ELEVATED", "UNUSUAL"}, b
            assert b["current"] and b["baseline"]
            assert b["deviation_display"]
        cash = [b for b in bl if b["metric"] == "Settlement cash"][0]
        assert cash["status"] == "UNUSUAL", cash

    def test_attention(self, owner):
        r = owner.get(f"{API}/analytics/attention", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        items = d["items"]
        assert d["count"] == len(items)
        types = {i["type"] for i in items}
        for t in ["pending_settlement", "reconciliation_exception", "overdue_receivables",
                  "fee_discrepancy", "refund_spike"]:
            assert t in types, types
        for i in items:
            assert i["reason"] and i["amount"] and i["evidence"] and i["recommended_action"]
        pending = [i for i in items if i["type"] == "pending_settlement"][0]
        assert pending["severity"] == "high"
        # high severity items sorted first
        order = {"high": 0, "medium": 1, "low": 2}
        sev = [order[i["severity"]] for i in items]
        assert sev == sorted(sev), sev

    def test_analytics_viewer_readable(self, viewer):
        for path in ["/analytics/baselines", "/analytics/attention"]:
            r = viewer.get(f"{API}{path}", timeout=TIMEOUT)
            assert r.status_code == 200, f"{path} {r.status_code}"


# ---------------- enhanced evidence ----------------
class TestEnhancedEvidence:
    def test_pending_settlements_evidence(self, owner):
        r = owner.get(f"{API}/evidence/metric/pending_settlements", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["source"] == "DEMO"
        assert isinstance(d["evidence_coverage"], (int, float))
        assert 0 <= d["evidence_coverage"] <= 1
        assert isinstance(d["source_transaction_count"], int) and d["source_transaction_count"] > 0
        assert isinstance(d["source_ids"], list)
        assert d["fact"]["value_display"].startswith("₹")
        assert d["prior_fact"] is not None
        assert d["delta"] is not None and "change_pct" in d["delta"]
        assert d["records"], "no source records returned"
        assert all("_id" not in rec for rec in d["records"])

    def test_gross_revenue_formatting(self, owner):
        r = owner.get(f"{API}/evidence/metric/gross_revenue", timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert d["fact"]["value_display"].startswith("₹")
        assert d["record_collection"] == "payments"
        assert d["source_transaction_count"] > 0

    def test_unknown_metric_404(self, owner):
        r = owner.get(f"{API}/evidence/metric/not_a_metric", timeout=TIMEOUT)
        assert r.status_code == 404


# ---------------- investigations + PDF export ----------------
class TestInvestigationExports:
    inv_id = None

    def test_create_investigation(self, owner):
        r = owner.post(f"{API}/investigations", json={
            "title": "TEST_pdf_export", "question": "Why did cash decrease this month?"},
            timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d.get("id")
        TestInvestigationExports.inv_id = d["id"]

    def test_pdf_export(self, owner):
        iid = TestInvestigationExports.inv_id
        assert iid, "no investigation created"
        r = owner.get(f"{API}/investigations/{iid}/report.pdf", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        assert r.headers["content-type"].startswith("application/pdf"), r.headers.get("content-type")
        assert r.content[:4] == b"%PDF", r.content[:20]
        assert len(r.content) > 1000

    def test_json_export(self, owner):
        r = owner.get(f"{API}/investigations/{TestInvestigationExports.inv_id}/report", timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert d["question"] and "findings" in d and d["disclaimer"]

    def test_csv_export(self, owner):
        r = owner.get(f"{API}/investigations/{TestInvestigationExports.inv_id}/report?fmt=csv",
                      timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert "type,statement" in r.text

    def test_pdf_404_unknown(self, owner):
        r = owner.get(f"{API}/investigations/does-not-exist/report.pdf", timeout=TIMEOUT)
        assert r.status_code == 404

    def test_investigation_create_forbidden_viewer(self, viewer):
        r = viewer.post(f"{API}/investigations", json={"title": "TEST_v", "question": "x"}, timeout=TIMEOUT)
        assert r.status_code == 403, r.status_code


# ---------------- regression of core ----------------
class TestCoreRegression:
    def test_ai_cash_autopsy(self, owner):
        r = owner.post(f"{API}/ai/ask", json={"question": "Why did cash decrease this month?"},
                       timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["intent"] == "cash_autopsy", d["intent"]
        assert d["confidence"]["band"] == "HIGH", d["confidence"]
        contribs = (d.get("autopsy") or {}).get("contributors") or []
        assert contribs, "no contributors in autopsy"
        assert contribs[0].get("metric") == "settlement_timing", contribs[0]

    def test_reconciliation(self, owner):
        r = owner.get(f"{API}/reconciliation", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["match_rate"] >= 90, d["match_rate"]
        assert d["exceptions"], "expected exceptions"
        assert d["summary"]["MATCHED"]["count"] > 0

    def test_evaluation_run(self, owner):
        r = owner.post(f"{API}/evaluations/run", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["score_pct"] == 100, d["score_pct"]
