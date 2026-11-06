"""Save one approved internal assessment as an Excel file."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import approved_summary, detail
from dashboard.excel_export import generate_excel


def main() -> int:
    parser = argparse.ArgumentParser(description="Export an approved FORGE case")
    parser.add_argument("opportunity_id", help="ID shown by the internal API")
    args = parser.parse_args()

    try:
        # This rechecks the current case version, human approval and blockers.
        approved_summary(args.opportunity_id)
        excel_bytes = generate_excel(detail(args.opportunity_id))
    except (KeyError, ValueError) as exc:
        print(f"Cannot export {args.opportunity_id}: {exc}", file=sys.stderr)
        return 1

    output_dir = ROOT / "dashboard" / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{args.opportunity_id}.xlsx"
    target.write_bytes(excel_bytes)
    print(f"Saved approved internal assessment: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
