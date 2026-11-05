"""Read the four future JSON reference sheets and prior form submissions.

These records provide context only. Until their data and rules are reviewed,
they never add to policy, feasibility, SME, or risk scores.
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import ROOT
from .repositories import list_cases
from .schemas import Opportunity

REFERENCE_DIR = ROOT / "data" / "reference"
FILES = ("successful_opportunities", "cost_impact", "technical_impact", "compliance")


def load_reference_data(folder: Path | None = None, *, current_id: str | None = None) -> dict:
    """Fail clearly on malformed files; never turn bad reference data into facts."""
    folder = folder or REFERENCE_DIR
    result = {}
    for name in FILES:
        path = folder / f"{name}.json"
        if not path.exists():
            result[name] = []
            continue
        with path.open(encoding="utf-8") as handle:
            content = json.load(handle)
        if not isinstance(content, dict) or content.get("schema_version") != 1 or not isinstance(content.get("records"), list):
            raise ValueError(f"Invalid reference file: {path.name}")
        records = content["records"]
        ids = []
        for index, record in enumerate(records, 1):
            if not isinstance(record, dict) or not isinstance(record.get("reference_id"), str) or not record["reference_id"].strip():
                raise ValueError(f"Missing reference_id in {path.name} record {index}")
            ids.append(record["reference_id"])
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate reference_id in {path.name}")
        result[name] = records

    # Form submissions live in the opportunity list, not in the successful
    # repository. A minimal JSON view lets agents compare later submissions.
    result["form_opportunities"] = [
        {"reference_id": row["case"]["opportunity_id"],
         "opportunity_id": row["case"]["opportunity_id"],
         "practice": row["case"]["practice"],
         "optimization_type": row["case"].get("optimization_type")}
        for row in list_cases()
        if row["case"].get("source_system") == "form"
        and row["case"]["opportunity_id"] != current_id
    ]
    return result


def matching_reference_ids(references: dict | None, section: str,
                           case: Opportunity) -> list[str]:
    """Match only an exact case ID or both practice and optimization label."""
    records = (references or {}).get(section, [])
    return [record["reference_id"] for record in records if (
        record.get("opportunity_id") == case.opportunity_id or
        (case.optimization_type and record.get("practice") == case.practice
         and record.get("optimization_type") == case.optimization_type)
    )]


def matching_reference_records(references: dict | None, section: str,
                               case: Opportunity) -> list[dict]:
    """Return source records as evidence, without turning them into scores."""
    ids = set(matching_reference_ids(references, section, case))
    return [record for record in (references or {}).get(section, [])
            if record["reference_id"] in ids]
