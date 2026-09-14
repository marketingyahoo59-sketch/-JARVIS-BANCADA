"""Persistência do histórico de medições e do caso."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CASES_DIR = Path(__file__).resolve().parent.parent / "data" / "cases"


class CaseMemory:
    """Salva e recupera o histórico completo de um diagnóstico."""

    def __init__(self, cases_dir: Path | None = None) -> None:
        self.cases_dir = cases_dir or CASES_DIR
        self.cases_dir.mkdir(parents=True, exist_ok=True)

    def new_case_id(self) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return f"{stamp}-{uuid.uuid4().hex[:8]}"

    def path_for(self, case_id: str) -> Path:
        return self.cases_dir / f"{case_id}.json"

    def create(
        self,
        board_model: str,
        symptom: str,
        case_id: str | None = None,
    ) -> dict[str, Any]:
        case = {
            "case_id": case_id or self.new_case_id(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "board_model": board_model,
            "symptom": symptom,
            "status": "intake",
            "phase": "intake",
            "messages": [],
            "measurements": [],
            "suspect_components": [],
            "probe_hints": [],
            "images": [],
            "solution_notes": [],
            "strategy_revisions": 0,
        }
        self.save(case)
        return case

    def load(self, case_id: str) -> dict[str, Any] | None:
        path = self.path_for(case_id)
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)

    def save(self, case: dict[str, Any]) -> None:
        case["updated_at"] = datetime.now(timezone.utc).isoformat()
        path = self.path_for(case["case_id"])
        with path.open("w", encoding="utf-8") as fh:
            json.dump(case, fh, ensure_ascii=False, indent=2)

    def list_cases(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.cases_dir.glob("*.json"), reverse=True):
            try:
                with path.open(encoding="utf-8") as fh:
                    data = json.load(fh)
                items.append(
                    {
                        "case_id": data.get("case_id", path.stem),
                        "board_model": data.get("board_model", "?"),
                        "symptom": data.get("symptom", ""),
                        "status": data.get("status", ""),
                        "updated_at": data.get("updated_at", ""),
                        "measurements": len(data.get("measurements", [])),
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue
        return items

    def add_message(
        self,
        case: dict[str, Any],
        role: str,
        content: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "role": role,
            "content": content,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        if meta:
            entry["meta"] = meta
        case.setdefault("messages", []).append(entry)
        self.save(case)

    def add_measurement(
        self,
        case: dict[str, Any],
        point: str,
        expected: str,
        measured: str,
        verdict: str,
        notes: str = "",
    ) -> None:
        case.setdefault("measurements", []).append(
            {
                "point": point,
                "expected": expected,
                "measured": measured,
                "verdict": verdict,
                "notes": notes,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.save(case)

    def add_image_note(
        self,
        case: dict[str, Any],
        filename: str,
        analysis: str,
        probe_targets: list[dict[str, Any]] | None = None,
    ) -> None:
        case.setdefault("images", []).append(
            {
                "filename": filename,
                "analysis": analysis,
                "probe_targets": probe_targets or [],
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if probe_targets:
            case.setdefault("probe_hints", []).extend(probe_targets)
        self.save(case)
