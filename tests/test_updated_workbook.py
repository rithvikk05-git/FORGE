"""Integration checks for the private updated 26-column workbook when present."""
import csv
import shutil
from collections import Counter
from pathlib import Path

import pytest
from fastapi import HTTPException
from openpyxl import load_workbook

from app.api import import_local_workbook
from app.policy_engine import assess
from app.repositories import list_cases
from app.schemas import Opportunity
from app.services import put_opportunity
from app.workbook_26 import load_cases

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "data" / "private" / "FORGE_60_Opportunities_26_Column_Agent_Input.xlsx"


def test_updated_workbook_joins_and_aggregate_summary(isolated_store):
    if not PRIVATE.is_file():
        pytest.skip("Private updated workbook is not present")
    shutil.copyfile(PRIVATE, isolated_store.source_xlsx_path)
    cases, practices, stages = load_cases(isolated_store.source_xlsx_path)
    assert len(cases) == len({case.opportunity_id for case in cases}) == 60
    assert sorted(practices.values()) == [10] * 6
    assert stages == Counter({"Stretch": 1, "Won": 19, "Validated": 20,
                              "Qualified": 10, "Noticed": 5, "Identified": 5})
    assert sum(case.evidence is None for case in cases) == 6
    assert sum(bool(case.pipeline_matches) for case in cases) == 0
    assert sum(bool(case.possible_existing_opportunity_ids) for case in cases) > 0
    blockers = Counter(code for case in cases for code in assess(case)["blockers"])
    assert blockers["CONTRACT_SCOPE_UNKNOWN"] == 60
    assert blockers["STALE_OR_FUTURE_EVIDENCE"] == 54
    assert blockers["SME_UNAVAILABLE"] == 27
    result = import_local_workbook()
    assert result["imported"] == 60 and result["source_sheet"] == "Opportunity_Input"
    rows = list_cases()
    assert len(rows) == 60
    assert all(row["case"]["source_system"] == "FORGE_26_workbook" for row in rows)
    with (ROOT / "data" / "opportunity_summary.csv").open(encoding="utf-8", newline="") as handle:
        summary = list(csv.DictReader(handle))
    assert len(summary) == 6 and sum(int(row["total"]) for row in summary) == 60
    assert "opportunity_id" not in summary[0] and "opportunity_name" not in summary[0]


def test_updated_workbook_rejects_broken_evidence_link(tmp_path):
    if not PRIVATE.is_file():
        pytest.skip("Private updated workbook is not present")
    target = tmp_path / "broken.xlsx"
    shutil.copyfile(PRIVATE, target)
    book = load_workbook(target)
    book["Opportunity_Input"]["Y2"] = "MISSING-EVIDENCE-REFERENCE"
    master = book["Master_Consolidated"]
    evidence_column = next(cell.column for cell in master[1] if cell.value == "Evidence ID")
    master.cell(row=2, column=evidence_column).value = "MISSING-EVIDENCE-REFERENCE"
    book.save(target)
    with pytest.raises(ValueError, match="Invalid evidence reference"):
        load_cases(target)


def test_import_rejects_other_catalog(isolated_store, valid_case):
    if not PRIVATE.is_file():
        pytest.skip("Private updated workbook is not present")
    shutil.copyfile(PRIVATE, isolated_store.source_xlsx_path)
    put_opportunity(Opportunity.model_validate(valid_case))
    with pytest.raises(HTTPException) as error:
        import_local_workbook()
    assert error.value.status_code == 409
    assert [row["case"]["opportunity_id"] for row in list_cases()] == ["TEST-001"]


def test_import_rejects_old_workbook_shape(isolated_store):
    if not PRIVATE.is_file():
        pytest.skip("Private updated workbook is not present")
    shutil.copyfile(PRIVATE, isolated_store.source_xlsx_path)
    book = load_workbook(isolated_store.source_xlsx_path)
    book["Opportunity_Input"].title = "Sheet1"
    book.save(isolated_store.source_xlsx_path)
    with pytest.raises(HTTPException) as error:
        import_local_workbook()
    assert error.value.status_code == 422
