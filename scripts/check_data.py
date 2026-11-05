"""Beginner-friendly check of the two private synthetic source files."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.policy_engine import assess
from app.sme_directory import load_directory
from app.workbook_26 import load_cases


def main() -> int:
    if not settings.source_xlsx_path.is_file():
        print(f"Missing workbook: {settings.source_xlsx_path}")
        return 1
    if not settings.sme_csv_path.is_file():
        print(f"Missing SME CSV: {settings.sme_csv_path}")
        return 1

    people = load_directory(settings.sme_csv_path)
    cases, practices, stages = load_cases(settings.source_xlsx_path, settings.sme_csv_path)
    results = [(case, assess(case, evidence_max_age_days=settings.evidence_max_age_days))
               for case in cases]
    blockers = Counter(code for _, result in results for code in result["blockers"])
    clear = [(case, result) for case, result in results if not result["blockers"]]

    print(f"Opportunities: {len(cases)}")
    print(f"Synthetic SMEs: {len(people)}")
    print("Practices:", dict(practices))
    print("Source stages:", dict(stages))
    print(f"Cases with no current blockers: {len(clear)}")
    print("Blocker counts:", dict(blockers))
    if clear:
        case, result = clear[0]
        print(f"Suggested internal demo case: {case.opportunity_id}")
        print(f"Its assigned reviewer ID: {result['assigned_sme']}")
        print("Set FORGE_SME_REVIEWER_ID to that reviewer ID before starting the API.")
    print("All figures above use fictional POC data and current local policy rules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
