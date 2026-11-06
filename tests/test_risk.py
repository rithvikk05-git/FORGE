from datetime import datetime, timezone
from decimal import Decimal

from app.policy_engine import assess
from app.schemas import Contract, Evidence, Opportunity, SME


def base_case(**changes):
    values = dict(opportunity_id="DEMO-1", practice="Cloud", opportunity_name="Synthetic cloud review",
                  source_sales_stage="Identified", synthetic=True)
    values.update(changes)
    return Opportunity(**values)


def test_missing_evidence_and_scope_are_hold():
    result = assess(base_case())
    assert result["priority"] == "HOLD"
    assert "MISSING_EVIDENCE" in result["blockers"]
    assert "CONTRACT_SCOPE_UNKNOWN" in result["blockers"]
    assert result["financial"]["validated_monthly_customer_savings"] is None


def test_supported_savings_are_distinct_from_commercial_value():
    case = base_case(
        evidence=Evidence(evidence_id="E-1", observed_at=datetime.now(timezone.utc),
                          monthly_baseline=Decimal("30000"), projected_monthly_cost=Decimal("15000"),
                          currency="USD", source="synthetic demo", verified=True, synthetic=True,
                          implementation_cost=Decimal("3000")),
        contract=Contract(contract_id="C-1", scope="in_scope", verified=True, synthetic=True),
        smes=[SME(sme_id="demo-sme", practice="Cloud", available=True, synthetic=True)],
        service_impact=0, technical_feasibility=0, capability_fit=0,
        commercial_opportunity_value=Decimal("8000"), commercial_currency="USD")
    result = assess(case)
    assert result["blockers"] == []
    assert result["financial"]["validated_monthly_customer_savings"] == "15000"
    assert result["financial"]["validated_annual_customer_savings"] == "180000"
    assert case.commercial_opportunity_value != Decimal(result["financial"]["validated_monthly_customer_savings"])
    assert result["priority"] == "P1"


def test_won_is_history_only():
    result = assess(base_case(source_sales_stage="Won"))
    assert "HISTORICAL_WON_RECORD" in result["blockers"]
