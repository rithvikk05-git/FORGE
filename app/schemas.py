
"""Validated API and source contracts. Missing fields stay unknown."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PRACTICES = (
    "Applications, Data & AI", "Cloud", "Core Enterprise and z/OS",
    "Digital Workspace Services", "Network & Edge", "Security & Resiliency",
)
STAGES = ("Identified", "Noticed", "Qualified", "Validated", "Won", "Lost", "Stretch")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Evidence(StrictModel):
    evidence_id: str = Field(min_length=1)
    observed_at: datetime
    monthly_baseline: Decimal = Field(gt=0)
    projected_monthly_cost: Decimal = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    source: str = Field(min_length=1)
    verified: bool = False
    synthetic: bool = False
    recurring: bool = True
    implementation_cost: Decimal = Field(default=Decimal("0"), ge=0)
    ongoing_incremental_monthly_cost: Decimal = Field(default=Decimal("0"), ge=0)
    evidence_type: str | None = None
    confidence_score: float | None = Field(default=None, ge=0, le=1)


class Contract(StrictModel):
    contract_id: str = Field(min_length=1)
    scope: Literal["in_scope", "out_of_scope", "unknown"] = "unknown"
    verified: bool = False
    synthetic: bool = False


class PipelineMatch(StrictModel):
    pipeline_id: str = Field(min_length=1)
    account_id: str
    asset_group_id: str
    optimization_type: str
    synthetic: bool = False


class SME(StrictModel):
    sme_id: str = Field(min_length=1)
    practice: str
    skills: list[str] = Field(default_factory=list)
    available: bool = False
    synthetic: bool = False
    # Optional profile fields from the synthetic 60-person CSV. Older tests and
    # manually entered SMEs still work with only the five fields above.
    name: str | None = None
    specialization: str | None = None
    availability_status: str | None = None
    utilization_percent: int | None = Field(default=None, ge=0, le=100)
    rating_points: float | None = Field(default=None, ge=0, le=5)
    experience_years: int | None = Field(default=None, ge=0)
    service_type_expertise: str | None = None
    industry_expertise: str | None = None
    match_reason: str | None = None
    matched_optimization: str | None = None


class Opportunity(StrictModel):
    opportunity_id: str = Field(min_length=1)
    practice: str
    opportunity_name: str = Field(min_length=1)
    source_sales_stage: str
    source_system: str = "manual"
    source_file: str | None = None
    source_record_id: str | None = None
    source_sheet: str | None = None
    source_row: int | None = Field(default=None, ge=2)
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    synthetic: bool = False
    account_id: str | None = None
    asset_group_id: str | None = None
    optimization_type: str | None = None
    required_skill: str | None = None
    customer_request: str | None = None
    level20: str | None = None
    level30_description: str | None = None
    line_item_name: str | None = None
    line_item_tag: str | None = None
    customer_name: str | None = None
    customer_number: str | None = None
    service_type: str | None = None
    industry: str | None = None
    source_owner_user_name: str | None = None
    source_created_at: datetime | None = None
    environment: str | None = None
    business_service: str | None = None
    criticality: str | None = None
    rto_minutes: int | None = Field(default=None, ge=0)
    rpo_minutes: int | None = Field(default=None, ge=0)
    technical_constraints: str | None = None
    source_baseline_monthly_cost: Decimal | None = Field(default=None, ge=0)
    source_proposed_monthly_cost: Decimal | None = Field(default=None, ge=0)
    # Signed source value: a negative amount is an unverified one-time credit.
    source_implementation_cost: Decimal | None = None
    claimed_monthly_customer_savings: Decimal | None = Field(default=None, ge=0)
    claimed_annual_customer_savings: Decimal | None = Field(default=None, ge=0)
    evidence: Evidence | None = None
    contract: Contract | None = None
    pipeline_matches: list[PipelineMatch] = Field(default_factory=list)
    possible_existing_opportunity_ids: list[str] = Field(default_factory=list)
    smes: list[SME] = Field(default_factory=list)
    service_impact: int | None = Field(default=None, ge=0, le=5)
    technical_feasibility: int | None = Field(default=None, ge=0, le=5)
    capability_fit: int | None = Field(default=None, ge=0, le=5)
    commercial_opportunity_value: Decimal | None = Field(default=None, ge=0)
    commercial_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")

    @field_validator("practice")
    @classmethod
    def check_practice(cls, value: str) -> str:
        if value not in PRACTICES:
            raise ValueError(f"practice must be one of {PRACTICES}")
        return value

    @field_validator("source_sales_stage")
    @classmethod
    def check_stage(cls, value: str) -> str:
        if value not in STAGES:
            raise ValueError(f"source_sales_stage must be one of {STAGES}")
        return value

    @model_validator(mode="after")
    def commercial_unit(self) -> "Opportunity":
        if self.commercial_opportunity_value is not None and self.commercial_currency is None:
            raise ValueError("commercial_currency is required with commercial_opportunity_value")
        return self


class Decision(StrictModel):
    decision: Literal["approve", "reject", "request_changes"]
    reviewer_id: str = Field(min_length=1)
    reviewer_role: Literal["sme", "governance"]
    case_version: str = Field(min_length=1)
    comments: str = Field(min_length=1)


class Outcome(StrictModel):
    outcome: str = Field(min_length=1)
    realized_customer_savings: Decimal | None = Field(default=None, ge=0)
    notes: str = ""
