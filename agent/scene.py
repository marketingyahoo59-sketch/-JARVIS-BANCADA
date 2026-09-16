"""Estado da cena — o operador lê e manipula o HUD, não o chatbot."""

from __future__ import annotations

import re
from typing import Any

LAYOUT_MODES: dict[str, dict[str, Any]] = {
    "repair": {
        "label": "MODO CONSERTO",
        "cols": [0.7, 1.05, 1.75],
        "hint": "Foco em imagem/esquema e telemetria da placa",
    },
    "social": {
        "label": "MODO SOCIAL",
        "cols": [0.5, 2.4, 0.7],
        "hint": "Chat expandido, módulos recolhidos",
    },
    "analysis": {
        "label": "MODO ANÁLISE",
        "cols": [1.05, 1.45, 1.05],
        "hint": "Tudo aberto: análise, chat e telemetria",
    },
}

_LAYOUT_ALIAS = {
    "repair": "repair",
    "conserto": "repair",
    "modo conserto": "repair",
    "fix": "repair",
    "diagnose": "repair",
    "diagnostico": "repair",
    "diagnóstico": "repair",
    "social": "social",
    "chat": "social",
    "modo social": "social",
    "papo": "social",
    "analysis": "analysis",
    "analise": "analysis",
    "análise": "analysis",
    "modo análise": "analysis",
    "modo analise": "analysis",
    "tudo": "analysis",
    "all": "analysis",
}


def _ss() -> Any | None:
    try:
        import streamlit as st

        return st.session_state
    except Exception:
        return None


def ensure_scene() -> None:
    ss = _ss()
    if ss is None:
        return
    ss.setdefault("scene_layout", "analysis")
    ss.setdefault("focus_component", "")
    ss.setdefault("hud_modules", [])
    ss.setdefault("hud_overrides", {})
    ss.setdefault("ui_errors", [])
    ss.setdefault("music_on", False)
    ss.setdefault("agent_actions", [])
    ss.setdefault("_last_anomaly_key", "")


def normalize_layout(mode: str) -> str | None:
    key = str(mode or "").strip().lower()
    return _LAYOUT_ALIAS.get(key)


def current_layout() -> str:
    ensure_scene()
    ss = _ss()
    mode = (ss.get("scene_layout") if ss is not None else None) or "analysis"
    return mode if mode in LAYOUT_MODES else "analysis"


def layout_columns() -> list[float]:
    return list(LAYOUT_MODES[current_layout()]["cols"])


def layout_label() -> str:
    return str(LAYOUT_MODES[current_layout()]["label"])


def current_focus() -> str:
    ensure_scene()
    ss = _ss()
    return str((ss.get("focus_component") if ss is not None else "") or "")


def parse_num(value: Any) -> float | None:
    if value is None:
        return None
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(value).replace(",", "."))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def screen_snapshot() -> dict[str, Any]:
    """O que está na tela agora — entrada da fase ANALISAR/VERIFICAR."""
    ensure_scene()
    ss = _ss()
    if ss is None:
        return {
            "layout": "analysis",
            "focus": "",
            "modules": [],
            "telemetry": {},
            "music_on": False,
            "ui_errors": [],
            "nav": "bancada",
            "voice_status": "idle",
        }
    mods = []
    for m in list(ss.get("hud_modules") or []):
        mods.append(
            {
                "id": m.get("id"),
                "kind": m.get("kind"),
                "title": m.get("title"),
                "side": m.get("side"),
            }
        )
    errs = []
    for e in list(ss.get("ui_errors") or []):
        if isinstance(e, dict) and not e.get("acked"):
            errs.append({"id": e.get("id") or e.get("source"), "message": e.get("message") or e.get("error")})
    return {
        "layout": current_layout(),
        "layout_label": layout_label(),
        "focus": current_focus(),
        "modules": mods,
        "telemetry": dict(ss.get("hud_overrides") or {}),
        "music_on": bool(ss.get("music_on")),
        "ui_errors": errs,
        "nav": ss.get("nav") or "bancada",
        "voice_status": ss.get("voice_status") or "idle",
        "open_module_ids": [m.get("id") for m in mods],
    }


def scan_anomalies(snap: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Detecta tensão/temp/erro sem esperar o usuário pedir."""
    snap = snap or screen_snapshot()
    telem = snap.get("telemetry") or {}
    alerts: list[dict[str, Any]] = []

    rail = parse_num(telem.get("rail_3v3"))
    if rail is not None and (rail > 3.63 or rail < 3.05):
        alerts.append(
            {
                "level": "danger",
                "id": "rail_3v3",
                "text": (
                    f"Sr. Igor, a linha de 3V3 está em {rail:.2f} V — fora da faixa. "
                    "Sugiro desligar a fonte agora."
                ),
            }
        )

    vbus = parse_num(telem.get("vbus"))
    if vbus is not None:
        if 4.0 <= vbus <= 7.5 and (vbus > 5.55 or vbus < 4.35):
            alerts.append(
                {
                    "level": "danger",
                    "id": "vbus_5v",
                    "text": (
                        "Sr. Igor, notei uma oscilação perigosa na linha de 5V, "
                        "sugiro desligar a fonte agora."
                    ),
                }
            )
        elif vbus > 13.8:
            alerts.append(
                {
                    "level": "danger",
                    "id": "vbus_high",
                    "text": (
                        f"Sr. Igor, VBUS em {vbus:.1f} V — acima do seguro. "
                        "Desligue a fonte antes de continuar."
                    ),
                }
            )
        elif 10.0 <= vbus <= 14.5 and vbus < 10.8:
            alerts.append(
                {
                    "level": "warn",
                    "id": "vbus_low",
                    "text": f"Sr. Igor, VBUS caiu para {vbus:.1f} V. Estou monitorando a fonte.",
                }
            )

    temp = parse_num(telem.get("temp"))
    if temp is not None and temp >= 75:
        alerts.append(
            {
                "level": "danger" if temp >= 85 else "warn",
                "id": "temp",
                "text": (
                    f"Sr. Igor, temperatura da bancada em {temp:.0f} °C. "
                    "Reduza carga ou desligue se continuar subindo."
                ),
            }
        )

    if snap.get("ui_errors"):
        alerts.append(
            {
                "level": "warn",
                "id": "ui",
                "text": "Erro de sistema no HUD. Estou remontando o módulo afetado.",
            }
        )
    return alerts


def has_ui() -> bool:
    return _ss() is not None


def verify_actions(actions: list[dict[str, Any]], after: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    after = after or screen_snapshot()
    checks: list[dict[str, Any]] = []
    live = has_ui()
    mods = {m.get("kind") for m in (after.get("modules") or [])}
    for a in actions or []:
        name = a.get("name") or a.get("tool")
        result = a.get("result") if isinstance(a.get("result"), dict) else {}
        ok = bool(result.get("ok", True))
        note = ""
        if not live:
            checks.append({"tool": name, "ok": ok, "note": "sem UI", "result": result})
            continue
        if name == "set_layout" and ok:
            want = result.get("layout") or a.get("mode")
            if want and after.get("layout") != want:
                ok = False
                note = f"layout ficou {after.get('layout')}, esperado {want}"
        elif name in {"close_all_modules", "close_modules"} and ok:
            kind = (result.get("closed") or a.get("kind") or "all").lower()
            if kind in {"all", ""} and after.get("modules"):
                ok = False
                note = "ainda há módulos abertos"
        elif name == "focus_component" and ok:
            want = result.get("id") or a.get("id")
            if want and after.get("focus") != want:
                ok = False
                note = f"foco ficou {after.get('focus')}"
        elif name == "launch_module" and ok:
            kind = result.get("type") or a.get("type")
            if kind and kind not in mods and kind not in {"image"}:
                # image mapeia para board
                mapped = {"image": "board", "pdf": "schematic"}.get(str(kind), kind)
                if mapped not in mods:
                    ok = False
                    note = f"módulo {kind} não apareceu"
        checks.append({"tool": name, "ok": ok, "note": note, "result": result})
    return checks
