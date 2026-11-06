"""Prepare an internal result after a current human approval and policy recheck."""
from app.models import GraphState


def run(state: GraphState) -> dict:
    case = state["case"]
    assessment = state["assessment"]
    summary = {
        "opportunity_id": state["opportunity_id"],
        "case_version": state["case_version"],
        "opportunity_name": case["opportunity_name"],
        "practice": case["practice"],
        "source_sales_stage": case["source_sales_stage"],
        "customer_savings": assessment["financial"],
        "risk_score": assessment["risk_score"],
        "risk_band": assessment["risk_band"],
        "priority": assessment["priority"],
        "assigned_sme": assessment["assigned_sme"],
        "assigned_sme_name": assessment.get("assigned_sme_name"),
        "sme_match_reason": assessment.get("sme_match_reason"),
        "synthetic_demo": assessment["synthetic_demo"],
        "use": "Internal proof-of-concept assessment only; no external transfer.",
    }
    return {
        "approved_summary": summary,
        "trace": state.get("trace", []) + ["result: approved internal summary prepared"],
    }
