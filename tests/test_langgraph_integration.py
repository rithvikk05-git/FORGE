"""The existing review graph now runs the four analysis agents in sequence."""
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

import app.graph as graph_module
import app.services as services_module
from app.api import app
from app.policy_engine import assess
from app.repositories import get_approval, get_evaluation
from app.schemas import Decision, Opportunity
from app.services import decide, detail, evaluate, put_opportunity
from app.workbook_26 import load_cases
from dashboard.excel_export import generate_excel

ROOT = Path(__file__).resolve().parents[1]
AGENTS = (
    ("sme_matching", "sme_matching", ()),
    ("feasibility", "feasibility", ("sme_matching",)),
    ("risk", "risk_assessment", ("sme_matching", "feasibility")),
    ("consolidation", "consolidation", ("sme_matching", "feasibility", "risk_assessment")),
)


def test_analysis_graph_has_exact_four_agent_path():
    edges = {(edge.source, edge.target)
             for edge in graph_module.build_analysis_graph().get_graph().edges}
    assert edges == {
        ("__start__", "sme_matching"),
        ("sme_matching", "feasibility"),
        ("feasibility", "risk"),
        ("risk", "consolidation"),
        ("consolidation", "__end__"),
    }


def test_nodes_run_in_order_with_upstream_outputs_and_one_id(isolated_store, valid_case, monkeypatch):
    seen = []
    for name, output_key, dependencies in AGENTS:
        module = getattr(graph_module, name)
        original = module.run

        def spy(state, name=name, original=original, dependencies=dependencies):
            assert Opportunity.model_validate(state["case"]).opportunity_id == state["opportunity_id"]
            assert all(state[key]["opportunity_id"] == state["opportunity_id"] for key in dependencies)
            seen.append(name)
            return original(state)

        monkeypatch.setattr(module, "run", spy)

    put_opportunity(Opportunity.model_validate(valid_case))
    result = evaluate("TEST-001")["result"]
    assert seen == [name for name, _, _ in AGENTS]
    assert all(result[key]["opportunity_id"] == "TEST-001" for _, key, _ in AGENTS)
    assert [item.split(":", 1)[0] for item in result["trace"]] == [
        "intake", "assessment", "sme_matching", "feasibility", "risk", "consolidation"
    ]
    assert result["review_status"] == "pending"
    assert result["approved_summary"] is None
    assert get_approval("TEST-001") is None


def test_policy_scoring_runs_once_before_human_review(isolated_store, valid_case, monkeypatch):
    calls = []
    original = graph_module.assessment.assess

    def counted(case, **kwargs):
        calls.append(case.opportunity_id)
        return original(case, **kwargs)

    for module in (graph_module.assessment, graph_module.risk, graph_module.consolidation):
        monkeypatch.setattr(module, "assess", counted)
    put_opportunity(Opportunity.model_validate(valid_case))
    evaluate("TEST-001")
    assert calls == ["TEST-001"]


def test_real_synthetic_case_reaches_consolidation_with_social_proxy(isolated_store):
    workbook = ROOT / "data/private/FORGE_60_Opportunities_26_Column_Agent_Input.xlsx"
    directory = ROOT / "data/private/Kyndryl_Synthetic_SME_Directory_60.csv"
    if not workbook.is_file() or not directory.is_file():
        pytest.skip("Private synthetic sources unavailable")
    case = next(item for item in load_cases(workbook, directory)[0]
                if item.opportunity_id == "SOC-1F91OWU")
    put_opportunity(case)
    result = evaluate(case.opportunity_id)["result"]
    consolidated = result["consolidation"]
    assert consolidated["opportunity_id"] == case.opportunity_id
    assert [item["sme_id"] for item in consolidated["recommended_smes"]] == ["SME-003"]
    assert consolidated["feasibility"]["score"] == result["feasibility"]["feasibility_score"]
    assert consolidated["risk"] == result["risk_assessment"]
    assert consolidated["risk"]["social_impact"]["provisional"] is True
    assert consolidated["risk"]["overall_risk_score"] is None
    assert consolidated["assessment_status"] == "NEEDS_INFORMATION"
    assert consolidated["requires_human_review"] is True
    assert result["review_status"] == "pending"


def test_missing_sme_match_and_social_evidence_stay_visible(isolated_store, valid_case):
    case = Opportunity.model_validate({**valid_case,
        "optimization_type": "unmapped_synthetic_optimization", "service_impact": None})
    put_opportunity(case)
    result = evaluate(case.opportunity_id)["result"]
    assert result["sme_matching"]["status"] == "no_match"
    assert result["feasibility"]["classification"] == "UNCERTAIN"
    assert result["risk_assessment"]["risk_classification"] == "UNCERTAIN"
    assert result["risk_assessment"]["overall_risk_score"] is None
    assert result["consolidation"]["assessment_status"] == "NEEDS_INFORMATION"
    assert {"available_sme", "social_impact_evidence"} <= set(result["consolidation"]["missing_information"])
    assert result["review_status"] == "pending"
    assert get_approval(case.opportunity_id) is None


@pytest.mark.parametrize("failure", ["missing_output", "exception"])
def test_agent_failure_or_missing_output_is_reported_without_saved_evaluation(
        isolated_store, valid_case, monkeypatch, failure):
    put_opportunity(Opportunity.model_validate(valid_case))

    def missing_output(_state):
        return {"trace": []}

    def raise_error(_state):
        raise RuntimeError("synthetic agent failure")

    monkeypatch.setattr(graph_module.risk, "run",
                        missing_output if failure == "missing_output" else raise_error)
    expected = ("Risk did not return risk_assessment" if failure == "missing_output"
                else "Risk failed: synthetic agent failure")
    with pytest.raises(ValueError, match=expected):
        evaluate("TEST-001")
    assert get_evaluation("TEST-001") is None


def test_invalid_opportunity_cannot_enter_agent_chain(isolated_store, monkeypatch):
    called = []

    def spy(_state):
        called.append(True)
        return {}

    monkeypatch.setattr(graph_module.sme_matching, "run", spy)
    with pytest.raises(Exception):
        graph_module.evaluate_graph({"opportunity_id": "BAD"}, "v1")
    assert called == []


def test_api_excel_and_review_keep_existing_behavior_without_repeating_matching(
        isolated_store, valid_case, monkeypatch):
    calls = []
    original = graph_module.sme_matching.run

    def spy(state):
        calls.append(state["opportunity_id"])
        return original(state)

    monkeypatch.setattr(graph_module.sme_matching, "run", spy)
    version = put_opportunity(Opportunity.model_validate(valid_case))["case_version"]
    with TestClient(app) as client:
        first = client.post("/api/opportunities/TEST-001/evaluate")
        assert first.status_code == 200, first.text
        assert first.json()["result"]["consolidation"]["requires_human_review"]
        second = client.post("/api/opportunities/TEST-001/evaluate")
        assert second.json() == first.json()
        assert calls == ["TEST-001"]
        assert client.get("/api/opportunities/TEST-001/approved-summary").status_code == 409
        exported = load_workbook(BytesIO(generate_excel(detail("TEST-001"))))
        assert "FORGE Assessment" in exported.sheetnames
        assert exported["FORGE Assessment"]["B2"].value == "TEST-001"

        decision = Decision(decision="approve", reviewer_id="demo-sme", reviewer_role="sme",
                            case_version=version, comments="Reviewed synthetic case")
        approved = decide("TEST-001", decision)
        assert approved["review_status"] == "approved"
        assert approved["result"]["consolidation"] == first.json()["result"]["consolidation"]
        assert calls == ["TEST-001"]


def test_resume_preserves_stored_analysis_when_checkpoint_has_old_state(
        isolated_store, valid_case, monkeypatch):
    case = Opportunity.model_validate(valid_case)
    version = put_opportunity(case)["case_version"]
    original = evaluate(case.opportunity_id)

    def legacy_resume(_opportunity_id, _version, _decision):
        return {"assessment": assess(case), "review_status": "approved",
                "approved_summary": {"opportunity_id": case.opportunity_id},
                "trace": ["review: old checkpoint resumed"]}

    monkeypatch.setattr(services_module, "resume_graph", legacy_resume)
    reviewed = decide(case.opportunity_id, Decision(
        decision="approve", reviewer_id="demo-sme", reviewer_role="sme",
        case_version=version, comments="Existing checkpoint review"))
    assert reviewed["review_status"] == "approved"
    assert reviewed["result"]["consolidation"] == original["result"]["consolidation"]
    assert reviewed["result"]["sme_matching"] == original["result"]["sme_matching"]
