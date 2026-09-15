"""Memória de aprendizado em SQLite — consertos resolvidos alimentam o cérebro."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "brain" / "learning.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS resolved_cases (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            board_model TEXT NOT NULL,
            symptom TEXT NOT NULL,
            failed_node TEXT,
            replaced_part TEXT NOT NULL,
            notes TEXT,
            measurements_json TEXT,
            board_norm TEXT,
            symptom_norm TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_board_norm ON resolved_cases(board_norm)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_symptom_norm ON resolved_cases(symptom_norm)"
    )
    conn.commit()
    return conn


def _norm(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9à-ü\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def remember_resolution(
    *,
    board_model: str,
    symptom: str,
    replaced_part: str,
    failed_node: str = "",
    notes: str = "",
    measurements: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Grava um conserto resolvido para aprendizado futuro."""
    entry_id = uuid.uuid4().hex[:12]
    created = datetime.now(timezone.utc).isoformat()
    board = (board_model or "").strip() or "desconhecido"
    symptom_s = (symptom or "").strip() or "—"
    part = (replaced_part or "").strip() or "peça não informada"
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO resolved_cases
            (id, created_at, board_model, symptom, failed_node, replaced_part,
             notes, measurements_json, board_norm, symptom_norm)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                created,
                board,
                symptom_s,
                failed_node or "",
                part,
                notes or "",
                json.dumps(measurements or [], ensure_ascii=False),
                _norm(board),
                _norm(symptom_s),
            ),
        )
        conn.commit()
    return {
        "id": entry_id,
        "at": created,
        "board_model": board,
        "symptom": symptom_s,
        "failed_node": failed_node,
        "replaced_part": part,
        "notes": notes,
        "measurements": measurements or [],
    }


def find_learned(
    board_model: str,
    symptom: str = "",
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Busca consertos parecidos já aprendidos."""
    board_n = _norm(board_model)
    symptom_n = _norm(symptom)
    if not board_n and not symptom_n:
        return []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM resolved_cases ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        score = 0
        b = row["board_norm"] or ""
        s = row["symptom_norm"] or ""
        if board_n and (board_n in b or b in board_n):
            score += 4
        score += len(set(board_n.split()) & set(b.split()))
        score += min(5, len(set(symptom_n.split()) & set(s.split())))
        if score <= 0:
            continue
        try:
            measurements = json.loads(row["measurements_json"] or "[]")
        except json.JSONDecodeError:
            measurements = []
        scored.append(
            (
                score,
                {
                    "id": row["id"],
                    "at": row["created_at"],
                    "board_model": row["board_model"],
                    "symptom": row["symptom"],
                    "failed_node": row["failed_node"],
                    "replaced_part": row["replaced_part"],
                    "notes": row["notes"],
                    "measurements": measurements,
                },
            )
        )
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[:limit]]


def learned_as_context(board_model: str, symptom: str = "") -> str:
    sims = find_learned(board_model, symptom)
    if not sims:
        return ""
    lines = [
        "MEMÓRIA DE APRENDIZADO (SQLite — consertos que VOCÊ já resolveu):",
        "Priorize estas soluções se o aparelho/sintoma bater — diga ao usuário que já viu isso antes.",
    ]
    for it in sims:
        lines.append(
            f"- {it['board_model']} | sintoma “{it['symptom']}” → "
            f"trocou **{it['replaced_part']}**"
            + (f" (nó {it['failed_node']})" if it.get("failed_node") else "")
            + (f" | nota: {it['notes']}" if it.get("notes") else "")
        )
    return "\n".join(lines)


def build_diagnostic_map(board_model: str, symptom: str, research_blurb: str = "") -> dict[str, Any]:
    """Mapa de diagnóstico em 3 passos (visão → básico → componentes)."""
    device = board_model or "aparelho"
    sym = symptom or "sintoma não informado"
    return {
        "device": device,
        "symptom": sym,
        "steps": [
            {
                "id": 1,
                "name": "Análise visual",
                "goal": "Inspecionar a placa: queima, inchaço, solda fria, cheiro, fusível.",
                "ask": "Me mande a foto da placa (área da fonte/entrada se possível).",
            },
            {
                "id": 2,
                "name": "Medições básicas",
                "goal": "Tensão de standby/entrada, continuidade de fusível, GND comum.",
                "ask": "Com o multímetro, vamos medir o primeiro ponto crítico.",
            },
            {
                "id": 3,
                "name": "Testes de componentes",
                "goal": "Isolar CI, capacitor, MOSFET ou regulador suspeito.",
                "ask": "Com base na medição, testamos o componente específico.",
            },
        ],
        "research_hint": (research_blurb or "")[:500],
        "current_step": 1,
    }


def map_as_context(diag_map: dict[str, Any] | None) -> str:
    if not diag_map:
        return ""
    lines = [
        "MAPA DE DIAGNÓSTICO (siga nesta ordem; UMA etapa por vez):",
        f"Aparelho: {diag_map.get('device')} | Sintoma: {diag_map.get('symptom')}",
        f"Passo atual: {diag_map.get('current_step', 1)}",
    ]
    for step in diag_map.get("steps") or []:
        lines.append(
            f"  {step['id']}. {step['name']}: {step['goal']} → {step['ask']}"
        )
    if diag_map.get("research_hint"):
        lines.append(f"Pista da pesquisa: {diag_map['research_hint']}")
    return "\n".join(lines)
