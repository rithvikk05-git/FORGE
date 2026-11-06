"""Reference sheets and form intake stay distinct from approved precedents."""
import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import app
from app.reference_data import FILES, load_reference_data, matching_reference_records
from app.schemas import Opportunity
from scripts.index_vectors import precedent_rows


def test_empty_reference_sheets_and_json_intake(isolated_store, valid_case):
    case = Opportunity.model_validate(valid_case)
    assert all(load_reference_data()[name] == [] for name in FILES)
    from app.agents.intake import run
    state = run({"case": case.model_dump(mode="json")})
    assert state["prompt_template"] is None
    assert json.loads(json.dumps(state["case"]))["opportunity_id"] == case.opportunity_id
    assert set(FILES).issubset(state["reference_data"])


def test_reference_records_are_exposed_as_evidence_without_scoring(tmp_path, isolated_store, valid_case):
    for name in FILES:
        records = [{"reference_id": f"{name}-1", "opportunity_id": "TEST-001",
                    "source_note": "provided reference"}] if name == "cost_impact" else []
        (tmp_path / f"{name}.json").write_text(json.dumps({"schema_version": 1, "records": records}), encoding="utf-8")
    refs = load_reference_data(tmp_path, current_id="TEST-001")
    case = Opportunity.model_validate(valid_case)
    assert matching_reference_records(refs, "cost_impact", case) == refs["cost_impact"]
    assert matching_reference_records(refs, "compliance", case) == []


def test_populated_reference_reaches_agent_output(tmp_path, isolated_store, valid_case, monkeypatch):
    import app.reference_data as reference_module
    for name in FILES:
        records = [{"reference_id": "COST-1", "opportunity_id": "TEST-001",
                    "source_note": "reference only"}] if name == "cost_impact" else []
        (tmp_path / f"{name}.json").write_text(json.dumps({"schema_version": 1, "records": records}), encoding="utf-8")
    monkeypatch.setattr(reference_module, "REFERENCE_DIR", tmp_path)
    with TestClient(app) as client:
        case = dict(valid_case, opportunity_id="TEST-001")
        assert client.post("/api/opportunities/form", json=case).status_code == 201
        response = client.post("/api/opportunities/TEST-001/evaluate")
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["reference_counts"]["cost_impact"] == 1
        assert result["feasibility"]["reference_evidence"]["cost_impact"][0]["reference_id"] == "COST-1"
        assert result["risk_assessment"]["reference_evidence"]["cost_impact"][0]["reference_id"] == "COST-1"
        assert result["consolidation"]["reference_ids"]["cost_impact"] == ["COST-1"]


def test_form_submission_is_listed_and_used_as_reference(isolated_store, valid_case):
    with TestClient(app) as client:
        first = dict(valid_case, opportunity_id="FORM-001", source_system="manual")
        second = dict(valid_case, opportunity_id="FORM-002", source_system="manual")
        assert client.post("/api/opportunities/form", json=first).status_code == 201
        assert client.post("/api/opportunities/form", json=second).status_code == 201
        assert client.post("/api/opportunities/form", json=second).status_code == 409
        assert client.get("/api/metrics").json()["total"] == 2
        assert client.get("/api/opportunities/FORM-001").json()["case"]["source_system"] == "form"
        evaluated = client.post("/api/opportunities/FORM-002/evaluate")
        assert evaluated.status_code == 200, evaluated.text
        result = evaluated.json()["result"]
        assert result["prompt_template"] is None
        assert result["reference_counts"]["form_opportunities"] == 1
        assert "FORM-001" in result["consolidation"]["reference_ids"]["form_opportunities"]
        assert precedent_rows() == []


def test_workbook_import_coexists_with_form_cases(isolated_store, valid_case):
    source = Path(__file__).resolve().parents[1] / "data/private/FORGE_60_Opportunities_26_Column_Agent_Input.xlsx"
    if not source.is_file():
        return
    shutil.copyfile(source, isolated_store.source_xlsx_path)
    with TestClient(app) as client:
        assert client.post("/api/opportunities/form", json=dict(valid_case, opportunity_id="FORM-001")).status_code == 201
        response = client.post("/api/opportunities/import")
        assert response.status_code == 200, response.text
        assert client.get("/api/metrics").json()["total"] == 61
        assert precedent_rows() == []
