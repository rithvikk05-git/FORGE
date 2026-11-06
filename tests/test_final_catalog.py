"""The final SOC workbook moves through import, graph, API, and Excel safely."""
import shutil
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.api import app
from app.policy_engine import assess
from app.workbook_26 import load_cases
from dashboard.excel_export import generate_excel
from scripts.index_vectors import precedent_rows

SOURCE = Path(__file__).resolve().parents[1] / "data/private/FORGE_60_Opportunities_26_Column_Agent_Input.xlsx"


def test_final_workbook_preserves_credit_and_unverified_contract_scope():
    cases = {case.opportunity_id: case for case in load_cases(SOURCE)[0]}
    assert len(cases) == 60
    assert "FORGE-POC-ADAI-001" not in cases
    credit = cases["SOC-0ALB-DESCOPE"]
    assert credit.source_implementation_cost == -26000
    assert credit.evidence.implementation_cost == 0
    assert assess(credit)["financial"]["unvalidated_implementation_credit"] == "26000"
    assert all(case.contract.scope == "unknown" for case in cases.values())
    assert sum(bool(case.possible_existing_opportunity_ids) for case in cases.values()) == 14
    assert all(not case.pipeline_matches for case in cases.values())
    assert sum(any(sme.available for sme in case.smes) for case in cases.values()) == 33


def test_final_case_runs_from_api_import_to_draft_excel(isolated_store):
    shutil.copyfile(SOURCE, isolated_store.source_xlsx_path)
    with TestClient(app) as client:
        imported = client.post("/api/opportunities/import")
        assert imported.status_code == 200, imported.text
        assert imported.json()["imported"] == 60
        metrics = client.get("/api/metrics").json()
        assert metrics["total"] == 60
        assert metrics["source_sales_stages"]["Stretch"] == 1
        assert len(precedent_rows()) == 0
        evaluated = client.post("/api/opportunities/SOC-1F91OWU/evaluate")
        assert evaluated.status_code == 200, evaluated.text
        result = evaluated.json()["result"]
        assert [item.split(":", 1)[0] for item in result["trace"]] == [
            "intake", "assessment", "sme_matching", "feasibility", "risk", "consolidation"
        ]
        assert result["sme_matching"]["recommendations"][0]["sme_id"] == "SME-003"
        assert result["risk_assessment"]["risk_classification"] == "UNCERTAIN"
        assert result["consolidation"]["assessment_status"] == "NEEDS_INFORMATION"
        assert evaluated.json()["review_status"] == "pending"
        assert client.get("/api/opportunities/SOC-1F91OWU/approved-summary").status_code == 409
        detail = client.get("/api/opportunities/SOC-1F91OWU").json()
        workbook = load_workbook(BytesIO(generate_excel(detail)))
        assert workbook["FORGE Assessment"]["B2"].value == "SOC-1F91OWU"
        assert workbook["Sales Brief"]["B3"].value.startswith("DRAFT - INTERNAL POC ONLY")
        stretch_detail = client.get("/api/opportunities/SOC-019M6XQ").json()
        stretch_export = load_workbook(BytesIO(generate_excel(stretch_detail)))
        assert stretch_export["Sales Brief"]["C11"].value == "Stretch"
