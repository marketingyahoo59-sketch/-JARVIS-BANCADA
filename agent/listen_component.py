"""Componente Streamlit: escuta contínua com status ouvindo/processando/falando."""

from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent / "frontend"
_listen = components.declare_component("jarvis_listen", path=str(_COMPONENT_DIR))


def continuous_listen(
    *,
    active: bool = True,
    paused: bool = False,
    agent_speaking: bool = False,
    key: str | None = None,
) -> str | None:
    """
    Escuta o microfone continuamente.
    Quando o usuário termina de falar (pausa natural), devolve o texto final.
    """
    value = _listen(
        active=active,
        paused=paused or agent_speaking,
        agent_speaking=agent_speaking,
        key=key,
        default=None,
    )
    if value is None:
        return None
    if isinstance(value, dict):
        text = str(value.get("transcript") or "").strip()
        return text or None
    text = str(value).strip()
    return text or None
