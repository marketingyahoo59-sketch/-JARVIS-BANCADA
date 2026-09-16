"""Agente autônomo de controle — o Jarvis opera o sistema, não conversa como chatbot."""

from __future__ import annotations

import json
from typing import Any

from .llm import call_llm
from .scene import scan_anomalies, screen_snapshot, verify_actions, has_ui


def _alerts_block(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return ""
    lines = ["ALERTA PROATIVO DA BANCADA (não espere o usuário pedir):"]
    for a in alerts:
        lines.append(f"- [{a.get('level')}] {a.get('text')}")
    lines.append(
        "Interrompa o papo. Execute tools (set_layout repair, play_ambient_sound alert, "
        "focus_component no rail). Informe o Sr. Igor. Se tensão perigosa: diga para desligar a fonte."
    )
    return "\n".join(lines)


def reason(
    case: dict[str, Any],
    user_text: str,
    image_bytes: bytes | None = None,
    image_mime: str = "image/jpeg",
    research_notes: str | None = None,
) -> dict[str, Any]:
    """Loop ANALISAR → PLANEJAR → EXECUTAR → VERIFICAR, depois a fala."""
    before = screen_snapshot()
    alerts = scan_anomalies(before)
    case["_screen"] = before
    case["_anomalies"] = alerts

    prompt = user_text or ""
    alert_txt = _alerts_block(alerts)
    if alert_txt:
        prompt = alert_txt + "\n\nMENSAGEM DO USUÁRIO:\n" + prompt

    result = call_llm(
        case,
        prompt,
        image_bytes=image_bytes,
        image_mime=image_mime,
        research_notes=research_notes,
    )

    after = screen_snapshot()
    actions = result.get("_agent_actions") or []
    checks = verify_actions(actions, after)
    failed = [c for c in checks if not c.get("ok")]
    if failed and has_ui():
        # Uma passagem extra: o operador corrige o que não refletiu na tela.
        fix_notes = json.dumps(failed, ensure_ascii=False)
        retry = call_llm(
            case,
            (
                "FASE VERIFICAR falhou. As ações abaixo não bateram com a tela.\n"
                f"{fix_notes}\n"
                f"TELA AGORA: {json.dumps(after, ensure_ascii=False)}\n"
                "Corrija com tools (refresh_component / set_layout / launch_module / "
                "close_all_modules) e só então fale com o Sr. Igor."
            ),
            research_notes=research_notes,
        )
        extra = retry.get("_agent_actions") or []
        if extra:
            actions = list(actions) + list(extra)
            retry["_agent_actions"] = actions
        # preserva fala da correção se veio
        if retry.get("assistant_message"):
            result = retry
            result["_agent_actions"] = actions
        after = screen_snapshot()
        checks = verify_actions(actions, after)

    result["_agent_actions"] = actions
    result["_reasoning"] = {
        "analyze": before,
        "anomalies": alerts,
        "execute": [
            {"name": a.get("name"), "ok": (a.get("result") or {}).get("ok")}
            for a in actions
        ],
        "verify": checks,
        "screen_after": after,
    }
    return result
