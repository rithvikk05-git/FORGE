
from app.models import GraphState
from app.schemas import Opportunity
from app.reference_data import load_reference_data


def run(state: GraphState) -> dict:
    case = Opportunity.model_validate(state["case"])
    return {"case": case.model_dump(mode="json"), "prompt_template": None,
            "reference_data": load_reference_data(current_id=case.opportunity_id),
            "trace": ["intake: validated source fields"]}
