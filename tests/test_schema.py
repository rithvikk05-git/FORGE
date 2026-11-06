import pytest
from pydantic import ValidationError

from app.schemas import Opportunity


def test_unknown_sales_stage_is_rejected():
    with pytest.raises(ValidationError):
        Opportunity(opportunity_id="X", practice="Cloud", opportunity_name="Example",
                    source_sales_stage="SME Approved")


def test_workbook_stage_does_not_imply_review():
    case = Opportunity(opportunity_id="X", practice="Cloud", opportunity_name="Example",
                       source_sales_stage="Validated")
    assert case.source_sales_stage == "Validated"
    assert not hasattr(case, "review_status")
