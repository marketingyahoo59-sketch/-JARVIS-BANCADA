"""Event Bus — fila de ações do agente para a UI reagir na hora."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent / "frontend" / "event_bus"

try:
    _bus_component = components.declare_component(
        "jarvis_event_bus",
        path=str(_COMPONENT_DIR),
    )
except Exception:  # noqa: BLE001
    _bus_component = None


def ensure_bus_state() -> None:
    st.session_state.setdefault("event_bus_queue", [])
    st.session_state.setdefault("event_bus_history", [])
    st.session_state.setdefault("component_refresh", {})
    st.session_state.setdefault("hud_overrides", {})
    st.session_state.setdefault("sfx_mood", None)


def emit(event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Enfileira evento para o bridge JS + histórico da sessão."""
    ensure_bus_state()
    evt = {
        "id": uuid.uuid4().hex[:10],
        "type": event_type,
        "payload": payload or {},
        "ts": time.time(),
    }
    q = list(st.session_state.get("event_bus_queue") or [])
    q.append(evt)
    st.session_state.event_bus_queue = q[-40:]
    hist = list(st.session_state.get("event_bus_history") or [])
    hist.append(evt)
    st.session_state.event_bus_history = hist[-60:]
    return evt


def bump_refresh(component_id: str) -> int:
    """Incrementa token de remount (cura removeChild / DOM stale)."""
    ensure_bus_state()
    tokens = dict(st.session_state.get("component_refresh") or {})
    tokens[component_id] = int(tokens.get(component_id) or 0) + 1
    st.session_state.component_refresh = tokens
    emit("refresh_component", {"component_id": component_id, "token": tokens[component_id]})
    return tokens[component_id]


def refresh_token(component_id: str) -> int:
    ensure_bus_state()
    return int((st.session_state.get("component_refresh") or {}).get(component_id) or 0)


def drain_events() -> list[dict[str, Any]]:
    ensure_bus_state()
    q = list(st.session_state.get("event_bus_queue") or [])
    st.session_state.event_bus_queue = []
    return q


def mount_event_bus() -> None:
    """Sempre montado no topo — aplica eventos na hora (toasts, SFX, telemetria live)."""
    ensure_bus_state()
    events = drain_events()
    # também espelha telemetria atual para o overlay
    telem = dict(st.session_state.get("hud_overrides") or {})
    music_on = bool(st.session_state.get("music_on"))
    payload = {
        "events": events,
        "telemetry": telem,
        "music_on": music_on,
        "tick": time.time(),
    }
    if _bus_component is None:
        # fallback: caption se houver eventos
        if events:
            kinds = ", ".join(e.get("type", "?") for e in events[-5:])
            st.caption(f"⚡ Event Bus · {kinds}")
        return
    _bus_component(data=json.dumps(payload, ensure_ascii=False), default=None, key="jarvis_event_bus")
