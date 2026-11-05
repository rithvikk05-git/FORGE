"""Risk Agent: supported dimensions, uncertainty, and replaceable social rule."""
from pathlib import Path

import pytest

from app.agents import risk
from app.agents.feasibility import assess_feasibility
from app.agents.sme_matching import run as run_sme
from app.schemas import Opportunity
from app.workbook_26 import load_cases

ROOT = Path(__file__).resolve().parents[1]


def inputs(case, status="matched"):
    matching = {"opportunity_id": case.opportunity_id, "status": status,
                "recommendations": [{"sme_id": "demo-sme", "availability_status": "Available"}] if status == "matched" else []}
    return matching, assess_feasibility(case, matching)


def test_real_synthetic_opportunity_has_four_explained_dimensions():
    workbook = ROOT / "data/private/FORGE_60_Opportunities_26_Column_Agent_Input.xlsx"
    directory = ROOT / "data/private/Kyndryl_Synthetic_SME_Directory_60.csv"
    if not workbook.is_file() or not directory.is_file():
        pytest.skip("Private synthetic sources unavailable")
    case = next(item for item in load_cases(workbook, directory)[0]
                if item.opportunity_id == "SOC-1F91OWU")
    state = {"case": case.model_dump(mode="json")}
    state.update(run_sme(state))
    state["feasibility"] = assess_feasibility(case, state["sme_matching"])
    result = risk.run(state)["risk_assessment"]
    assert result["overall_risk_score"] is None
    assert result["risk_classification"] == "UNCERTAIN"
    assert [result[name]["score"] for name in risk.DIMENSION_WEIGHTS] == [None, 0.6, 3, 4]
    assert result["social_impact"]["source_factors"] == {"service_impact": 4}
    assert "validated_financial_evidence" in result["missing_evidence"]
    assert result["requires_human_review"]


def test_high_and_low_risk_bounds_and_direction(valid_case):
    low = Opportunity.model_validate({**valid_case, "service_impact": 0,
                                      "technical_feasibility": 0, "capability_fit": 0})
    high = Opportunity.model_validate({**valid_case, "service_impact": 5,
                                       "technical_feasibility": 5, "capability_fit": 5})
    low_result = risk.assess_risk(low, *inputs(low))
    high_result = risk.assess_risk(high, *inputs(high))
    assert low_result["overall_risk_score"] == 0
    assert low_result["risk_classification"] == "LOW"
    assert high_result["overall_risk_score"] == 65
    assert high_result["risk_classification"] == "HIGH"
    assert 0 <= low_result["overall_risk_score"] < high_result["overall_risk_score"] <= 100


def test_missing_feasibility_and_social_evidence_withhold_total(valid_case):
    case = Opportunity.model_validate(valid_case)
    matching, feasibility = inputs(case)
    no_feasibility = risk.assess_risk(case, matching, None)
    assert no_feasibility["overall_risk_score"] is None
    assert no_feasibility["risk_classification"] == "UNCERTAIN"
    assert "feasibility_output" in no_feasibility["missing_evidence"]
    no_social = case.model_copy(update={"service_impact": None})
    result = risk.assess_risk(no_social, matching, assess_feasibility(no_social, matching))
    assert result["social_impact"]["score"] is None
    assert result["social_impact"]["classification"] == "UNKNOWN"
    assert result["overall_risk_score"] is None
    assert "social_impact_evidence" in result["missing_evidence"]


def test_no_matching_sme_is_known_resource_risk_not_auto_rejection(valid_case):
    case = Opportunity.model_validate(valid_case)
    result = risk.assess_risk(case, *inputs(case, "no_match"))
    assert result["feasibility_impact"]["source_factors"]["resource_availability"] == 5
    assert "available_sme" in result["missing_evidence"]
    assert result["overall_risk_score"] is not None
    assert "decision" not in result


def test_social_proxy_is_provisional_and_replaceable(valid_case, monkeypatch):
    case = Opportunity.model_validate(valid_case)
    matching, feasibility = inputs(case)
    original = risk.assess_risk(case, matching, feasibility)
    assert original["social_impact"]["provisional"] is True
    assert original["social_impact"]["confidence"] == "LOW"
    monkeypatch.setattr(risk, "calculate_social_impact", lambda _case: {
        "score": 5, "classification": "Direct assessment", "source_factors": {"approved_measure": 5},
        "explanation": "Replacement rule", "provisional": False, "confidence": "HIGH",
        "evidence_limitations": [], "requires_sme_validation": False,
    })
    replaced = risk.assess_risk(case, matching, feasibility)
    assert replaced["overall_risk_score"] == original["overall_risk_score"] + 20
    assert replaced["social_impact"]["provisional"] is False


def test_missing_dimensions_and_no_factor_double_counting(valid_case):
    case = Opportunity.model_validate({**valid_case, "capability_fit": None,
                                       "technical_feasibility": None})
    matching, feasibility = inputs(case)
    result = risk.assess_risk(case, matching, feasibility)
    assert result["overall_risk_score"] is None
    assert {"capability_fit", "technical_feasibility"} <= set(result["missing_evidence"])
    complete = Opportunity.model_validate(valid_case)
    matching, feasibility = inputs(complete)
    first = risk.assess_risk(complete, matching, feasibility)
    feasibility["feasibility_score"] = 0  # Context changed; distinct policy factors did not.
    second = risk.assess_risk(complete, matching, feasibility)
    assert first["overall_risk_score"] == second["overall_risk_score"]
    assert second["feasibility_impact"]["source_factors"]["feasibility_agent_score"] == 0
