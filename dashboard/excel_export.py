"""Fill the supplied, sanitized sales brief without changing its layout or formulas."""
from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

TEMPLATE = Path(__file__).resolve().parent / "templates" / "sales_opportunity_template.xlsx"
MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
STAGES = "Identified,Noticed,Qualified,Validated,Won,Lost,Stretch"


class TemplateUnavailable(RuntimeError):
    """The user's real formatted workbook has not been copied into the repo."""


def safe_filename(opportunity_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", opportunity_id).strip("_")[:80]
    return f"{safe or 'opportunity'}_FORGE_internal_assessment.xlsx"


def _normalized(value: Any) -> dict:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if not isinstance(value, Mapping):
        raise TypeError("Expected the API opportunity detail mapping")
    case = value.get("case")
    evaluation = value.get("evaluation") or {}
    assessment = evaluation.get("result") or {}
    approval = value.get("approval") or {}
    if not isinstance(case, Mapping) or not case.get("opportunity_id"):
        raise ValueError("Opportunity detail must include a case with opportunity_id")
    version = value.get("case_version")
    approved = bool(evaluation.get("review_status") == "approved" and
                    approval.get("decision") == "approve" and
                    approval.get("case_version") == version and
                    evaluation.get("case_version") == version and
                    not assessment.get("blockers") and assessment.get("approved_summary"))
    return {"case": dict(case), "assessment": dict(assessment), "approval": dict(approval),
            "evaluation": dict(evaluation), "version": version, "approved": approved,
            "audit_events": value.get("audit_events") or [], "outcomes": value.get("outcomes") or []}


def _add_assessment(workbook, data: dict) -> None:
    if "FORGE Assessment" in workbook.sheetnames:
        del workbook["FORGE Assessment"]
    ws = workbook.create_sheet("FORGE Assessment")
    case, a, approval = data["case"], data["assessment"], data["approval"]
    status = "APPROVED INTERNAL ASSESSMENT" if data["approved"] else "DRAFT - INTERNAL POC ONLY"
    ws.append(["FORGE ASSESSMENT", status])
    ws.append(["Opportunity ID", case["opportunity_id"]])
    ws.append(["Case version", data["version"]])
    ws.append(["Source system", case.get("source_system")])
    ws.append(["Source file / sheet / row", " / ".join(str(x or "") for x in
               (case.get("source_file"), case.get("source_sheet"), case.get("source_row")))])
    ws.append(["Source sales stage", case.get("source_sales_stage")])
    ws.append(["FORGE review status", data["evaluation"].get("review_status") or "not evaluated"])
    ws.append(["Data provenance", "SYNTHETIC DEMO / UNVERIFIED REAL-WORLD INPUTS" if
               (case.get("synthetic") or a.get("synthetic_demo")) else "SOURCE RECORD; enrichment unverified unless evidence says otherwise"])
    ws.append(["Customer request", case.get("customer_request")])
    ws.append(["Practice", case.get("practice")])
    ws.append(["Technical classification", case.get("level30_description")])
    ws.append(["Evidence ID", (case.get("evidence") or {}).get("evidence_id")])
    ws.append(["Evidence observed at", (case.get("evidence") or {}).get("observed_at")])
    ws.append(["Evidence source", (case.get("evidence") or {}).get("source")])
    ws.append(["Contract scope", (case.get("contract") or {}).get("scope") or "UNKNOWN"])
    ws.append(["Exact duplicate IDs", ", ".join(a.get("exact_duplicate_ids") or [])])
    ws.append(["Possible prior opportunity IDs", ", ".join(a.get("possible_existing_opportunity_ids") or [])])
    ws.append(["Risk score", a.get("risk_score")])
    ws.append(["Risk band", a.get("risk_band")])
    for factor, score in (a.get("risk_factors") or {}).items():
        ws.append([f"Risk: {factor}", score])
    ws.append(["Priority", a.get("priority")])
    ws.append(["Assigned SME", a.get("assigned_sme")])
    for key, value in (a.get("financial") or {}).items():
        ws.append([f"Financial: {key}", ", ".join(value) if isinstance(value, list) else value])
    ws.append(["Commercial opportunity value", case.get("commercial_opportunity_value")])
    ws.append(["Commercial currency", case.get("commercial_currency")])
    ws.append(["Policy blockers", ", ".join(a.get("blockers") or []) or "None recorded"])
    ws.append(["Reviewer", approval.get("reviewer_id")])
    ws.append(["Review decision", approval.get("decision")])
    ws.append(["Review timestamp", approval.get("decided_at")])
    ws.append(["Reviewer comments", approval.get("comments")])
    ws.append(["Audit event IDs", ", ".join(str(item.get("event_id")) for item in data["audit_events"])])
    ws.append(["Disclaimer", "Internal POC assessment only. Synthetic entries are demonstration data; no external transfer or customer proposal."])
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 90
    ws.freeze_panes = "B2"
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="17365D")
    for row in ws.iter_rows(min_row=2, max_col=2):
        row[0].font = Font(bold=True)
        row[1].alignment = Alignment(wrap_text=True, vertical="top")


def generate_excel(opportunity_result: Mapping | Any, *, template_path: Path | None = None) -> bytes:
    """Return XLSX bytes from the same API detail object shown in the dashboard."""
    data = _normalized(opportunity_result)
    path = template_path or TEMPLATE
    if not path.is_file() or path.stat().st_size == 0:
        raise TemplateUnavailable(f"Copy the real sanitized sales template to {path}")
    try:
        workbook = load_workbook(path)
    except Exception as exc:
        raise TemplateUnavailable(f"Cannot open the sales template at {path}: {exc}") from exc
    if "Sales Brief" not in workbook.sheetnames:
        raise TemplateUnavailable("Template must contain the 'Sales Brief' worksheet")
    ws = workbook["Sales Brief"]
    case, a = data["case"], data["assessment"]
    status = "APPROVED INTERNAL ASSESSMENT" if data["approved"] else "DRAFT - INTERNAL POC ONLY"
    ws["B2"] = "FORGE INTERNAL OPPORTUNITY ASSESSMENT"
    ws["G2"] = case["opportunity_id"]
    ws["B3"] = status + (" | SYNTHETIC DEMO" if case.get("synthetic") or a.get("synthetic_demo") else "")
    ws["C9"] = case["opportunity_id"]
    ws["C10"] = case.get("opportunity_name")
    ws["C11"] = case.get("source_sales_stage")
    ws["C12"] = case.get("customer_name")  # Present only in the updated synthetic workbook.
    ws["C13"] = float(case["commercial_opportunity_value"]) if case.get("commercial_opportunity_value") is not None else None
    ws["E9"] = a.get("assigned_sme")
    for address in ("E10", "E11", "E12", "E13", "G9", "I9", "G10", "I10", "G11", "I11", "G12", "I12", "G13", "I13"):
        ws[address] = None
    ws["B16"] = case.get("customer_request") or case.get("level30_description") or case.get("opportunity_name")
    trace = a.get("trace") or []
    ws["B22"] = "\n".join(str(item) for item in trace) or "No progress recorded."
    for dv in list(ws.data_validations.dataValidation):
        if "C11" in dv:
            ws.data_validations.dataValidation.remove(dv)
    stage_validation = DataValidation(type="list", formula1=f'"{STAGES}"', allow_blank=True)
    ws.add_data_validation(stage_validation)
    stage_validation.add(ws["C11"])
    _add_assessment(workbook, data)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
