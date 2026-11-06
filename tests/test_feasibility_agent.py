"""Focused checks for Feasibility Agent using the active synthetic sources."""
from pathlib import Path

import pytest

from app.agents.feasibility import assess_feasibility, run as run_feasibility
from app.agents.sme_matching import run as run_sme_matching
from app.policy_engine import assess
from app.schemas import Opportunity
from app.workbook_26 import load_cases

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "data/private/FORGE_60_Opportunities_26_Column_Agent_Input.xlsx"
SME_CSV = ROOT / "data/private/Kyndryl_Synthetic_SME_Directory_60.csv"


@pytest.fixture
def cases():
    if not WORKBOOK.is_file() or not SME_CSV.is_file():
        pytest.skip("Private synthetic source files are not present")
    return load_cases(WORKBOOK, SME_CSV)[0]


def test_real_case_reuses_policy_factors_and_explains_delivery_constraints(cases):
    case = next(item for item in cases if item.opportunity_id == "SOC-1F91OWU")
    state = {"case": case.model_dump(mode="json"), "trace": ["intake"]}
    state.update(run_sme_matching(state))
    output = run_feasibility(state)
    result = output["feasibility"]

    assert result["opportunity_id"] == case.opportunity_id
    assert result["feasibility_score"] == 48
    assert result["classification"] == "LOW"
    assert result["missing_evidence"] == []
    assert result["supporting_factors"]["recommended_sme_ids"] == ["SME-003"]
    for name, value in result["supporting_factors"]["policy_factor_values"].items():
        assert value == assess(case)["risk_factors"][name]
    assert result["supporting_factors"]["delivery_constraints"]["rto_minutes"] == 180
    assert any("Zero-trust RBAC" in concern for concern in result["concerns"])
    assert "policy blockers and human review" in result["explanation"]
    assert output["trace"][0] == "intake"
    assert output["trace"][-1].startswith("feasibility:")


def test_no_available_sme_is_uncertain_without_auto_rejection(cases):
    case = next(
        item for item in cases
        if run_sme_matching({"case": item.model_dump(mode="json")})["sme_matching"]["status"] == "no_match"
    )
    state = {"case": case.model_dump(mode="json")}
    state.update(run_sme_matching(state))
    result = run_feasibility(state)["feasibility"]

    assert 0 <= result["feasibility_score"] <= 100
    assert result["classification"] == "UNCERTAIN"
    assert result["supporting_factors"]["policy_factor_values"]["resource_availability"] == 5
    assert "available_sme" in result["missing_evidence"]
    assert any("No available SME" in concern for concern in result["concerns"])
    assert "decision" not in result


def test_missing_inputs_are_conservative_and_reported():
    case = Opportunity(
        opportunity_id="TEST-FEASIBILITY", opportunity_name="Synthetic incomplete case",
        practice="Cloud", source_sales_stage="Identified",
    )
    result = run_feasibility({"case": case.model_dump(mode="json")})["feasibility"]

    assert result["feasibility_score"] == 0
    assert result["classification"] == "UNCERTAIN"
    assert set(result["missing_evidence"]) == {
        "sme_matching_output", "service_impact", "technical_feasibility", "capability_fit"
    }
    assert result["supporting_factors"]["policy_factor_values"]["resource_availability"] == 5


def test_unscored_constraints_do_not_change_policy_based_score(cases):
    case = next(item for item in cases if item.opportunity_id == "SOC-1F91OWU")
    matching = run_sme_matching({"case": case.model_dump(mode="json")})["sme_matching"]
    with_constraints = assess_feasibility(case, matching)
    without_constraints = assess_feasibility(
        case.model_copy(update={
            "technical_constraints": None, "rto_minutes": None, "rpo_minutes": None
        }),
        matching,
    )
    assert with_constraints["feasibility_score"] == without_constraints["feasibility_score"]
    assert len(with_constraints["concerns"]) > len(without_constraints["concerns"])
