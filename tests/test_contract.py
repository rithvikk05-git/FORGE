from app.policy_engine import assess
from app.schemas import Opportunity


def test_unknown_scope_blocks(valid_case):
    valid_case["contract"]["scope"] = "unknown"
    result = assess(Opportunity.model_validate(valid_case))
    assert "CONTRACT_SCOPE_UNKNOWN" in result["blockers"]
    assert result["priority"] == "HOLD"


def test_excluded_scope_blocks_even_when_verified(valid_case):
    valid_case["contract"]["scope"] = "out_of_scope"
    result = assess(Opportunity.model_validate(valid_case))
    assert "CONTRACT_OUT_OF_SCOPE" in result["blockers"]
    assert result["priority"] == "HOLD"
