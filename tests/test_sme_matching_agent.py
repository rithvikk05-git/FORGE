"""Focused checks for the deterministic SME Matching Agent."""
from pathlib import Path

import pytest

from app.agents.sme_matching import match_opportunity, run
from app.sme_directory import load_directory, matching_smes
from app.workbook_26 import load_cases

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "data/private/FORGE_60_Opportunities_26_Column_Agent_Input.xlsx"
SME_CSV = ROOT / "data/private/Kyndryl_Synthetic_SME_Directory_60.csv"


@pytest.fixture
def synthetic_sources():
    if not WORKBOOK.is_file() or not SME_CSV.is_file():
        pytest.skip("Private synthetic source files are not present")
    cases, _, _ = load_cases(WORKBOOK, SME_CSV)
    return cases, load_directory(SME_CSV)


def test_agent_ranks_real_synthetic_candidates_with_explanations(synthetic_sources):
    cases, directory = synthetic_sources
    case = next(item for item in cases if item.opportunity_id == "SOC-1F91OWU")
    state = {"case": case.model_dump(mode="json"), "trace": ["intake"]}
    first = run(state)
    second = run(state)
    result = first["sme_matching"]

    assert result == second["sme_matching"]
    assert result["status"] == "matched"
    assert result["eligible_count"] == 1
    assert [item["sme_id"] for item in result["recommendations"]] == ["SME-003"]
    assert len(result["recommendations"]) <= 3
    assert first["trace"][:1] == ["intake"]
    known_ids = {row["SME_ID"] for row in directory}
    for rank, item in enumerate(result["recommendations"], 1):
        assert item["rank"] == rank
        assert item["sme_id"] in known_ids
        assert item["availability_status"] != "Limited"
        assert 0 <= item["sme_match_score"] <= 100
        assert item["sme_match_score"] == sum(item["match_score_breakdown"].values())
        assert item["sme_rating_points"] == float(next(row["Rating_Points"] for row in directory if row["SME_ID"] == item["sme_id"]))
        assert "confidence_score" not in item and "score" not in item
        assert item["reasons"] and item["specialization"]


def test_missing_optional_fields_and_unmapped_skill_are_explained(synthetic_sources):
    cases, directory = synthetic_sources
    case = next(item for item in cases if item.opportunity_id == "SOC-1F91OWU")
    missing_skill = case.model_copy(update={"optimization_type": None, "required_skill": None})
    result = match_opportunity(missing_skill, directory)
    assert result["status"] == "insufficient_information"
    assert result["recommendations"] == []

    unknown_skill = case.model_copy(update={"optimization_type": "not_in_directory",
                                            "required_skill": "not_in_directory"})
    result = match_opportunity(unknown_skill, directory)
    assert result["status"] == "no_match"
    assert result["recommendations"] == []

    missing_context = case.model_copy(update={"service_type": None, "industry": None})
    result = match_opportunity(missing_context, directory)
    assert result["status"] == "matched"
    assert all(item["match_score_breakdown"]["service_type"] == 0 for item in result["recommendations"])
    assert all(item["match_score_breakdown"]["industry"] == 0 for item in result["recommendations"])


def test_limited_smes_are_not_recommended(synthetic_sources):
    cases, directory = synthetic_sources
    case = next(
        item for item in cases
        if (candidates := matching_smes(
            directory, item.practice, item.optimization_type, item.service_type, item.industry
        )) and all(not sme.available for sme in candidates)
    )
    result = match_opportunity(case, directory)
    assert result["status"] == "no_match"
    assert result["recommendations"] == []
    assert result["eligible_count"] == 0


def test_technical_skill_bonus_uses_actual_opportunity_text(synthetic_sources):
    cases, directory = synthetic_sources
    case = next(item for item in cases if item.opportunity_id == "SOC-1F91OWU")
    result = match_opportunity(case, directory)
    specialist = next(item for item in result["recommendations"] if item["sme_id"] == "SME-003")
    assert "Agentic AI" in specialist["technical_skills_matched"]
    assert specialist["match_score_breakdown"]["technical_skills"] == 5
    assert any("Agentic AI" in reason for reason in specialist["reasons"])
