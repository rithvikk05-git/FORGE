
"""Local FastAPI interface for FORGE. OpenAPI is available at /docs."""
from __future__ import annotations

from importlib.util import find_spec
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import FastAPI, Header, HTTPException
from pydantic import ValidationError

from .config import settings
from .db import initialize
from .repositories import get_case, list_cases
from .schemas import Decision, Opportunity, Outcome
from .services import approved_summary, decide, detail, evaluate, metrics, put_opportunity, record_outcome
from .workbook_26 import load_cases as load_26_cases

app = FastAPI(title="FORGE", version="0.1.0", description="Local FinOps opportunity review POC")


@app.get("/health")
def health() -> dict:
    try:
        initialize()
        storage = "ok"
    except Exception as exc:
        storage = f"error: {type(exc).__name__}"
    try:
        with urlopen(settings.qdrant_url.rstrip("/") + "/healthz", timeout=0.4):
            qdrant = "ok"
    except (URLError, TimeoutError, OSError):
        qdrant = "unavailable; exact duplicate checks still work"
    embedding_available = find_spec("sentence_transformers") is not None
    sources_present = settings.source_xlsx_path.is_file() and settings.sme_csv_path.is_file()
    return {"status": "ok" if storage == "ok" and sources_present else "degraded", "sqlite": storage,
            "qdrant": qdrant, "embedding_package_available": embedding_available,
            "qdrant_optional": True,
            "source_workbook_present": settings.source_xlsx_path.is_file(),
            "sme_directory_present": settings.sme_csv_path.is_file(),
            "review_authorization_configured": bool((settings.sme_token and settings.sme_reviewer_id) or
                                                      (settings.governance_token and settings.governance_reviewer_id))}


@app.put("/api/opportunities/{opportunity_id}")
def revise_opportunity(opportunity_id: str, case: Opportunity) -> dict:
    """Revise enrichment of an existing workbook row; never add a 61st ID."""
    current = get_case(opportunity_id)
    if current is None:
        raise HTTPException(404, "Import the 60-row workbook before revising a case")
    original = current[0]
    source_fields = ("opportunity_id", "practice", "opportunity_name", "source_sales_stage", "synthetic",
                     "source_system", "source_file", "source_record_id", "source_sheet", "source_row",
                     "level20", "level30_description", "line_item_name", "line_item_tag",
                     "customer_name", "customer_number", "service_type", "industry",
                     "source_owner_user_name", "source_created_at", "environment", "business_service",
                     "criticality", "rto_minutes", "rpo_minutes", "technical_constraints",
                     "source_baseline_monthly_cost", "source_proposed_monthly_cost", "source_implementation_cost")
    if any(getattr(original, field) != getattr(case, field) for field in source_fields):
        raise HTTPException(409, "Workbook source fields and opportunity ID cannot be changed here")
    if original.source_system != "FORGE_26_workbook":
        raise HTTPException(409, "Only the 60-row workbook is active")
    return put_opportunity(case)


@app.post("/api/opportunities/import")
def import_local_workbook() -> dict:
    """Import only the configured 26-column local workbook."""

    path = settings.source_xlsx_path
    if not path.is_file() or path.stat().st_size == 0:
        raise HTTPException(404, f"Place the private workbook at {path}")
    try:
        cases, practices, stages = load_26_cases(path, settings.sme_csv_path)
    except (OSError, ValueError, ValidationError) as exc:
        raise HTTPException(422, f"Updated workbook validation failed: {exc}") from exc

    source_ids = {case.opportunity_id for case in cases}
    existing = {row["case"]["opportunity_id"]: row["case"] for row in list_cases()}
    foreign_ids = {key for key, value in existing.items()
                   if key not in source_ids and value.get("source_system") != "form"}
    form_collisions = {key for key in source_ids if key in existing
                       and existing[key].get("source_system") == "form"}
    if foreign_ids or form_collisions:
        raise HTTPException(409, "Database contains a different opportunity catalog; use a separate SQLITE_PATH")
    for case in cases:
        put_opportunity(case)
    return {
        "imported": len(cases),
        "practices": dict(practices),
        "source_sales_stages": dict(stages),
        "source_sheet": "Opportunity_Input",
        "synthetic_enrichment_loaded": True,
        "sme_directory_source": settings.sme_csv_path.name,
        "note": "Fictional local POC data. No external transfer.",
    }


@app.post("/api/opportunities/form", status_code=201)
def submit_form_opportunity(case: Opportunity) -> dict:
    """Record a new form opportunity in the same list used by the agents."""
    if get_case(case.opportunity_id) is not None:
        raise HTTPException(409, "Opportunity ID already exists")
    form_case = case.model_copy(update={"source_system": "form", "source_file": None,
                                "source_sheet": None, "source_row": None,
                                "source_record_id": case.opportunity_id})
    return put_opportunity(form_case)


@app.get("/api/opportunities")
def opportunities(practice: str | None = None, stage: str | None = None,
                  risk: str | None = None, status: str | None = None,
                  priority: str | None = None) -> list[dict]:
    rows = list_cases()
    return [r for r in rows if (not practice or r["case"]["practice"] == practice)
            and (not stage or r["case"]["source_sales_stage"] == stage)
            and (not status or r["review_status"] == status)
            and (not risk or r["evaluation"] and r["evaluation"]["risk_band"] == risk)
            and (not priority or r["evaluation"] and r["evaluation"]["priority"] == priority)]


@app.get("/api/reviews")
def reviews() -> list[dict]:
    return [r for r in list_cases() if r["review_status"] == "pending"]


@app.get("/api/metrics")
def portfolio_metrics() -> dict:
    return metrics()


@app.get("/api/opportunities/{opportunity_id}")
def opportunity_detail(opportunity_id: str) -> dict:
    try:
        return detail(opportunity_id)
    except KeyError:
        raise HTTPException(404, "Opportunity not found") from None


@app.post("/api/opportunities/{opportunity_id}/evaluate")
def evaluate_opportunity(opportunity_id: str) -> dict:
    try:
        return evaluate(opportunity_id)
    except KeyError:
        raise HTTPException(404, "Opportunity not found") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/reviews/{opportunity_id}/decision")
def review_decision(opportunity_id: str, decision: Decision,
                    x_reviewer_token: str | None = Header(default=None)) -> dict:
    allowed = {"sme": (settings.sme_token, settings.sme_reviewer_id),
               "governance": (settings.governance_token, settings.governance_reviewer_id)}
    token, reviewer_id = allowed[decision.reviewer_role]
    if not token or not reviewer_id or x_reviewer_token != token or decision.reviewer_id != reviewer_id:
        raise HTTPException(403, "Local reviewer authorization is not configured or token is invalid")
    try:
        return decide(opportunity_id, decision)
    except KeyError:
        raise HTTPException(404, "Opportunity not found") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/opportunities/{opportunity_id}/approved-summary")
def internal_approved_summary(opportunity_id: str) -> dict:
    try:
        return approved_summary(opportunity_id)
    except KeyError:
        raise HTTPException(404, "Opportunity not found") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/opportunities/{opportunity_id}/outcomes")
def submit_outcome(opportunity_id: str, outcome: Outcome) -> dict:
    try:
        return record_outcome(opportunity_id, outcome)
    except KeyError:
        raise HTTPException(404, "Opportunity not found") from None
