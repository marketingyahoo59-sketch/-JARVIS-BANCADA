"""Componente Streamlit estável para escuta contínua.

Importante: o iframe deve permanecer SEMPRE montado (mesmo pausado).
Montar/desmontar o custom component no meio do layout causa
NotFoundError: removeChild no React do Streamlit.
"""

from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent / "frontend"
_listen = components.declare_component("jarvis_listen", path=str(_COMPONENT_DIR))

# Altura fixa — NÃO redimensionar dinamicamente (evita thrash no DOM).
_FIXED_HEIGHT = 132


def continuous_listen(
    *,
    active: bool = True,
    paused: bool = False,
    agent_speaking: bool = False,
    key: str = "jarvis_listen_stable",
) -> str | None:
    """
    Escuta o microfone. Devolve texto final quando o usuário pausa a fala.
    Sempre chame esta função (com active=False se desligado) para não desmontar o iframe.
    """
    value = _listen(
        active=bool(active),
        paused=bool(paused or agent_speaking or not active),
        agent_speaking=bool(agent_speaking or not active),
        key=key,
        default=None,
    )
    if not active:
        return None
    if value is None:
        return None
    if isinstance(value, dict):
        text = str(value.get("transcript") or value.get("text") or "").strip()
        return text or None
    text = str(value).strip()
    return text or None
