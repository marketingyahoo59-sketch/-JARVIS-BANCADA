"""Self-healing: captura erros JS e entrega ao JARVIS."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent / "frontend" / "error_bridge"

try:
    _error_bridge = components.declare_component(
        "jarvis_error_bridge",
        path=str(_COMPONENT_DIR),
    )
except Exception:  # noqa: BLE001
    _error_bridge = None


def ensure_heal_state() -> None:
    st.session_state.setdefault("ui_errors", [])
    st.session_state.setdefault("ui_heal_log", [])


def mount_self_heal_bridge() -> None:
    """Sempre montado — captura erros no parent e injeta em session_state."""
    ensure_heal_state()
    if _error_bridge is None:
        return
    raw = _error_bridge(default=None, key="jarvis_err_bridge")
    if not raw:
        return
    try:
        batch = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return
    if not isinstance(batch, list) or not batch:
        return
    errs = list(st.session_state.get("ui_errors") or [])
    for item in batch:
        if not isinstance(item, dict):
            continue
        msg = str(item.get("message") or "").strip()
        if not msg:
            continue
        item = dict(item)
        item.setdefault("acked", False)
        errs.append(item)
    st.session_state.ui_errors = errs[-40:]


def pending_ui_errors(limit: int = 5) -> list[dict[str, Any]]:
    ensure_heal_state()
    out = []
    for e in list(st.session_state.get("ui_errors") or []):
        if e.get("acked"):
            continue
        out.append(e)
        if len(out) >= limit:
            break
    return out


def format_ui_errors_for_llm(limit: int = 5) -> str:
    errs = pending_ui_errors(limit=limit)
    if not errs:
        return ""
    return (
        "ERROS DE UI (self-healing) — analise e chame acknowledge_ui_error "
        "com correção sugerida:\n"
        + json.dumps(errs, ensure_ascii=False, indent=2)
    )


def render_heal_panel() -> None:
    """Painel compacto de erros / patches sugeridos (dev)."""
    ensure_heal_state()
    errs = list(st.session_state.get("ui_errors") or [])
    heals = list(st.session_state.get("ui_heal_log") or [])
    pending = [e for e in errs if not e.get("acked")]
    if not pending and not heals:
        return
    with st.expander(f"Self-heal · {len(pending)} erro(s) pendente(s)", expanded=bool(pending)):
        for e in pending[-5:]:
            st.caption(f"`{e.get('type', 'error')}` · {e.get('message', '')[:180]}")
        for h in heals[-3:]:
            st.info(
                f"**{h.get('severity', 'medium').upper()}** — {h.get('summary', '')}\n\n"
                f"Patch sugerido:\n```\n{h.get('suggested_fix', '')}\n```"
            )
