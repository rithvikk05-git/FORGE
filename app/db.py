
"""SQLite storage for local case, review, and append-only audit records."""
from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from .config import settings


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or settings.sqlite_path
    target.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(target, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    return db


def initialize(path: Path | None = None) -> None:
    with closing(connect(path)) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS opportunities (
            opportunity_id TEXT PRIMARY KEY, case_json TEXT NOT NULL,
            case_version TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evaluations (
            opportunity_id TEXT PRIMARY KEY REFERENCES opportunities(opportunity_id),
            case_version TEXT NOT NULL, result_json TEXT NOT NULL,
            review_status TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS approvals (
            opportunity_id TEXT PRIMARY KEY REFERENCES opportunities(opportunity_id),
            case_version TEXT NOT NULL, decision TEXT NOT NULL,
            reviewer_id TEXT NOT NULL, reviewer_role TEXT NOT NULL,
            comments TEXT NOT NULL, decided_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id TEXT NOT NULL, event_type TEXT NOT NULL,
            actor TEXT NOT NULL, case_version TEXT NOT NULL,
            payload_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS idempotency (
            key TEXT PRIMARY KEY, opportunity_id TEXT NOT NULL,
            case_version TEXT NOT NULL, result_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS outcomes (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id TEXT NOT NULL, outcome_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)


@contextmanager
def transaction(path: Path | None = None):
    db = connect(path)
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
