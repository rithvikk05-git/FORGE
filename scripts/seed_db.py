"""Import only the user's 60-opportunity workbook and synthetic POC enrichment."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import HTTPException
from app.api import import_local_workbook


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the local FORGE SQLite store")
    parser.add_argument("--source", choices=("workbook",), default="workbook",
                        help="The sole active 60-row workbook source")
    args = parser.parse_args()
    try:
        result = import_local_workbook()
    except HTTPException as exc:
        print(f"Import failed ({exc.status_code}): {exc.detail}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
