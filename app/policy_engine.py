"""Plain Python rules for the synthetic FORGE proof of concept.

Every blocker is a reason a case cannot be approved. A score describes risk;
it never removes a blocker or replaces a human review.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from .schemas import Opportunity, SME

# These are POC weights, not an official company policy.
WEIGHTS = {
    "service_impact": 0.30,
    "financial_uncertainty": 0.25,
    "technical_feasibility": 0.20,
    "capability_fit": 0.15,
    "resource_availability": 0.10,
}


def check_finances(case: Opportunity, now: datetime, max_age_days: int) -> tuple[dict, list[str], bool]:
    """Calculate customer savings only when evidence is current and valid."""
    evidence = case.evidence
    financial = {
        "claimed_monthly_customer_savings": str(case.claimed_monthly_customer_savings)
        if case.claimed_monthly_customer_savings is not None else None,
        "claimed_annual_customer_savings": str(case.claimed_annual_customer_savings)
        if case.claimed_annual_customer_savings is not None else None,
        "validated_monthly_customer_savings": None,
        "validated_annual_customer_savings": None,
        "first_year_net_customer_benefit": None,
        "payback_months": None,
        "unvalidated_implementation_credit": str(-case.source_implementation_cost)
        if case.source_implementation_cost is not None and case.source_implementation_cost < 0 else None,
        "currency": evidence.currency if evidence else None,
        "evidence_ids": [evidence.evidence_id] if evidence else [],
        "assumption": "12 recurring months; no currency conversion",
    }
    if evidence is None:
        return financial, ["MISSING_EVIDENCE"], False

    observed_at = evidence.observed_at
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    age_days = (now - observed_at.astimezone(timezone.utc)).days
    if age_days < 0 or age_days > max_age_days:
        return financial, ["STALE_OR_FUTURE_EVIDENCE"], False
    if not evidence.verified:
        return financial, ["UNVERIFIED_EVIDENCE"], False
    if evidence.projected_monthly_cost > evidence.monthly_baseline:
        return financial, ["FINANCIAL_ARITHMETIC_ANOMALY"], False

    monthly_savings = evidence.monthly_baseline - evidence.projected_monthly_cost
    monthly_net = monthly_savings - evidence.ongoing_incremental_monthly_cost
    financial["validated_monthly_customer_savings"] = str(monthly_savings)
    if evidence.recurring:
        financial["validated_annual_customer_savings"] = str(monthly_savings * 12)
        financial["first_year_net_customer_benefit"] = str(monthly_net * 12 - evidence.implementation_cost)
        if monthly_net > 0:
            financial["payback_months"] = str(
                (evidence.implementation_cost / monthly_net).quantize(Decimal("0.01"))
            )
    return financial, [], True


def check_contract(case: Opportunity) -> list[str]:
    """A missing or unknown contract scope blocks approval."""
    if case.contract and case.contract.scope == "out_of_scope":
        return ["CONTRACT_OUT_OF_SCOPE"]
    if case.contract is None or case.contract.scope == "unknown" or not case.contract.verified:
        return ["CONTRACT_SCOPE_UNKNOWN"]
    return []


def exact_duplicates(case: Opportunity) -> list[str]:
    """Only an exact account + asset + optimization match counts."""
    if not (case.account_id and case.asset_group_id and case.optimization_type):
        return []
    return [
        match.pipeline_id for match in case.pipeline_matches
        if (match.account_id, match.asset_group_id, match.optimization_type) ==
        (case.account_id, case.asset_group_id, case.optimization_type)
    ]


def choose_sme(case: Opportunity) -> SME | None:
    """The importer ranks candidates; use the first eligible specialist."""
    for sme in case.smes:
        if sme.available and sme.practice == case.practice:
            if (not case.required_skill or case.required_skill in sme.skills or
                    sme.matched_optimization == case.required_skill):
                return sme
    return None


def risk_band(score: float) -> str:
    if score < 25:
        return "LOW"
    if score < 50:
        return "MEDIUM"
    if score < 75:
        return "HIGH"
    return "CRITICAL"


def priority_for(score: float, blockers: list[str], monthly_savings: str | None) -> str:
    if blockers:
        return "HOLD"
    if score < 25 and monthly_savings is not None and Decimal(monthly_savings) >= 10000:
        return "P1"
    if score < 50:
        return "P2"
    return "P3"


def assess(case: Opportunity, *, now: datetime | None = None,
           evidence_max_age_days: int = 180) -> dict:
    """Assess one case and return an explanation the API can store."""
    now = now or datetime.now(timezone.utc)
    financial, blockers, evidence_valid = check_finances(case, now, evidence_max_age_days)
    blockers.extend(check_contract(case))

    duplicate_ids = exact_duplicates(case)
    if duplicate_ids:
        blockers.append("EXACT_PIPELINE_DUPLICATE")
    if case.possible_existing_opportunity_ids:
        blockers.append("POSSIBLE_PIPELINE_DUPLICATE_REVIEW_REQUIRED")

    assigned = choose_sme(case)
    if assigned is None:
        blockers.append("SME_UNAVAILABLE")
    if case.service_impact is None or case.service_impact >= 5:
        blockers.append("SERVICE_IMPACT_REVIEW_REQUIRED")
    if case.technical_feasibility is None:
        blockers.append("TECHNICAL_FEASIBILITY_UNKNOWN")
    if case.capability_fit is None:
        blockers.append("CAPABILITY_FIT_UNKNOWN")
    if case.source_sales_stage == "Won":
        blockers.append("HISTORICAL_WON_RECORD")

    # Missing factors receive the highest risk value, five.
    factors = {
        "service_impact": case.service_impact if case.service_impact is not None else 5,
        "financial_uncertainty": 0 if evidence_valid else 5,
        "technical_feasibility": case.technical_feasibility if case.technical_feasibility is not None else 5,
        "capability_fit": case.capability_fit if case.capability_fit is not None else 5,
        "resource_availability": 0 if assigned else 5,
    }
    score = round(20 * sum(WEIGHTS[name] * value for name, value in factors.items()), 2)
    return {
        "policy_version": "poc-2",
        "blockers": blockers,
        "financial": financial,
        "risk_factors": factors,
        "risk_score": score,
        "risk_band": risk_band(score),
        "priority": priority_for(score, blockers, financial["validated_monthly_customer_savings"]),
        "assigned_sme": assigned.sme_id if assigned else None,
        "assigned_sme_name": assigned.name if assigned else None,
        "sme_match_reason": assigned.match_reason if assigned else None,
        "exact_duplicate_ids": duplicate_ids,
        "possible_existing_opportunity_ids": case.possible_existing_opportunity_ids,
        "synthetic_demo": case.synthetic or bool(case.evidence and case.evidence.synthetic)
        or bool(case.contract and case.contract.synthetic),
    }
