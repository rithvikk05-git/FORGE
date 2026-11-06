"""Agent 2: explain technical and delivery feasibility using existing POC rules.

The score inverts the existing 0–5 policy risk factors and weights. Recovery
targets and written constraints are reported for review because FORGE has no
policy threshold for converting them into a numeric penalty.
"""
from __future__ import annotations

from app.models import GraphState
from app.policy_engine import WEIGHTS, choose_sme, risk_band
from app.schemas import Opportunity
from app.reference_data import matching_reference_ids, matching_reference_records

FACTORS = ("service_impact", "technical_feasibility", "capability_fit", "resource_availability")
FEASIBILITY_BY_RISK = {
    "LOW": "HIGH",
    "MEDIUM": "MODERATE",
    "HIGH": "LOW",
    "CRITICAL": "VERY_LOW",
}


def assess_feasibility(case: Opportunity, sme_matching: dict | None) -> dict:
    """Return a conservative 0–100 feasibility assessment for one case."""
    if not isinstance(sme_matching, dict):
        sme_matching = None
    concerns: list[str] = []
    missing_evidence: list[str] = []
    policy_sme = choose_sme(case)

    # Use Agent 1 when supplied. A stored case SME is a provisional fallback
    # when the agent result has not yet been added to the graph.
    recommendations = []
    if sme_matching is None:
        missing_evidence.append("sme_matching_output")
        concerns.append("SME Matching Agent output is missing; stored case candidates are provisional.")
        has_sme = policy_sme is not None
    else:
        raw_recommendations = sme_matching.get("recommendations")
        if isinstance(raw_recommendations, list):
            recommendations = [
                item for item in raw_recommendations
                if isinstance(item, dict) and isinstance(item.get("sme_id"), str)
                and item["sme_id"]
                and item.get("availability_status") in {"Available", "Partially Available"}
            ]
        has_sme = sme_matching.get("status") == "matched" and bool(recommendations)
        if sme_matching.get("status") == "directory_unavailable":
            missing_evidence.append("sme_directory")
            concerns.append("Synthetic SME directory is unavailable; resource capacity is unconfirmed.")
        elif not has_sme:
            missing_evidence.append("available_sme")
            concerns.append("No available SME was recommended; the existing policy requires SME availability.")
            if policy_sme is not None:
                concerns.append("Stored case candidates and SME Matching Agent output disagree; review the source data.")
        if has_sme and policy_sme is None:
            concerns.append("The recommendation is absent from stored case candidates; policy may hold until the case is refreshed.")

    input_values = {
        "service_impact": case.service_impact,
        "technical_feasibility": case.technical_feasibility,
        "capability_fit": case.capability_fit,
    }
    for name, value in input_values.items():
        if value is None:
            missing_evidence.append(name)
            concerns.append(f"{name.replace('_', ' ').capitalize()} has not been established.")

    # Existing policy treats unknown 0–5 factors as 5 and SME availability
    # as 0 when confirmed or 5 when unavailable.
    factor_values = {
        name: value if value is not None else 5
        for name, value in input_values.items()
    }
    factor_values["resource_availability"] = 0 if has_sme else 5
    total_weight = sum(WEIGHTS[name] for name in FACTORS)
    weighted_sum = sum(WEIGHTS[name] * factor_values[name] for name in FACTORS)
    weighted_risk = 20 * weighted_sum / total_weight
    feasibility_score = round(100 - weighted_risk, 2)
    band = risk_band(weighted_risk)

    if case.service_impact is not None and case.service_impact >= 5:
        concerns.append("Critical service impact requires review under the existing policy.")
    if case.technical_constraints:
        concerns.append(f"Documented technical constraint needs delivery review: {case.technical_constraints}")
    if case.rto_minutes is not None or case.rpo_minutes is not None:
        concerns.append("Recovery targets need delivery validation; no POC scoring threshold is defined.")

    uncertain = bool(missing_evidence) or (has_sme and policy_sme is None)
    classification = "UNCERTAIN" if uncertain else FEASIBILITY_BY_RISK[band]
    weights = {name: WEIGHTS[name] for name in FACTORS}
    explanation = (
        f"{feasibility_score}/100 = 100 - 20 × ({weighted_sum:.2f} / {total_weight:.2f}) "
        "using the existing 0–5 policy factors and weights. Unknown factors count as 5. "
        "The score is advisory; policy blockers and human review remain authoritative."
    )
    if uncertain:
        reasons = missing_evidence or ["SME recommendation needs reconciliation"]
        explanation += " Classification is UNCERTAIN because: " + ", ".join(reasons) + "."
    else:
        explanation += f" Classification {classification} reverses the existing {band} risk band."
    return {
        "opportunity_id": case.opportunity_id,
        "feasibility_score": feasibility_score,
        "classification": classification,
        "supporting_factors": {
            "policy_factor_values": factor_values,
            "policy_weights": weights,
            "risk_band_for_feasibility_factors": band,
            "environment": case.environment,
            "criticality": case.criticality,
            "recommended_sme_ids": [item["sme_id"] for item in recommendations],
            "stored_case_sme_id": policy_sme.sme_id if policy_sme else None,
            "delivery_constraints": {
                "technical_constraints": case.technical_constraints,
                "rto_minutes": case.rto_minutes,
                "rpo_minutes": case.rpo_minutes,
            },
        },
        "concerns": concerns,
        "missing_evidence": missing_evidence,
        "explanation": explanation,
    }


def run(state: GraphState) -> dict:
    """Validate graph input and return this agent's future state update."""
    case = Opportunity.model_validate(state["case"])
    result = assess_feasibility(case, state.get("sme_matching"))
    result["reference_ids"] = {
        name: matching_reference_ids(state.get("reference_data"), name, case)
        for name in ("technical_impact", "successful_opportunities", "cost_impact", "form_opportunities")
    }
    result["reference_evidence"] = {
        name: matching_reference_records(state.get("reference_data"), name, case)
        for name in ("technical_impact", "successful_opportunities", "cost_impact", "form_opportunities")
    }
    return {
        "feasibility": result,
        "trace": state.get("trace", []) + ["feasibility: policy factors and delivery constraints reviewed"],
    }
