
"""Small shared state vocabulary for the workflow."""
from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    opportunity_id: str
    case: dict[str, Any]
    case_version: str
    prompt_template: str | None
    reference_data: dict[str, list[dict[str, Any]]]
    assessment: dict[str, Any]
    sme_matching: dict[str, Any]
    feasibility: dict[str, Any]
    risk_assessment: dict[str, Any]
    consolidation: dict[str, Any]
    review_status: str
    approval: dict[str, Any] | None
    approved_summary: dict[str, Any] | None
    trace: list[str]


REVIEW_PENDING = "pending"
REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"
REVIEW_CHANGES = "changes_requested"
