from app.repositories import audit_events, get_evaluation
from app.schemas import Decision, Opportunity
from app.services import decide, evaluate, put_opportunity


def test_checkpoint_resume_and_idempotent_evaluate(isolated_store, valid_case):
    version = put_opportunity(Opportunity.model_validate(valid_case))["case_version"]
    first = evaluate("TEST-001")
    second = evaluate("TEST-001")
    assert first == second
    assert len([e for e in audit_events("TEST-001") if e["event_type"] == "EVALUATED"]) == 1
    assert isolated_store.checkpoint_path.is_file()
    resumed = decide("TEST-001", Decision(decision="approve", reviewer_id="demo-sme",
                                           reviewer_role="sme", case_version=version,
                                           comments="Approved after checkpoint reopen"))
    assert resumed["review_status"] == "approved"
    assert get_evaluation("TEST-001")["result"]["approved_summary"] is not None


def test_request_changes_requires_revised_case(isolated_store, valid_case):
    version = put_opportunity(Opportunity.model_validate(valid_case))["case_version"]
    evaluate("TEST-001")
    result = decide("TEST-001", Decision(decision="request_changes", reviewer_id="demo-governance",
                                          reviewer_role="governance", case_version=version,
                                          comments="Provide revised evidence"))
    assert result["review_status"] == "changes_requested"
    valid_case["opportunity_name"] = "Revised synthetic test case"
    new_version = put_opportunity(Opportunity.model_validate(valid_case))["case_version"]
    assert new_version != version
    assert evaluate("TEST-001")["review_status"] == "pending"
