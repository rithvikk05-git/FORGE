import pytest

from app.repositories import get_approval
from app.schemas import Decision, Opportunity
from app.services import approved_summary, decide, evaluate, put_opportunity


def test_rejected_case_has_no_approved_summary(isolated_store, valid_case):
    version = put_opportunity(Opportunity.model_validate(valid_case))["case_version"]
    evaluate("TEST-001")
    decide("TEST-001", Decision(decision="reject", reviewer_id="demo-governance",
                                reviewer_role="governance", case_version=version,
                                comments="Rejected synthetic test case"))
    with pytest.raises(ValueError, match="approved"):
        approved_summary("TEST-001")


def test_material_revision_invalidates_prior_approval(isolated_store, valid_case):
    version = put_opportunity(Opportunity.model_validate(valid_case))["case_version"]
    evaluate("TEST-001")
    decide("TEST-001", Decision(decision="approve", reviewer_id="demo-sme",
                                reviewer_role="sme", case_version=version,
                                comments="Approved synthetic test case"))
    assert approved_summary("TEST-001")["opportunity_id"] == "TEST-001"
    valid_case["evidence"]["projected_monthly_cost"] = "19000"
    new_version = put_opportunity(Opportunity.model_validate(valid_case))["case_version"]
    assert new_version != version
    assert get_approval("TEST-001") is None
    with pytest.raises(ValueError, match="approved"):
        approved_summary("TEST-001")
