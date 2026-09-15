"""Raiz de dados persistente (Railway Volume / VPS / local)."""

from __future__ import annotations

import os
from pathlib import Path

# No Railway: monte o volume em /data e defina JARVIS_DATA_DIR=/data
_DEFAULT = Path(__file__).resolve().parent.parent / "data"
DATA_ROOT = Path(os.getenv("JARVIS_DATA_DIR", str(_DEFAULT))).expanduser().resolve()

CASES_DIR = DATA_ROOT / "cases"
UPLOADS_DIR = DATA_ROOT / "uploads"
BRAIN_DIR = DATA_ROOT / "brain"
FAILURES_DIR = DATA_ROOT / "failures"
DOCS_DIR = DATA_ROOT / "docs"
SENSORS_DIR = DATA_ROOT / "sensors"
PROFILE_PATH = DATA_ROOT / "profile.json"
LEARNING_DB = BRAIN_DIR / "learning.db"


def ensure_data_dirs() -> Path:
    for d in (CASES_DIR, UPLOADS_DIR, BRAIN_DIR, FAILURES_DIR, DOCS_DIR, SENSORS_DIR):
        d.mkdir(parents=True, exist_ok=True)
    return DATA_ROOT
