from fastapi.testclient import TestClient

from app.api import app
from app.schemas import Opportunity
from app.services import put_opportunity


def test_api_review_and_internal_summary_guard(isolated_store, valid_case):
    version = put_opportunity(Opportunity.model_validate(valid_case))["case_version"]
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/opportunities?practice=Cloud").json()[0]["case"]["opportunity_id"] == "TEST-001"
        evaluated = client.post("/api/opportunities/TEST-001/evaluate")
        assert evaluated.status_code == 200
        assert evaluated.json()["review_status"] == "pending"
        assert len(client.get("/api/reviews").json()) == 1
        assert client.get("/api/opportunities/TEST-001/approved-summary").status_code == 409
        decision = {"decision": "approve", "reviewer_id": "demo-sme", "reviewer_role": "sme",
                    "case_version": version, "comments": "Synthetic test review approved"}
        assert client.post("/api/reviews/TEST-001/decision", json=decision).status_code == 403
        approved = client.post("/api/reviews/TEST-001/decision", json=decision,
                               headers={"X-Reviewer-Token": "test-sme-token"})
        assert approved.status_code == 200, approved.text
        assert approved.json()["review_status"] == "approved"
        summary = client.get("/api/opportunities/TEST-001/approved-summary")
        assert summary.status_code == 200
        assert summary.json()["use"].startswith("Internal proof-of-concept")
        assert summary.json()["customer_savings"]["validated_monthly_customer_savings"] == "12000"
        assert client.get("/api/opportunities/TEST-001/gtm-pack").status_code == 404
        metrics = client.get("/api/metrics").json()
        assert metrics["total"] == 1
        assert sum(metrics["priorities"].values()) == 1


def test_missing_case_is_404(isolated_store):
    with TestClient(app) as client:
        assert client.get("/api/opportunities/absent").status_code == 404
        assert client.post("/api/opportunities/absent/evaluate").status_code == 404
        assert client.put("/api/opportunities/absent", json={
            "opportunity_id": "absent", "practice": "Cloud", "opportunity_name": "Synthetic",
            "source_sales_stage": "Identified"}).status_code == 404
