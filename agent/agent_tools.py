"""Ferramentas do agente JARVIS — a IA dispara ações reais na UI/sistema."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

# Schemas OpenAI / Anthropic (function calling)
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "open_module",
            "description": (
                "Abre um módulo holográfico flutuante na interface (imagem/placa, "
                "esquema/PDF, ou vídeo). Use quando o operador pedir para ver/abrir "
                "algo. NÃO descreva o link — abra o módulo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["board", "schematic", "video", "pdf"],
                        "description": "Tipo do módulo",
                    },
                    "title": {"type": "string", "description": "Título do módulo"},
                    "side": {
                        "type": "string",
                        "enum": ["left", "right"],
                        "description": "Lado da tela (vídeo=left, esquema/placa=right)",
                    },
                    "url": {
                        "type": "string",
                        "description": "URL do vídeo/PDF se aplicável",
                    },
                    "label": {"type": "string", "description": "Legenda curta"},
                },
                "required": ["kind"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_modules",
            "description": "Fecha módulos flutuantes da interface.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["board", "schematic", "video", "pdf", "all"],
                        "description": "Qual fechar (all = todos)",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": (
                "Controla a trilha de ambiente (synthwave/lo-fi) e o waveform do rodapé."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["on", "off", "toggle"],
                    },
                    "style": {
                        "type": "string",
                        "enum": ["synthwave", "lofi", "focus", "ambient"],
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_hud",
            "description": (
                "Atualiza sensores/telemetria exibidos no HUD (tensão, CPU, RAM, temp)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sensor": {
                        "type": "string",
                        "enum": ["vbus", "rail_3v3", "temp", "cpu", "ram", "scan", "net"],
                    },
                    "value": {
                        "type": "string",
                        "description": "Valor a exibir, ex: '12.1 V' ou '67%'",
                    },
                },
                "required": ["sensor", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "Grava nota/medição na memória do caso (bancada).",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Texto da nota"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "acknowledge_ui_error",
            "description": (
                "Registra que você analisou um erro de interface (self-healing). "
                "Use quando houver erro JS/removeChild no contexto."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "suggested_fix": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                },
                "required": ["summary", "suggested_fix"],
            },
        },
    },
]


def _session():
    try:
        import streamlit as st

        return st.session_state
    except Exception:
        return None


def _ensure_stores(ss: Any) -> None:
    if ss is None:
        return
    ss.setdefault("hud_modules", [])
    ss.setdefault("music_on", False)
    ss.setdefault("music_track", 0)
    ss.setdefault("hud_overrides", {})
    ss.setdefault("ui_errors", [])
    ss.setdefault("ui_heal_log", [])
    ss.setdefault("agent_actions", [])


def execute_tool(
    name: str,
    args: dict[str, Any],
    *,
    case: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Executa uma ferramenta e altera estado da UI/caso. Retorna resultado para o LLM."""
    ss = _session()
    _ensure_stores(ss)
    args = args or {}
    case = case if isinstance(case, dict) else {}

    if name == "open_module":
        return _tool_open_module(ss, args, case)
    if name == "close_modules":
        return _tool_close_modules(ss, args)
    if name == "play_music":
        return _tool_play_music(ss, args)
    if name == "update_hud":
        return _tool_update_hud(ss, args)
    if name == "save_note":
        return _tool_save_note(ss, args, case)
    if name == "acknowledge_ui_error":
        return _tool_ack_error(ss, args)
    return {"ok": False, "error": f"ferramenta desconhecida: {name}"}


def _log_action(ss: Any, name: str, detail: str) -> None:
    if ss is None:
        return
    actions = list(ss.get("agent_actions") or [])
    actions.append(
        {
            "tool": name,
            "detail": detail,
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )
    ss.agent_actions = actions[-30:]


def _tool_open_module(ss: Any, args: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    from .hud_modules import DEFAULT_VIDEO, open_module

    kind = str(args.get("kind") or "schematic").lower()
    if kind == "pdf":
        kind = "schematic"
    side = str(args.get("side") or ("left" if kind == "video" else "right"))
    title = str(args.get("title") or {
        "board": "MÓDULO · PLACA",
        "schematic": "MÓDULO · ESQUEMA",
        "video": "MÓDULO · VÍDEO",
    }.get(kind, "MÓDULO"))
    payload: dict[str, Any] = {
        "label": args.get("label") or "",
        "board": case.get("board_model") or "",
        "symptom": case.get("symptom") or "",
    }
    if kind == "video":
        payload["url"] = args.get("url") or DEFAULT_VIDEO
        payload["label"] = payload["label"] or "Referência"
    elif kind == "board":
        if ss is not None:
            payload["has_image"] = bool(ss.get("last_image_bytes"))
            payload["name"] = ss.get("last_image_name") or "placa"
    elif kind == "schematic":
        if args.get("url"):
            payload["url"] = args["url"]

    mod = open_module(kind=kind, title=title, side=side, payload=payload)
    _log_action(ss, "open_module", f"{kind}@{side}")
    return {"ok": True, "opened": mod.get("id"), "kind": kind, "side": side, "title": title}


def _tool_close_modules(ss: Any, args: dict[str, Any]) -> dict[str, Any]:
    from .hud_modules import close_modules

    kind = str(args.get("kind") or "all").lower()
    if kind == "all":
        close_modules()
    else:
        close_modules(kind=kind)
    _log_action(ss, "close_modules", kind)
    return {"ok": True, "closed": kind}


def _tool_play_music(ss: Any, args: dict[str, Any]) -> dict[str, Any]:
    action = str(args.get("action") or "on").lower()
    style = str(args.get("style") or "synthwave").lower()
    if ss is None:
        return {"ok": False, "error": "sem sessão UI"}
    if action == "off":
        ss.music_on = False
    elif action == "toggle":
        ss.music_on = not bool(ss.music_on)
    else:
        ss.music_on = True
    # track por estilo
    style_map = {"synthwave": 0, "focus": 0, "lofi": 1, "ambient": 1}
    ss.music_track = style_map.get(style, 0)
    _log_action(ss, "play_music", f"{action}/{style} -> {ss.music_on}")
    return {"ok": True, "music_on": bool(ss.music_on), "style": style}


def _tool_update_hud(ss: Any, args: dict[str, Any]) -> dict[str, Any]:
    sensor = str(args.get("sensor") or "").lower()
    value = str(args.get("value") or "").strip()
    if not sensor or not value:
        return {"ok": False, "error": "sensor/value obrigatórios"}
    if ss is None:
        return {"ok": False, "error": "sem sessão UI"}
    overrides = dict(ss.get("hud_overrides") or {})
    overrides[sensor] = value
    ss.hud_overrides = overrides
    _log_action(ss, "update_hud", f"{sensor}={value}")
    return {"ok": True, "sensor": sensor, "value": value}


def _tool_save_note(ss: Any, args: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    text = str(args.get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "texto vazio"}
    prev = str(case.get("notes") or "")
    case["notes"] = (prev + "\n" + text).strip() if prev else text
    case.setdefault("operator_notes", [])
    if isinstance(case["operator_notes"], list):
        case["operator_notes"].append(
            {"text": text, "at": datetime.now(timezone.utc).isoformat(), "source": "agent"}
        )
    # também espelha no learning rápido da sessão
    if ss is not None:
        notes = list(ss.get("bench_notes") or [])
        notes.append(text)
        ss.bench_notes = notes[-50:]
    _log_action(ss, "save_note", text[:80])
    return {"ok": True, "saved": text[:200]}


def _tool_ack_error(ss: Any, args: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "summary": str(args.get("summary") or ""),
        "suggested_fix": str(args.get("suggested_fix") or ""),
        "severity": str(args.get("severity") or "medium"),
        "at": datetime.now(timezone.utc).isoformat(),
    }
    if ss is not None:
        log = list(ss.get("ui_heal_log") or [])
        log.append(entry)
        ss.ui_heal_log = log[-20:]
        # marca erros como reconhecidos
        errs = list(ss.get("ui_errors") or [])
        for e in errs:
            e["acked"] = True
        ss.ui_errors = errs
    _log_action(ss, "acknowledge_ui_error", entry["summary"][:80])
    return {"ok": True, "heal": entry}


def tools_as_openai() -> list[dict[str, Any]]:
    return TOOL_DEFINITIONS


def tools_as_anthropic() -> list[dict[str, Any]]:
    out = []
    for t in TOOL_DEFINITIONS:
        fn = t["function"]
        out.append(
            {
                "name": fn["name"],
                "description": fn["description"],
                "input_schema": fn["parameters"],
            }
        )
    return out


def format_actions_for_user(actions: list[dict[str, Any]]) -> str:
    if not actions:
        return ""
    bits = []
    for a in actions:
        name = a.get("name") or a.get("tool")
        if name == "open_module":
            bits.append(f"módulo `{a.get('kind', '?')}`")
        elif name == "play_music":
            bits.append("áudio de ambiente")
        elif name == "update_hud":
            bits.append(f"HUD {a.get('sensor')}")
        elif name == "save_note":
            bits.append("nota salva")
        elif name == "close_modules":
            bits.append("módulos fechados")
        elif name == "acknowledge_ui_error":
            bits.append("diagnóstico de UI")
    if not bits:
        return ""
    return "Ações: " + ", ".join(bits) + "."
