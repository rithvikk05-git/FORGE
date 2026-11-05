"""Run the complete deterministic policy for one validated case."""
from app.config import settings
from app.models import GraphState
from app.policy_engine import assess
from app.schemas import Opportunity


def run(state: GraphState) -> dict:
    case = Opportunity.model_validate(state["case"])
    result = assess(case, evidence_max_age_days=settings.evidence_max_age_days)
    return {
        "assessment": result,
        "trace": state.get("trace", []) + ["assessment: policy checks and scoring complete"],
    }
