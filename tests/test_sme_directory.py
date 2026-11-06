"""Checks for the supplied synthetic SME directory and live case matching."""
import csv
import shutil
from collections import Counter
from pathlib import Path

import pytest

from app.policy_engine import assess
from app.api import import_local_workbook
from app.schemas import Decision
from app.services import approved_summary, decide, detail, evaluate
from app.sme_directory import load_directory, matching_smes
from app.workbook_26 import load_cases
from dashboard.excel_export import generate_excel

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "data/private/FORGE_60_Opportunities_26_Column_Agent_Input.xlsx"
SME_CSV = ROOT / "data/private/Kyndryl_Synthetic_SME_Directory_60.csv"


def private_sources():
    if not WORKBOOK.is_file() or not SME_CSV.is_file():
        pytest.skip("Private synthetic source files are not present")


def test_sme_directory_has_60_valid_people_and_normalized_practices():
    private_sources()
    people = load_directory(SME_CSV)
    assert len(people) == len({person["SME_ID"] for person in people}) == 60
    assert sorted(Counter(person["practice"] for person in people).values()) == [10] * 6
    assert sum(person["Availability_Status"] == "Available" for person in people) == 14
    assert sum(person["Availability_Status"] == "Partially Available" for person in people) == 22
    assert sum(person["Availability_Status"] == "Limited" for person in people) == 24


def test_workbook_cases_use_csv_specialists_and_explain_matches():
    private_sources()
    cases, _, _ = load_cases(WORKBOOK, SME_CSV)
    assert len(cases) == 60
    assert sum(bool(assess(case)["assigned_sme"]) for case in cases) == 33
    assert sum("SME_UNAVAILABLE" in assess(case)["blockers"] for case in cases) == 27
    source_rows = {row["SME_ID"]: row for row in load_directory(SME_CSV)}
    for case in cases:
        for sme in case.smes:
            assert sme.sme_id.startswith("SME-")
            assert sme.name and sme.specialization and sme.match_reason
            assert sme.practice == case.practice
            assert sme.matched_optimization == case.optimization_type
            assert sme.skills == [part.strip() for part in source_rows[sme.sme_id]["Skillset"].split(",")]
            assert sme.service_type_expertise in {case.service_type, "Both"}
    cloud = matching_smes(load_directory(SME_CSV), "Cloud", "vm_rightsizing", "Manage", "Retail")
    assert cloud and all(person.specialization in {"Cloud Optimization", "Cloud Operations"} for person in cloud)
    assert all(person.available == (person.availability_status != "Limited") for person in cloud)


def test_duplicate_sme_id_is_rejected(tmp_path):
    private_sources()
    with SME_CSV.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        headers = reader.fieldnames
    rows[1]["SME_ID"] = rows[0]["SME_ID"]
    broken = tmp_path / "broken_smes.csv"
    with broken.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="duplicate SME ID"):
        load_directory(broken)


def test_real_csv_match_stays_on_hold_until_evidence_and_scope_review(isolated_store):
    private_sources()
    shutil.copyfile(WORKBOOK, isolated_store.source_xlsx_path)
    assert import_local_workbook()["imported"] == 60
    case_id = "SOC-1F91OWU"
    evaluated = evaluate(case_id)
    assert evaluated["result"]["assigned_sme"] == "SME-003"
    assert {"STALE_OR_FUTURE_EVIDENCE", "CONTRACT_SCOPE_UNKNOWN"} <= set(evaluated["result"]["blockers"])
    reviewed = decide(case_id, Decision(
        decision="approve", reviewer_id="SME-003", reviewer_role="sme",
        case_version=evaluated["case_version"], comments="Synthetic POC review",
    ))
    assert reviewed["review_status"] == "hold"
    with pytest.raises(ValueError, match="No current approved evaluation"):
        approved_summary(case_id)
    assert generate_excel(detail(case_id))[:2] == b"PK"
