"""Banco de falhas resolvidas — memória coletiva de consertos."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BANK_DIR = Path(__file__).resolve().parent.parent / "data" / "failures"
BANK_PATH = BANK_DIR / "bank.json"


def _load() -> list[dict[str, Any]]:
    BANK_DIR.mkdir(parents=True, exist_ok=True)
    if not BANK_PATH.exists():
        return []
    try:
        with BANK_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(items: list[dict[str, Any]]) -> None:
    BANK_DIR.mkdir(parents=True, exist_ok=True)
    with BANK_PATH.open("w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=2)


def _norm(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9à-ü\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def add_resolved_failure(
    *,
    board_model: str,
    symptom: str,
    failed_node: str,
    replaced_part: str,
    notes: str = "",
    measurements: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    items = _load()
    entry = {
        "id": uuid.uuid4().hex[:12],
        "at": datetime.now(timezone.utc).isoformat(),
        "board_model": board_model,
        "symptom": symptom,
        "failed_node": failed_node,
        "replaced_part": replaced_part,
        "notes": notes,
        "measurements": measurements or [],
    }
    items.insert(0, entry)
    _save(items[:500])
    return entry


def find_similar(
    board_model: str,
    symptom: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    board_n = _norm(board_model)
    symptom_n = _norm(symptom)
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in _load():
        score = 0
        b = _norm(str(item.get("board_model", "")))
        s = _norm(str(item.get("symptom", "")))
        if board_n and board_n in b or b and b in board_n:
            score += 3
        # token overlap on symptom
        bt = set(board_n.split())
        bb = set(b.split())
        score += len(bt & bb)
        st = set(symptom_n.split())
        ss = set(s.split())
        score += min(4, len(st & ss))
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[:limit]]


def similar_as_context(board_model: str, symptom: str) -> str:
    sims = find_similar(board_model, symptom)
    if not sims:
        return ""
    lines = ["CASOS RESOLVIDOS PARECIDOS (banco local):"]
    for it in sims:
        lines.append(
            f"- {it.get('board_model')}: sintoma “{it.get('symptom')}” → "
            f"troca {it.get('replaced_part')} (nó {it.get('failed_node')})"
            + (f" | {it.get('notes')}" if it.get("notes") else "")
        )
    return "\n".join(lines)


def list_failures(limit: int = 30) -> list[dict[str, Any]]:
    return _load()[:limit]
