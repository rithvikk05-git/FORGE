"""Print the internal path from one workbook case to human review.

This is a local developer view. It evaluates the case if needed; it never
approves, rejects, exports, or sends the opportunity anywhere.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import evaluate


def main() -> int:
    parser = argparse.ArgumentParser(description="Trace one local FORGE assessment")
    parser.add_argument("opportunity_id", help="An ID from the active 60-row workbook")
    parser.add_argument("--json", action="store_true", help="Print the complete internal evaluation JSON")
    args = parser.parse_args()
    try:
        evaluation = evaluate(args.opportunity_id)
    except KeyError:
        print("Opportunity not found. Run scripts/seed_db.py --source workbook first.", file=sys.stderr)
        return 1
    result = evaluation["result"]
    if args.json:
        print(json.dumps(evaluation, indent=2))
        return 0

    print("Opportunity:", args.opportunity_id)
    for step in result.get("trace", []):
        print("  ->", step)
    matching = result.get("sme_matching") or {}
    feasibility = result.get("feasibility") or {}
    risk = result.get("risk_assessment") or {}
    consolidated = result.get("consolidation") or {}
    print("SME matching:", matching.get("status"),
          [item["sme_id"] for item in matching.get("recommendations", [])])
    print("Feasibility:", feasibility.get("feasibility_score"), feasibility.get("classification"))
    print("Risk:", risk.get("overall_risk_score"), risk.get("risk_classification"))
    print("Social Impact provisional:", (risk.get("social_impact") or {}).get("provisional"))
    print("Missing information:", consolidated.get("missing_information", []))
    print("Policy blockers:", result.get("blockers", []))
    print("Next action:", consolidated.get("recommended_next_action"))
    print("Human review status:", evaluation["review_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
