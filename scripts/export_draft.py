"""Save one evaluated case as a local, clearly labeled draft Excel file."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import detail, evaluate
from dashboard.excel_export import generate_excel, safe_filename


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a local draft FORGE assessment")
    parser.add_argument("opportunity_id", help="An ID from the active 60-row workbook")
    args = parser.parse_args()
    try:
        evaluate(args.opportunity_id)
        workbook = generate_excel(detail(args.opportunity_id))
    except (KeyError, ValueError, RuntimeError) as exc:
        print(f"Cannot export {args.opportunity_id}: {exc}", file=sys.stderr)
        return 1
    folder = ROOT / "dashboard" / "exports"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / safe_filename(args.opportunity_id)
    path.write_bytes(workbook)
    print(f"Saved internal draft: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
