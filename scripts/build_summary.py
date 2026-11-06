"""Create a commit-safe aggregate summary of the private 26-column workbook."""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.schemas import PRACTICES
from app.workbook_26 import load_cases


def main() -> None:
    cases, _, _ = load_cases(settings.source_xlsx_path)
    target = ROOT / "data" / "opportunity_summary.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("practice", "total", "identified", "noticed", "qualified",
                         "validated", "won", "stretch"))
        for practice in PRACTICES:
            stage_counts = Counter(case.source_sales_stage for case in cases if case.practice == practice)
            writer.writerow((practice, sum(stage_counts.values()), *(stage_counts[stage] for stage in
                             ("Identified", "Noticed", "Qualified", "Validated", "Won", "Stretch"))))
    print(f"Wrote six aggregate practice rows to {target}; no opportunity IDs or names included.")

    # Keep a private, full 26-column inspection copy in sync with the workbook.
    details = ROOT / "data" / "private" / "opportunity_details.csv"
    book = load_workbook(settings.source_xlsx_path, read_only=True, data_only=True)
    try:
        with details.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerows(book["Opportunity_Input"].values)
    finally:
        book.close()
    print(f"Wrote private 60-row inspection copy to {details}.")


if __name__ == "__main__":
    main()
