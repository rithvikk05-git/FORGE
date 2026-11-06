"""Consolidation keeps agent findings distinct and routes uncertainty to review."""
from pathlib import Path

import pytest

from app.agents.consolidation import consolidate, run as run_consolidation
from app.agents.feasibility import assess_feasibility
from app.agents.risk import assess_risk
from app.agents.sme_matching import run as run_sme
from app.schemas import Opportunity
from app.workbook_26 import load_cases

ROOT = Path(__file__).resolve().parents[1]


def complete(case):
    state = {"case": case.model_dump(mode="json")}
    state.update(run_sme(state))
    state["feasibility"] = assess_feasibility(case, state["sme_matching"])
    state["risk_assessment"] = assess_risk(case, state["sme_matching"], state["feasibility"])
    return state


def test_real_case_consolidates_three_agents_without_approval():
    workbook = ROOT / "data/private/FORGE_60_Opportunities_26_Column_Agent_Input.xlsx"
    directory = ROOT / "data/private/Kyndryl_Synthetic_SME_Directory_60.csv"
    if not workbook.is_file() or not directory.is_file():
        pytest.skip("Private synthetic sources unavailable")
    case = next(item for item in load_cases(workbook, directory)[0]
                if item.opportunity_id == "SOC-1F91OWU")
    result = run_consolidation(complete(case))["consolidation"]
    assert result["opportunity_id"] == case.opportunity_id
    assert [item["sme_id"] for item in result["recommended_smes"]] == ["SME-003"]
    assert result["feasibility"]["score"] == 48
    assert result["risk"]["overall_risk_score"] is None
    assert result["assessment_status"] == "NEEDS_INFORMATION"
    assert result["risk"]["social_impact"]["provisional"] is True
    assert result["provisional_assumptions"]
    assert result["requires_human_review"]
    assert "decision" not in result


def test_uncertain_risk_requests_information(valid_case):
    case = Opportunity.model_validate({**valid_case, "service_impact": None})
    state = complete(case)
    result = run_consolidation(state)["consolidation"]
    assert result["risk"]["risk_classification"] == "UNCERTAIN"
    assert result["assessment_status"] == "NEEDS_INFORMATION"
    assert "social_impact_evidence" in result["missing_information"]
    assert "Request missing information" in result["recommended_next_action"]


def test_no_sme_match_is_visible_to_reviewer(valid_case):
    case = Opportunity.model_validate(valid_case)
    matching = {"opportunity_id": case.opportunity_id, "status": "no_match",
                "recommendations": [], "message": "No suitable SME available."}
    feasibility = assess_feasibility(case, matching)
    result = consolidate(case, matching, feasibility, assess_risk(case, matching, feasibility))
    assert result["recommended_smes"] == []
    assert "available_sme" in result["missing_information"]
    assert "No suitable SME available." in result["main_concerns"]
    assert result["requires_human_review"]


def test_inconsistent_opportunity_ids_are_rejected(valid_case):
    case = Opportunity.model_validate(valid_case)
    state = complete(case)
    state["risk_assessment"]["opportunity_id"] = "OTHER-ID"
    with pytest.raises(ValueError, match="risk_assessment opportunity_id"):
        run_consolidation(state)


def test_missing_agent_outputs_are_gracefully_marked_incomplete(valid_case):
    case = Opportunity.model_validate(valid_case)
    result = run_consolidation({"case": case.model_dump(mode="json")})["consolidation"]
    assert result["feasibility"]["score"] is None
    assert result["risk"]["overall_risk_score"] is None
    assert result["assessment_status"] == "NEEDS_INFORMATION"
    assert {"sme_matching_output", "feasibility_output", "risk_assessment_output"} <= set(result["missing_information"])
    assert result["policy"]["priority"] in {"HOLD", "P1", "P2", "P3"}
