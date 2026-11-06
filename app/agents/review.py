
from langgraph.types import interrupt

from app.models import GraphState


def run(state: GraphState) -> dict:
    # This node may restart on resume. Keep all business writes outside it.
    decision = interrupt({"opportunity_id": state["opportunity_id"],
                          "case_version": state["case_version"],
                          "blockers": state["assessment"]["blockers"]})
    status = {"approve": "approved", "reject": "rejected",
              "request_changes": "changes_requested"}[decision["decision"]]
    return {"review_status": status,
            "trace": state.get("trace", []) + ["review: human decision resumed"]}
