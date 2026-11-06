
"""Local-only configuration. Paths are anchored to the repository."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def local_path(name: str, default: str) -> Path:
    value = Path(os.getenv(name, default)).expanduser()
    return value if value.is_absolute() else ROOT / value


@dataclass(frozen=True)
class Settings:
    sqlite_path: Path = local_path("SQLITE_PATH", "runtime/forge_final.sqlite")
    checkpoint_path: Path = local_path("CHECKPOINT_PATH", "runtime/langgraph_final.sqlite")
    source_xlsx_path: Path = local_path("SOURCE_XLSX_PATH", "data/private/FORGE_60_Opportunities_26_Column_Agent_Input.xlsx")
    sme_csv_path: Path = local_path("SME_CSV_PATH", "data/private/Kyndryl_Synthetic_SME_Directory_60.csv")
    qdrant_url: str = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
    evidence_max_age_days: int = int(os.getenv("EVIDENCE_MAX_AGE_DAYS", "180"))
    sme_token: str | None = os.getenv("FORGE_SME_TOKEN")
    sme_reviewer_id: str | None = os.getenv("FORGE_SME_REVIEWER_ID")
    governance_token: str | None = os.getenv("FORGE_GOVERNANCE_TOKEN")
    governance_reviewer_id: str | None = os.getenv("FORGE_GOVERNANCE_REVIEWER_ID")


settings = Settings()
