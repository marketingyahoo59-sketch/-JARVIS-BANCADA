"""Perfil do técnico de manutenção (Sr. Igor, etc.)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


from .paths import PROFILE_PATH, ensure_data_dirs

ensure_data_dirs()

DEFAULT_PROFILE: dict[str, Any] = {
    "display_name": "Sr. Igor",
    "full_name": "Igor",
    "title": "Técnico de Manutenção",
    "workshop": "Bancada Principal",
    "specialty": "Fontes SMPS / placas digitais",
    "shift": "Integral",
    "notes": "",
    "call_by_name": True,
    "voice_greeting": True,
    "theme": "stark-cyan",
}

PRESETS: list[dict[str, Any]] = [
    {
        "display_name": "Sr. Igor",
        "full_name": "Igor",
        "title": "Técnico de Manutenção",
        "workshop": "Bancada Principal",
        "specialty": "Fontes SMPS / placas digitais",
        "shift": "Integral",
        "notes": "Operador principal da bancada JARVIS.",
        "call_by_name": True,
        "voice_greeting": True,
        "theme": "stark-cyan",
    },
    {
        "display_name": "Sr. Técnico",
        "full_name": "Técnico",
        "title": "Técnico de Manutenção",
        "workshop": "Bancada 2",
        "specialty": "Eletrônica geral",
        "shift": "Integral",
        "notes": "",
        "call_by_name": True,
        "voice_greeting": True,
        "theme": "stark-cyan",
    },
    {
        "display_name": "Assistente",
        "full_name": "Assistente de bancada",
        "title": "Auxiliar",
        "workshop": "Bancada Principal",
        "specialty": "Apoio / triagem",
        "shift": "Tarde",
        "notes": "",
        "call_by_name": True,
        "voice_greeting": True,
        "theme": "stark-cyan",
    },
]


def load_profile() -> dict[str, Any]:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not PROFILE_PATH.exists():
        save_profile(DEFAULT_PROFILE)
        return dict(DEFAULT_PROFILE)
    try:
        data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        out = dict(DEFAULT_PROFILE)
        out.update({k: v for k, v in data.items() if v is not None})
        return out
    except Exception:
        return dict(DEFAULT_PROFILE)


def save_profile(profile: dict[str, Any]) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged = dict(DEFAULT_PROFILE)
    merged.update({k: v for k, v in profile.items() if v is not None})
    PROFILE_PATH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_presets() -> list[dict[str, Any]]:
    return [dict(p) for p in PRESETS]


def address_user(profile: dict[str, Any] | None = None) -> str:
    p = profile or load_profile()
    name = str(p.get("display_name") or "técnico").strip()
    if p.get("call_by_name", True):
        return name
    return "técnico"
