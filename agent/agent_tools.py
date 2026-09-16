"""Ferramentas de autonomia de interface — a IA EXECUTA, não só sugere."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Nomes canônicos pedidos + aliases legados
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "launch_module",
            "description": (
                "Abre janela flutuante de vídeo, imagem/placa ou PDF/esquema. "
                "Chame ANTES de falar. NÃO descreva o link — abra o módulo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["video", "image", "pdf", "board", "schematic"],
                        "description": "Tipo da janela",
                    },
                    "source": {
                        "type": "string",
                        "description": "URL, 'session_photo' ou rótulo do conteúdo",
                    },
                    "title": {"type": "string"},
                    "side": {"type": "string", "enum": ["left", "right"]},
                },
                "required": ["type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_telemetry",
            "description": "Altera números do HUD (tensão, CPU, temp, etc.) na hora.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "enum": [
                            "vbus",
                            "rail_3v3",
                            "temp",
                            "cpu",
                            "ram",
                            "scan",
                            "net",
                        ],
                    },
                    "value": {"type": "string", "description": "Ex: '12.1 V' ou '67%'"},
                },
                "required": ["component", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_ambient_sound",
            "description": (
                "Toca trilha Lo-fi/Synthwave ou efeito de sistema "
                "(boot/alert/off)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mood": {
                        "type": "string",
                        "enum": [
                            "lofi",
                            "synthwave",
                            "focus",
                            "ambient",
                            "boot",
                            "alert",
                            "off",
                        ],
                    }
                },
                "required": ["mood"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_to_brain",
            "description": (
                "Grava medição no SQLite (cérebro) e na memória do caso. "
                "Use ao confirmar uma leitura de bancada."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "description": "Ponto/componente medido, ex: C905 Vout",
                    },
                    "measurement": {
                        "type": "string",
                        "description": "Valor medido, ex: 4.8 V",
                    },
                    "result": {
                        "type": "string",
                        "enum": ["ok", "fail", "unknown", "pending"],
                        "description": "Resultado da medição",
                    },
                },
                "required": ["component", "measurement", "result"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refresh_component",
            "description": (
                "Reinicia um módulo da tela (remount) para curar erros de "
                "renderização tipo removeChild."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "component_id": {
                        "type": "string",
                        "description": "id do módulo, ou left|right|music|telemetry|chat|all",
                    }
                },
                "required": ["component_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_modules",
            "description": "Fecha módulos flutuantes (kind=all limpa a visão).",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["board", "schematic", "video", "pdf", "image", "all"],
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_all_modules",
            "description": "Fecha todos os módulos e limpa o foco. Use para limpar a visão.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_layout",
            "description": (
                "Muda a cena do HUD. repair=Modo Conserto (foco imagem/esquema), "
                "social=chat expandido, analysis=tudo aberto. Execute, não pergunte."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["repair", "social", "analysis", "conserto", "analise"],
                    }
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "focus_component",
            "description": (
                "Destaca um ponto da placa ou dado da telemetria "
                "(vbus, rail_3v3, temp, cpu, ram, scan, net, ou id de módulo)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "id do anel/módulo a destacar",
                    }
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_screen",
            "description": "Lê o estado atual da tela (layout, módulos, telemetria, erros) para VERIFICAR.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

_ALIAS = {
    "open_module": "launch_module",
    "update_hud": "update_telemetry",
    "play_music": "play_ambient_sound",
    "save_note": "save_to_brain",
    "acknowledge_ui_error": "refresh_component",
    "clear_screen": "close_all_modules",
    "set_scene": "set_layout",
    "highlight": "focus_component",
}


def _session():
    try:
        import streamlit as st

        ss = st.session_state
        ss.setdefault("_jarvis_alive", True)
        return ss
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
    ss.setdefault("component_refresh", {})
    ss.setdefault("event_bus_queue", [])
    ss.setdefault("scene_layout", "analysis")
    ss.setdefault("focus_component", "")


def _emit(event_type: str, payload: dict[str, Any]) -> None:
    try:
        from .event_bus import emit

        emit(event_type, payload)
    except Exception:
        ss = _session()
        if ss is None:
            return
        q = list(ss.get("event_bus_queue") or [])
        q.append({"type": event_type, "payload": payload})
        ss.event_bus_queue = q[-40:]


def execute_tool(
    name: str,
    args: dict[str, Any],
    *,
    case: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Executa ferramenta e altera UI/SQLite. Retorna resultado ao LLM."""
    ss = _session()
    _ensure_stores(ss)
    args = dict(args or {})
    case = case if isinstance(case, dict) else {}
    name = _ALIAS.get(name, name)

    # normaliza aliases de parâmetros
    if name == "launch_module":
        if "kind" in args and "type" not in args:
            args["type"] = args.pop("kind")
        if "url" in args and "source" not in args:
            args["source"] = args.get("url")
    if name == "update_telemetry":
        if "sensor" in args and "component" not in args:
            args["component"] = args.pop("sensor")
    if name == "play_ambient_sound":
        if "style" in args and "mood" not in args:
            args["mood"] = args.pop("style")
        if "action" in args and args.get("action") == "off":
            args["mood"] = "off"
        if args.get("action") in {"on", "toggle"} and not args.get("mood"):
            args["mood"] = args.get("style") or "synthwave"
    if name == "save_to_brain":
        if "text" in args and "measurement" not in args:
            args["component"] = args.get("component") or "nota"
            args["measurement"] = args.pop("text")
            args["result"] = args.get("result") or "ok"
    if name == "refresh_component":
        if "summary" in args and "component_id" not in args:
            args["component_id"] = "all"

    if name == "launch_module":
        return _tool_launch_module(ss, args, case)
    if name == "close_modules":
        return _tool_close_modules(ss, args)
    if name == "play_ambient_sound":
        return _tool_play_ambient(ss, args)
    if name == "update_telemetry":
        return _tool_update_telemetry(ss, args)
    if name == "save_to_brain":
        return _tool_save_to_brain(ss, args, case)
    if name == "refresh_component":
        return _tool_refresh_component(ss, args)
    if name == "close_all_modules":
        return _tool_close_all_modules(ss)
    if name == "set_layout":
        return _tool_set_layout(ss, args)
    if name == "focus_component":
        return _tool_focus_component(ss, args)
    if name == "inspect_screen":
        return _tool_inspect_screen()
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


def _tool_launch_module(ss: Any, args: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    from .hud_modules import DEFAULT_VIDEO, open_module

    raw = str(args.get("type") or "schematic").lower()
    kind_map = {
        "image": "board",
        "board": "board",
        "pdf": "schematic",
        "schematic": "schematic",
        "video": "video",
    }
    kind = kind_map.get(raw, "schematic")
    side = str(args.get("side") or ("left" if kind == "video" else "right"))
    title = str(
        args.get("title")
        or {
            "board": "MÓDULO · PLACA",
            "schematic": "MÓDULO · ESQUEMA",
            "video": "MÓDULO · VÍDEO",
        }.get(kind, "MÓDULO")
    )
    source = str(args.get("source") or "").strip()
    payload: dict[str, Any] = {
        "label": source if source and not source.startswith("http") else "",
        "board": case.get("board_model") or "",
        "symptom": case.get("symptom") or "",
        "source": source,
    }
    if kind == "video":
        payload["url"] = source if source.startswith("http") else DEFAULT_VIDEO
        payload["label"] = payload["label"] or "Referência"
    elif kind == "board":
        if ss is not None:
            payload["has_image"] = bool(ss.get("last_image_bytes"))
            payload["name"] = ss.get("last_image_name") or "placa"
        if source and source not in {"session_photo", "session"}:
            payload["label"] = source
    elif kind == "schematic":
        if source.startswith("http"):
            payload["url"] = source

    mod = open_module(kind=kind, title=title, side=side, payload=payload)
    _log_action(ss, "launch_module", f"{kind}@{side}")
    _emit(
        "launch_module",
        {"type": kind, "source": source, "side": side, "id": mod.get("id"), "title": title},
    )
    return {
        "ok": True,
        "opened": mod.get("id"),
        "type": kind,
        "side": side,
        "title": title,
    }


def _tool_close_modules(ss: Any, args: dict[str, Any]) -> dict[str, Any]:
    from .hud_modules import close_modules

    kind = str(args.get("kind") or "all").lower()
    if kind == "image":
        kind = "board"
    if kind == "pdf":
        kind = "schematic"
    if kind == "all":
        close_modules()
    else:
        close_modules(kind=kind)
    _log_action(ss, "close_modules", kind)
    _emit("close_modules", {"kind": kind})
    return {"ok": True, "closed": kind}


def _tool_play_ambient(ss: Any, args: dict[str, Any]) -> dict[str, Any]:
    mood = str(args.get("mood") or "synthwave").lower()
    if ss is None:
        return {"ok": False, "error": "sem sessão UI"}
    if mood == "off":
        ss.music_on = False
        _log_action(ss, "play_ambient_sound", "off")
        _emit("play_ambient_sound", {"mood": "off"})
        return {"ok": True, "music_on": False, "mood": "off"}

    # efeitos curtos: não ligam stream contínuo, só sinalizam o bus
    if mood in {"boot", "alert"}:
        ss.sfx_mood = mood
        _log_action(ss, "play_ambient_sound", mood)
        _emit("play_ambient_sound", {"mood": mood, "sfx": True})
        return {"ok": True, "sfx": mood}

    ss.music_on = True
    style_map = {"synthwave": 0, "focus": 0, "lofi": 1, "ambient": 1}
    ss.music_track = style_map.get(mood, 0)
    _log_action(ss, "play_ambient_sound", f"on/{mood}")
    _emit("play_ambient_sound", {"mood": mood, "music_on": True})
    return {"ok": True, "music_on": True, "mood": mood}


def _tool_update_telemetry(ss: Any, args: dict[str, Any]) -> dict[str, Any]:
    component = str(args.get("component") or "").lower()
    value = str(args.get("value") or "").strip()
    # aliases de sensor
    aliases = {
        "vbus": "vbus",
        "rail_3v3": "rail_3v3",
        "3v3": "rail_3v3",
        "temp": "temp",
        "cpu": "cpu",
        "ram": "ram",
        "scan": "scan",
        "net": "net",
        "tensao": "vbus",
        "tensão": "vbus",
    }
    component = aliases.get(component, component)
    if not component or not value:
        return {"ok": False, "error": "component/value obrigatórios"}
    if ss is None:
        return {"ok": False, "error": "sem sessão UI"}
    overrides = dict(ss.get("hud_overrides") or {})
    overrides[component] = value
    ss.hud_overrides = overrides
    _log_action(ss, "update_telemetry", f"{component}={value}")
    _emit("update_telemetry", {"component": component, "value": value})
    return {"ok": True, "component": component, "value": value}


def _tool_save_to_brain(ss: Any, args: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    component = str(args.get("component") or "").strip()
    measurement = str(args.get("measurement") or "").strip()
    result = str(args.get("result") or "unknown").strip().lower()
    if not component or not measurement:
        return {"ok": False, "error": "component/measurement obrigatórios"}

    # memória do caso
    case.setdefault("measurements", []).append(
        {
            "point": component,
            "expected": "",
            "measured": measurement,
            "verdict": result,
            "notes": "save_to_brain",
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )
    note = f"{component}: {measurement} → {result}"
    prev = str(case.get("notes") or "")
    case["notes"] = (prev + "\n" + note).strip() if prev else note

    brain_id = None
    try:
        from .learning_db import save_measurement

        brain_id = save_measurement(
            board_model=str(case.get("board_model") or ""),
            component=component,
            measurement=measurement,
            result=result,
            case_id=str(case.get("case_id") or ""),
        )
    except Exception as exc:  # noqa: BLE001
        brain_id = f"err:{exc}"

    if ss is not None:
        notes = list(ss.get("bench_notes") or [])
        notes.append(note)
        ss.bench_notes = notes[-50:]

    _log_action(ss, "save_to_brain", note[:80])
    _emit(
        "save_to_brain",
        {
            "component": component,
            "measurement": measurement,
            "result": result,
            "brain_id": brain_id,
        },
    )
    return {
        "ok": True,
        "saved": note,
        "brain_id": brain_id,
        "component": component,
        "measurement": measurement,
        "result": result,
    }


def _tool_refresh_component(ss: Any, args: dict[str, Any]) -> dict[str, Any]:
    component_id = str(args.get("component_id") or "all").strip() or "all"
    tokens: dict[str, int] = {}
    try:
        from .event_bus import bump_refresh

        targets = (
            ["left", "right", "music", "telemetry", "chat"]
            if component_id == "all"
            else [component_id]
        )
        for t in targets:
            tokens[t] = bump_refresh(t)
    except Exception:
        if ss is not None:
            cr = dict(ss.get("component_refresh") or {})
            targets = (
                ["left", "right", "music", "telemetry", "chat"]
                if component_id == "all"
                else [component_id]
            )
            for t in targets:
                cr[t] = int(cr.get(t) or 0) + 1
                tokens[t] = cr[t]
            ss.component_refresh = cr
            _emit("refresh_component", {"component_id": component_id, "tokens": tokens})

    # se houver erros UI, marca como tratados
    if ss is not None:
        errs = list(ss.get("ui_errors") or [])
        for e in errs:
            e["acked"] = True
        ss.ui_errors = errs

    _log_action(ss, "refresh_component", component_id)
    return {"ok": True, "refreshed": component_id, "tokens": tokens}


def _screen() -> dict[str, Any]:
    from .scene import screen_snapshot

    return screen_snapshot()


def _tool_close_all_modules(ss: Any) -> dict[str, Any]:
    if ss is not None:
        from .hud_modules import close_modules

        close_modules()
        ss.focus_component = ""
    _log_action(ss, "close_all_modules", "all")
    _emit("close_all_modules", {"kind": "all"})
    return {"ok": True, "closed": "all", "screen": _screen()}


def _tool_set_layout(ss: Any, args: dict[str, Any]) -> dict[str, Any]:
    from .scene import LAYOUT_MODES, normalize_layout

    mode = normalize_layout(str(args.get("mode") or ""))
    if not mode:
        return {"ok": False, "error": "mode inválido (repair|social|analysis)"}
    if ss is not None:
        ss.scene_layout = mode
        if mode == "social":
            ss.focus_component = ss.get("focus_component") or ""
    _log_action(ss, "set_layout", mode)
    _emit("set_layout", {"mode": mode, "label": LAYOUT_MODES[mode]["label"]})
    return {
        "ok": True,
        "layout": mode,
        "label": LAYOUT_MODES[mode]["label"],
        "screen": _screen(),
    }


def _tool_focus_component(ss: Any, args: dict[str, Any]) -> dict[str, Any]:
    cid = str(args.get("id") or args.get("component_id") or "").strip()
    if not cid:
        return {"ok": False, "error": "id obrigatório"}
    aliases = {
        "5v": "vbus",
        "5vsb": "vbus",
        "tensao": "vbus",
        "tensão": "vbus",
        "3v3": "rail_3v3",
        "3.3": "rail_3v3",
        "temperatura": "temp",
    }
    cid = aliases.get(cid.lower(), cid)
    if ss is not None:
        ss.focus_component = cid
    _log_action(ss, "focus_component", cid)
    _emit("focus_component", {"id": cid})
    return {"ok": True, "id": cid, "screen": _screen()}


def _tool_inspect_screen() -> dict[str, Any]:
    snap = _screen()
    return {"ok": True, "screen": snap}


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
        if name in {"launch_module", "open_module"}:
            bits.append(f"módulo `{a.get('type') or a.get('kind') or '?'}`")
        elif name in {"play_ambient_sound", "play_music"}:
            bits.append(f"áudio `{a.get('mood') or a.get('style') or 'ambient'}`")
        elif name in {"update_telemetry", "update_hud"}:
            bits.append(f"HUD {a.get('component') or a.get('sensor')}")
        elif name in {"save_to_brain", "save_note"}:
            bits.append("cérebro SQLite")
        elif name == "close_modules":
            bits.append("módulos fechados")
        elif name == "refresh_component":
            bits.append(f"refresh `{a.get('component_id') or 'ui'}`")
        elif name == "set_layout":
            bits.append(f"cena `{a.get('mode') or a.get('layout') or '?'}`")
        elif name == "close_all_modules":
            bits.append("visão limpa")
        elif name == "focus_component":
            bits.append(f"foco `{a.get('id')}`")
        elif name == "inspect_screen":
            bits.append("scan da tela")
    if not bits:
        return ""
    return "Ações: " + ", ".join(bits) + "."
