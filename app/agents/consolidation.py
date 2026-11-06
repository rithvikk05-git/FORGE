"""Combine three agent findings into one human-review-ready assessment.

This component reports policy priority without making an approval decision.
The current graph, API, dashboard, and Excel export remain unchanged until the
later orchestration step.
"""
from __future__ import annotations

from app.config import settings
from app.models import GraphState
from app.policy_engine import assess
from app.schemas import Opportunity
from app.reference_data import matching_reference_ids, matching_reference_records


def consolidate(case: Opportunity, sme_matching: dict | None,
                feasibility: dict | None, risk_assessment: dict | None,
                policy_assessment: dict | None = None) -> dict:
    """Preserve upstream evidence and identify gaps before SME review."""
    sources = {"sme_matching": sme_matching, "feasibility": feasibility,
               "risk_assessment": risk_assessment}
    for name, result in sources.items():
        if isinstance(result, dict) and result.get("opportunity_id") != case.opportunity_id:
            raise ValueError(f"{name} opportunity_id does not match the opportunity")

    policy = (policy_assessment if policy_assessment is not None
              else assess(case, evidence_max_age_days=settings.evidence_max_age_days))
    missing: list[str] = []
    concerns: list[str] = []
    assumptions: list[str] = []
    recommendations = []

    if isinstance(sme_matching, dict):
        recommendations = [item for item in sme_matching.get("recommendations", [])
                           if isinstance(item, dict)]
        if sme_matching.get("status") != "matched" or not recommendations:
            missing.append("available_sme")
            concerns.append(sme_matching.get("message") or "No available SME was recommended.")
    else:
        missing.append("sme_matching_output")

    if isinstance(feasibility, dict):
        missing.extend(feasibility.get("missing_evidence") or [])
        concerns.extend(feasibility.get("concerns") or [])
        if feasibility.get("classification") == "UNCERTAIN":
            concerns.append("Feasibility classification is uncertain and needs human review.")
    else:
        missing.append("feasibility_output")

    if isinstance(risk_assessment, dict):
        missing.extend(risk_assessment.get("missing_evidence") or [])
        assumptions.extend(risk_assessment.get("provisional_assumptions") or [])
        if risk_assessment.get("risk_classification") == "UNCERTAIN":
            concerns.append("Risk classification is uncertain; the overall risk score is incomplete.")
        social = risk_assessment.get("social_impact") or {}
        if social.get("provisional"):
            concerns.append("Social Impact is provisional and needs SME validation.")
    else:
        missing.append("risk_assessment_output")

    concerns.extend(f"Policy blocker: {item}" for item in policy["blockers"])
    if case.possible_existing_opportunity_ids:
        concerns.append("Possible prior opportunities share the customer and practice; exact asset and optimization overlap is unverified: "
                        + ", ".join(case.possible_existing_opportunity_ids))
        missing.append("duplicate_verification")
    missing = list(dict.fromkeys(missing))
    concerns = list(dict.fromkeys(concerns))
    if missing:
        action = "Request missing information and send the assessment to an SME for review."
        status = "NEEDS_INFORMATION"
    elif policy["blockers"]:
        action = "Resolve policy blockers and send the assessment to an SME for review."
        status = "READY_FOR_REVIEW_WITH_BLOCKERS"
    else:
        action = "Send the assessment to the assigned SME for human review."
        status = "READY_FOR_REVIEW"

    return {
        "opportunity_id": case.opportunity_id,
        "opportunity_name": case.opportunity_name,
        "practice": case.practice,
        "recommended_smes": recommendations,
        "feasibility": {
            "score": feasibility.get("feasibility_score") if isinstance(feasibility, dict) else None,
            "classification": feasibility.get("classification", "UNKNOWN") if isinstance(feasibility, dict) else "UNKNOWN",
            "supporting_factors": feasibility.get("supporting_factors", {}) if isinstance(feasibility, dict) else {},
            "concerns": feasibility.get("concerns", []) if isinstance(feasibility, dict) else [],
            "explanation": feasibility.get("explanation") if isinstance(feasibility, dict) else None,
        },
        "risk": risk_assessment if isinstance(risk_assessment, dict) else {
            "overall_risk_score": None, "risk_classification": "UNKNOWN"},
        "policy": {
            "priority": policy["priority"], "risk_score": policy["risk_score"],
            "risk_band": policy["risk_band"], "blockers": policy["blockers"],
            "assigned_sme": policy["assigned_sme"],
        },
        "main_concerns": concerns,
        "supporting_evidence": {
            "risk": risk_assessment.get("supporting_evidence", []) if isinstance(risk_assessment, dict) else [],
            "feasibility": feasibility.get("supporting_factors", {}) if isinstance(feasibility, dict) else {},
            "financial": policy["financial"],
        },
        "missing_information": missing,
        "provisional_assumptions": list(dict.fromkeys(assumptions)),
        "assessment_status": status,
        "recommended_next_action": action,
        "requires_human_review": True,
    }


def run(state: GraphState) -> dict:
    """Validate case input and return a future LangGraph state update."""
    case = Opportunity.model_validate(state["case"])
    result = consolidate(case, state.get("sme_matching"), state.get("feasibility"),
                         state.get("risk_assessment"), state.get("assessment"))
    result["reference_ids"] = {
        name: matching_reference_ids(state.get("reference_data"), name, case)
        for name in ("successful_opportunities", "cost_impact", "technical_impact", "compliance", "form_opportunities")
    }
    result["reference_evidence"] = {
        name: matching_reference_records(state.get("reference_data"), name, case)
        for name in ("successful_opportunities", "cost_impact", "technical_impact", "compliance", "form_opportunities")
    }
    return {"consolidation": result,
            "trace": state.get("trace", []) + ["consolidation: three agent outputs prepared for human review"]}
