from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook

from dashboard.excel_export import TEMPLATE, TemplateUnavailable, generate_excel, safe_filename


def detail(status="pending", approved=False):
    return {
        "case_version": "v1",
        "case": {"opportunity_id": "SYN50-001", "opportunity_name": "Synthetic example",
                 "practice": "Cloud", "source_sales_stage": "Validated", "synthetic": True,
                 "commercial_opportunity_value": None},
        "evaluation": {"case_version": "v1", "review_status": status,
                       "result": {"blockers": [], "risk_score": 10, "risk_band": "LOW",
                                  "priority": "P2", "financial": {"validated_monthly_customer_savings": "200"},
                                  "approved_summary": {"opportunity_id": "SYN50-001"} if approved else None}},
        "approval": {"case_version": "v1", "decision": "approve", "reviewer_id": "demo-sme"} if approved else None,
        "audit_events": [],
    }


def test_missing_template_is_explicit(tmp_path):
    with pytest.raises(TemplateUnavailable):
        generate_excel(detail(), template_path=tmp_path / "missing.xlsx")


def test_draft_preserves_template_formulas_and_merges(tmp_path):
    template = tmp_path / "brief.xlsx"
    workbook = Workbook()
    ws = workbook.active
    ws.title = "Sales Brief"
    ws["B6"] = "=C13"
    ws.merge_cells("B16:I19")
    ws.merge_cells("B22:I27")
    workbook.save(template)
    exported = load_workbook(BytesIO(generate_excel(detail(), template_path=template)))
    brief = exported["Sales Brief"]
    assert brief["B3"].value.startswith("DRAFT - INTERNAL POC ONLY")
    assert brief["B6"].value == "=C13"
    assert brief["C11"].value == "Validated"
    assert brief["C12"].value is None
    assert brief["C13"].value is None
    assert brief["G11"].value is None
    assert "B16:I19" in {str(r) for r in brief.merged_cells.ranges}
    assert "FORGE Assessment" in exported.sheetnames


def test_approved_label_requires_current_approval(tmp_path):
    template = tmp_path / "brief.xlsx"
    workbook = Workbook()
    workbook.active.title = "Sales Brief"
    workbook.save(template)
    exported = load_workbook(BytesIO(generate_excel(detail(status="approved", approved=True), template_path=template)))
    assert exported["Sales Brief"]["B3"].value.startswith("APPROVED INTERNAL ASSESSMENT")
    assert safe_filename("A / B") == "A_B_FORGE_internal_assessment.xlsx"


def test_real_sanitized_template_structure_and_export():
    if not TEMPLATE.is_file() or TEMPLATE.stat().st_size == 0:
        pytest.skip("Sanitized sales template is not present")
    source = load_workbook(TEMPLATE)
    assert source.sheetnames == ["Sales Brief"]
    sheet = source["Sales Brief"]
    assert sheet["B6"].value == '=IF(C13="","",C13)'
    assert sheet["C9"].value is None
    assert sheet["G11"].value is None
    assert "B16:I19" in {str(r) for r in sheet.merged_cells.ranges}
    exported = load_workbook(BytesIO(generate_excel(detail(), template_path=TEMPLATE)))
    assert exported["Sales Brief"]["C11"].value == "Validated"
    assert exported["Sales Brief"]["B6"].value == '=IF(C13="","",C13)'
    assert exported.sheetnames == ["Sales Brief", "FORGE Assessment"]
