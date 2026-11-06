from app.policy_engine import assess
from app.schemas import Opportunity


def test_exact_pipeline_keys_block(valid_case):
    valid_case["pipeline_matches"] = [{"pipeline_id": "PIPE-1", "account_id": "TEST-A",
                                      "asset_group_id": "TEST-ASSET", "optimization_type": "rightsizing"}]
    result = assess(Opportunity.model_validate(valid_case))
    assert result["exact_duplicate_ids"] == ["PIPE-1"]
    assert "EXACT_PIPELINE_DUPLICATE" in result["blockers"]


def test_related_but_nonidentical_keys_are_not_proven_duplicate(valid_case):
    valid_case["pipeline_matches"] = [{"pipeline_id": "PIPE-2", "account_id": "TEST-A",
                                      "asset_group_id": "DIFFERENT-ASSET", "optimization_type": "rightsizing"}]
    result = assess(Opportunity.model_validate(valid_case))
    assert result["exact_duplicate_ids"] == []
    assert "EXACT_PIPELINE_DUPLICATE" not in result["blockers"]
