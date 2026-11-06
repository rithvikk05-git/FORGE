"""Deterministic SME recommendations for one validated FORGE opportunity.

This agent reads the same synthetic CSV and specialization map as the workbook
importer. It returns a LangGraph state update.
Scores rank suitable candidates; they are POC routing aids, not policy approval.
"""
from __future__ import annotations

import re

from app.config import settings
from app.models import GraphState
from app.schemas import Opportunity
from app.reference_data import matching_reference_ids, matching_reference_records
from app.sme_directory import MATCHING_RULES, load_directory, matching_smes


def _technical_matches(case: Opportunity, skillset: str) -> list[str]:
    """Find CSV skills mentioned exactly in the opportunity's own text."""
    context = " ".join(
        value for value in (
            case.customer_request,
            case.technical_constraints,
            case.business_service,
            case.line_item_name,
        ) if value
    ).casefold()
    if not context:
        return []
    skills = [skill.strip() for skill in skillset.split(",") if skill.strip()]
    return [
        skill for skill in skills
        if re.search(r"(?<!\w)" + re.escape(skill.casefold()) + r"(?!\w)", context)
    ]


def _industry_matches(industry: str | None, expertise: str) -> bool:
    if not industry:
        return False
    known_industries = [part.strip().casefold() for part in re.split(r"[&,/|]", expertise)]
    return industry.casefold() in known_industries


def _score(case: Opportunity, sme, row: dict[str, str],
           specialties: tuple[str, ...]) -> dict:
    """Explain a 100-point POC score using only available source fields."""
    optimization = case.optimization_type or case.required_skill
    specialty_points = 30 if sme.specialization == specialties[0] else 25
    service_points = (
        10 if case.service_type == sme.service_type_expertise else
        8 if case.service_type and sme.service_type_expertise == "Both" else 0
    )
    availability_points = 20 if sme.availability_status == "Available" else 12
    industry_points = 5 if _industry_matches(case.industry, row["Industry_Expertise"]) else 0
    technical_matches = _technical_matches(case, row["Skillset"])
    technical_points = 5 if technical_matches else 0

    breakdown = {
        "practice": 30,
        "specialization": specialty_points,
        "service_type": service_points,
        "availability": availability_points,
        "industry": industry_points,
        "technical_skills": technical_points,
    }
    reasons = [
        f"Practice matches {case.practice}",
        f"{sme.specialization} is mapped to {optimization}",
        f"{sme.availability_status} ({sme.utilization_percent}% utilized)",
    ]
    if service_points:
        reasons.append(f"{sme.service_type_expertise} service expertise fits {case.service_type}")
    if industry_points:
        reasons.append(f"Industry expertise includes {case.industry}")
    if technical_matches:
        reasons.append("Opportunity mentions: " + ", ".join(technical_matches))

    return {
        "sme_id": sme.sme_id,
        "name": sme.name,
        "specialization": sme.specialization,
        "availability_status": sme.availability_status,
        "utilization_percent": sme.utilization_percent,
        "sme_match_score": sum(breakdown.values()),
        "sme_rating_points": float(row["Rating_Points"]),
        "match_score_breakdown": breakdown,
        "technical_skills_matched": technical_matches,
        "reasons": reasons,
    }


def match_opportunity(case: Opportunity, directory: list[dict[str, str]]) -> dict:
    """Return up to three available, explainable SME recommendations."""
    optimization = case.optimization_type or case.required_skill
    result = {
        "opportunity_id": case.opportunity_id,
        "status": "no_match",
        "recommendations": [],
        "eligible_count": 0,
        "message": "",
    }
    if not optimization:
        result.update(status="insufficient_information",
                      message="Optimization type or required skill is missing.")
        return result

    specialties = MATCHING_RULES.get(case.practice, {}).get(optimization)
    if not specialties:
        result["message"] = "No SME specialization is mapped to this practice and optimization."
        return result

    candidates = matching_smes(
        directory, case.practice, optimization, case.service_type, case.industry
    )
    rows_by_id = {row["SME_ID"]: row for row in directory}
    scored = [
        _score(case, sme, rows_by_id[sme.sme_id], specialties)
        for sme in candidates if sme.available
    ]
    scored.sort(
        key=lambda item: (
            -item["sme_match_score"],
            item["utilization_percent"],
            -float(rows_by_id[item["sme_id"]]["Rating_Points"]),
            item["sme_id"],
        )
    )
    for rank, recommendation in enumerate(scored[:3], 1):
        recommendation["rank"] = rank

    result["recommendations"] = scored[:3]
    result["eligible_count"] = len(scored)
    if scored:
        result["status"] = "matched"
        result["message"] = f"{len(scored[:3])} of {len(scored)} eligible SMEs recommended."
    else:
        result["message"] = "No available SME meets the practice, specialization, and service requirements."
    return result


def run(state: GraphState) -> dict:
    """Validate graph input and return only this agent's state updates."""
    case = Opportunity.model_validate(state["case"])
    try:
        directory = load_directory(settings.sme_csv_path)
    except OSError:
        result = {
            "opportunity_id": case.opportunity_id,
            "status": "directory_unavailable",
            "recommendations": [],
            "eligible_count": 0,
            "message": "Synthetic SME directory is unavailable.",
        }
    else:
        result = match_opportunity(case, directory)
    result["reference_ids"] = {
        name: matching_reference_ids(state.get("reference_data"), name, case)
        for name in ("successful_opportunities", "form_opportunities")
    }
    result["reference_evidence"] = {
        name: matching_reference_records(state.get("reference_data"), name, case)
        for name in ("successful_opportunities", "form_opportunities")
    }
    return {
        "sme_matching": result,
        "trace": state.get("trace", []) + ["sme_matching: deterministic recommendations prepared"],
    }
