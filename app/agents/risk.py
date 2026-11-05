"""Agent 3: four explainable risk dimensions for human review.

This provisional score is separate from the existing policy score and blockers.
"""
from __future__ import annotations

from app.config import settings
from app.models import GraphState
from app.policy_engine import WEIGHTS, assess, risk_band
from app.schemas import Opportunity
from app.reference_data import matching_reference_ids, matching_reference_records

# No approved four-dimension formula exists. Keep these POC weights together.
DIMENSION_WEIGHTS = {
    "cost_impact": 0.25, "feasibility_impact": 0.25,
    "technical_impact": 0.25, "social_impact": 0.25,
}
SOCIAL_LEVELS = (
    "No identifiable disruption", "Negligible disruption", "Limited disruption",
    "Moderate disruption", "Significant disruption", "Severe or widespread disruption",
)


def calculate_social_impact(case: Opportunity) -> dict:
    """Replace this provisional service-impact proxy when a formula is approved.

    The current schema has no affected-user, downtime, or operational-change
    measure. Protected demographic characteristics must never be used here.
    """
    if case.service_impact is None:
        return {
            "score": None, "classification": "UNKNOWN", "source_factors": {},
            "explanation": "No direct social evidence or service_impact proxy is available.",
            "provisional": True, "confidence": "UNKNOWN",
            "evidence_limitations": ["Affected users, downtime, and operational change are not recorded."],
            "requires_sme_validation": True,
        }
    return {
        "score": case.service_impact,
        "classification": SOCIAL_LEVELS[case.service_impact],
        "source_factors": {"service_impact": case.service_impact},
        "explanation": "Existing service_impact is used as a provisional disruption proxy.",
        "provisional": True, "confidence": "LOW",
        "evidence_limitations": [
            "Service impact does not directly measure affected users, downtime, or social outcomes."
        ],
        "requires_sme_validation": True,
    }


def _dimension(score: float | None, sources: dict, explanation: str) -> dict:
    return {"score": round(score, 2) if score is not None else None,
            "source_factors": sources, "explanation": explanation}


def assess_risk(case: Opportunity, sme_matching: dict | None,
                feasibility: dict | None, policy_assessment: dict | None = None) -> dict:
    """Use each policy factor once and withhold totals for unsupported inputs."""
    for name, result in (("sme_matching", sme_matching), ("feasibility", feasibility)):
        if isinstance(result, dict) and result.get("opportunity_id") != case.opportunity_id:
            raise ValueError(f"{name} opportunity_id does not match the opportunity")

    policy = (policy_assessment if policy_assessment is not None
              else assess(case, evidence_max_age_days=settings.evidence_max_age_days))
    missing: list[str] = []
    evidence: list[str] = []

    # The existing financial factor measures evidence quality, not cost size.
    valid_finances = policy["financial"]["validated_monthly_customer_savings"] is not None
    cost_score = policy["risk_factors"]["financial_uncertainty"] if valid_finances else None
    if valid_finances:
        evidence.extend(policy["financial"]["evidence_ids"])
    else:
        missing.append("validated_financial_evidence")
    cost = _dimension(cost_score,
                      {"financial_uncertainty": cost_score} if cost_score is not None else {},
                      "Financial uncertainty measures cost evidence quality; cost magnitude is unscored.")

    # Do not use the Feasibility Agent's total as a factor: it already contains
    # service and technical inputs that belong to the other dimensions.
    matching_known = isinstance(sme_matching, dict) and (
        sme_matching.get("status") == "no_match"
        or (sme_matching.get("status") == "matched"
            and isinstance(sme_matching.get("recommendations"), list)
            and bool(sme_matching["recommendations"]))
    )
    feasibility_value = feasibility.get("feasibility_score") if isinstance(feasibility, dict) else None
    feasibility_known = isinstance(feasibility_value, (int, float)) and 0 <= feasibility_value <= 100
    if case.capability_fit is None:
        missing.append("capability_fit")
    if not matching_known:
        missing.append("sme_matching_output")
    if not feasibility_known:
        missing.append("feasibility_output")
    if case.capability_fit is not None and matching_known and feasibility_known:
        resource = 0 if sme_matching["status"] == "matched" else 5
        feasibility_score = (
            WEIGHTS["capability_fit"] * case.capability_fit
            + WEIGHTS["resource_availability"] * resource
        ) / (WEIGHTS["capability_fit"] + WEIGHTS["resource_availability"])
        feasibility_sources = {"capability_fit": case.capability_fit,
                               "resource_availability": resource,
                               "feasibility_agent_score": feasibility["feasibility_score"]}
        if resource == 5:
            missing.append("available_sme")
    else:
        feasibility_score = None
        feasibility_sources = {}
    feasibility_dimension = _dimension(
        feasibility_score, feasibility_sources,
        "Capability fit and known SME availability use their existing relative policy weights (0.15 and 0.10). "
        "The Feasibility Agent total is context only, avoiding duplicate service and technical factors.")

    technical_score = case.technical_feasibility
    if technical_score is None:
        missing.append("technical_feasibility")
    technical = _dimension(technical_score,
                           {"technical_feasibility": technical_score} if technical_score is not None else {},
                           "Existing technical_feasibility factor; recovery targets have no scoring threshold.")

    social = calculate_social_impact(case)
    social_score = social.get("score")
    if not isinstance(social_score, (int, float)) or not 0 <= social_score <= 5:
        social_score = None
        missing.append("social_impact_evidence")
    if social_score is not None:
        evidence.append("service_impact proxy" if social["source_factors"].get("service_impact") is not None
                        else "direct social impact evidence")

    scores = {"cost_impact": cost["score"], "feasibility_impact": feasibility_dimension["score"],
              "technical_impact": technical["score"], "social_impact": social_score}
    if all(score is not None for score in scores.values()):
        total = round(20 * sum(DIMENSION_WEIGHTS[name] * score for name, score in scores.items()), 2)
        classification = risk_band(total)
        formula = "20 x (" + " + ".join(
            f"{DIMENSION_WEIGHTS[name]:.2f} x {scores[name]:g}" for name in DIMENSION_WEIGHTS
        ) + f") = {total}/100."
    else:
        total = None
        classification = "UNCERTAIN"
        formula = "Overall score withheld because one or more dimensions lack supported evidence."

    drivers = [f"{name}: {score}/5" for name, score in scores.items() if score is not None and score > 0]
    drivers.extend(f"Policy blocker: {blocker}" for blocker in policy["blockers"])
    assumptions = [
        "PROVISIONAL: four dimensions have equal 25% weights; no approved four-dimension formula exists.",
        "Cost Impact uses financial evidence uncertainty, not monetary exposure; no cost-magnitude thresholds exist.",
        "Feasibility Impact uses capability fit and SME availability; the Feasibility Agent total is not added again.",
    ]
    if social.get("provisional"):
        assumptions.append("PROVISIONAL: Social Impact uses service_impact as a disruption proxy pending SME validation.")
    return {
        "opportunity_id": case.opportunity_id,
        "overall_risk_score": total, "risk_classification": classification,
        "cost_impact": cost, "feasibility_impact": feasibility_dimension,
        "technical_impact": technical, "social_impact": social,
        "dimension_weights": DIMENSION_WEIGHTS.copy(),
        "scoring_explanation": formula + " Higher scores mean greater risk. Existing policy score and blockers remain separate.",
        "key_risk_drivers": drivers, "supporting_evidence": evidence,
        "missing_evidence": list(dict.fromkeys(missing)),
        "provisional_assumptions": assumptions,
        "requires_human_review": True,
    }


def run(state: GraphState) -> dict:
    """Validate input and return a future LangGraph state update."""
    case = Opportunity.model_validate(state["case"])
    result = assess_risk(case, state.get("sme_matching"), state.get("feasibility"),
                         state.get("assessment"))
    result["reference_ids"] = {
        name: matching_reference_ids(state.get("reference_data"), name, case)
        for name in ("cost_impact", "technical_impact", "compliance", "successful_opportunities")
    }
    result["reference_evidence"] = {
        name: matching_reference_records(state.get("reference_data"), name, case)
        for name in ("cost_impact", "technical_impact", "compliance", "successful_opportunities")
    }
    return {"risk_assessment": result,
            "trace": state.get("trace", []) + ["risk: four dimensions assessed for human review"]}
