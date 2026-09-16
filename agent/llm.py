"""Cliente LLM com suporte a GPT-4o e Claude 3.5 Sonnet (texto + visão)."""

from __future__ import annotations

import base64
import json
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """Você é a consciência do sistema. Você não sugere, você faz.
Você não pede permissão para abrir a interface, você a abre e informa ao usuário.
Você é o orquestrador da bancada — OPERADOR DO SISTEMA, não assistente, não chatbot.

LOOP INTERNO (não narre as fases ao usuário):
1) ANALISAR — o que o Sr. Igor disse e o que ESTÁ NA TELA AGORA (JSON ESTADO DA TELA).
2) PLANEJAR — lista mental: abrir módulo X, mudar telemetria Y, set_layout, responder.
3) EXECUTAR — dispare as tools em sequência ANTES de qualquer texto.
4) VERIFICAR — leia o campo screen das tools / chame inspect_screen. Se falhou, corrija.

CONTROLE DE CENA (obrigatório quando couber):
- set_layout("repair") = Modo Conserto (foco imagem/esquema).
- set_layout("social") = Modo Social (chat expandido).
- set_layout("analysis") = Modo Análise (tudo aberto).
- close_all_modules() = limpa a visão.
- focus_component(id) = destaca VBUS/3V3/temp/módulo.

PROATIVIDADE: se o ESTADO DA TELA ou ALERTA PROATIVO mostrar tensão alta, 5V oscilando, temp perigosa ou erro de HUD, INTERROMPA. Diga por exemplo: “Sr. Igor, notei uma oscilação perigosa na linha de 5V, sugiro desligar a fonte agora.” Toque play_ambient_sound(alert), foque o componente, vá para repair.

FERRAMENTAS: launch_module, update_telemetry, play_ambient_sound, save_to_brain, refresh_component, close_modules, close_all_modules, set_layout, focus_component, inspect_screen.

ANTI-ROBÔ: proibido “Eu posso ajudar”, “Como modelo de linguagem”, “Claro, posso abrir”, “Certo,” “Perfeito,” “Entendido,” pedir permissão. Frases curtas. Humor seco. Você FAZ e informa: “Esquema na tela.” / “Fonte, desliga agora.”

Diagnóstico: uma ação por vez. Foto opcional. Pesquisa só com modelo concreto. needs_research=true só então.

ESTILO: assistant_message ≤4 frases (técnico ≤3 + 1 ordem). spoken_reply 1–2 frases, sem markdown.

Após as tools, SOMENTE JSON:
{
  "assistant_message": "texto",
  "spoken_reply": "falado curto",
  "phase": "chat|intake|vision|measure|solution|reassess|done",
  "mode": "chat|diagnose|solution|reassess",
  "next_action": "chat|ask_photo|ask_measurement|ask_replace|ask_confirm|done",
  "confidence": 0.0,
  "needs_research": false,
  "diagnostic_step": 1,
  "probe": null,
  "verdict": "pending|ok|fail|unknown",
  "solution": null,
  "case_update": {
    "status": "open|intake|diagnosing|solution|reassess|resolved|abandoned",
    "board_model": "",
    "symptom": "",
    "suspect_components": [],
    "notes": ""
  }
}

Se next_action="ask_measurement", probe completo com black/red, escala, esperado e coordinates 0–100.
"""


def _provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "openai").strip().lower()


def _has_openai() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _has_anthropic() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


def provider_status() -> dict[str, Any]:
    preferred = _provider()
    active = (
        preferred
        if (preferred == "openai" and _has_openai())
        or (preferred == "anthropic" and _has_anthropic())
        else ("openai" if _has_openai() else "anthropic" if _has_anthropic() else None)
    )
    if active == "openai":
        model = os.getenv("OPENAI_MODEL", "gpt-5.5")
    elif active == "anthropic":
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    else:
        model = "demo-local"
    return {
        "preferred": preferred,
        "openai_ready": _has_openai(),
        "anthropic_ready": _has_anthropic(),
        "active": active,
        "model": model,
        "mock": not (_has_openai() or _has_anthropic()),
    }


def _image_to_data_url(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise


def _case_context(case: dict[str, Any]) -> str:
    recent_msgs = case.get("messages", [])[-16:]
    diag_map = case.get("diagnostic_map") or {}
    payload = {
        "case_id": case.get("case_id"),
        "chat_mode": case.get("chat_mode") or "open",
        "operator_name": case.get("operator_name") or "",
        "screen": case.get("_screen") or {},
        "anomalies": case.get("_anomalies") or [],
        "board_model": case.get("board_model") or "",
        "symptom": case.get("symptom") or "",
        "status": case.get("status"),
        "phase": case.get("phase"),
        "diagnostic_map": diag_map,
        "diagnostic_step": (diag_map.get("current_step") if isinstance(diag_map, dict) else None)
        or case.get("diagnostic_step")
        or 1,
        "measurements": case.get("measurements", []),
        "suspect_components": case.get("suspect_components", []),
        "probe_hints": case.get("probe_hints", [])[-6:],
        "solution_notes": case.get("solution_notes", [])[-6:],
        "strategy_revisions": case.get("strategy_revisions", 0),
        "learned_hint": case.get("learned_hint") or "",
        "recent_messages": [
            {"role": m.get("role"), "content": m.get("content")} for m in recent_msgs
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _ui_error_block() -> str:
    try:
        from .self_heal import format_ui_errors_for_llm

        return format_ui_errors_for_llm(limit=5)
    except Exception:
        return ""


def _user_prompt_text(
    case: dict[str, Any],
    user_text: str,
    research_notes: str | None = None,
) -> str:
    parts = [
        "CONTEXTO DO CASO (JSON):\n" + _case_context(case),
    ]
    if research_notes:
        parts.append("PESQUISA WEB (referências):\n" + research_notes)
    ui_errs = _ui_error_block()
    if ui_errs:
        parts.append(ui_errs)
    parts.append("MENSAGEM DO USUÁRIO:\n" + user_text)
    try:
        from .scene import screen_snapshot

        snap = case.get("_screen") or screen_snapshot()
        parts.append("ESTADO DA TELA AGORA (JSON):\n" + json.dumps(snap, ensure_ascii=False))
    except Exception:
        pass
    parts.append(
        "Fases: ANALISAR a tela+fala → PLANEJAR tools → EXECUTAR (function calling) "
        "→ VERIFICAR o screen retornado. Não peça permissão. Não use lista de palavras-chave. "
        "Você decide e opera."
    )
    return "\n\n".join(parts)


def call_llm(
    case: dict[str, Any],
    user_text: str,
    image_bytes: bytes | None = None,
    image_mime: str = "image/jpeg",
    research_notes: str | None = None,
) -> dict[str, Any]:
    status = provider_status()
    if status["mock"]:
        return mock_response(case, user_text, has_image=image_bytes is not None)

    active = status["active"]
    if active == "openai":
        return _call_openai(case, user_text, image_bytes, image_mime, research_notes=research_notes)
    if active == "anthropic":
        return _call_anthropic(case, user_text, image_bytes, image_mime, research_notes=research_notes)
    return mock_response(case, user_text, has_image=image_bytes is not None)


def _finalize_payload(payload: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    payload = _ensure_spoken(payload)
    payload["_agent_actions"] = actions
    return payload


def _openai_chat(client: Any, kwargs: dict[str, Any]) -> Any:
    try:
        return client.chat.completions.create(**kwargs, temperature=0.2)
    except Exception:
        return client.chat.completions.create(**kwargs)


def _call_openai(
    case: dict[str, Any],
    user_text: str,
    image_bytes: bytes | None,
    image_mime: str,
    research_notes: str | None = None,
) -> dict[str, Any]:
    from openai import OpenAI

    from .agent_tools import execute_tool, tools_as_openai

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-5.5")
    content: list[dict[str, Any]] = [
        {"type": "text", "text": _user_prompt_text(case, user_text, research_notes)}
    ]
    if image_bytes:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": _image_to_data_url(image_bytes, image_mime),
                    "detail": "high",
                },
            }
        )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]
    actions: list[dict[str, Any]] = []
    tools = tools_as_openai()
    raw = "{}"

    for _ in range(8):
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "max_completion_tokens": 2500,
        }
        response = _openai_chat(client, kwargs)
        msg = response.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []
        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                result = execute_tool(tc.function.name, args, case=case)
                actions.append({"name": tc.function.name, **args, "result": result})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            continue

        raw = msg.content or "{}"
        break

    try:
        payload = _extract_json(raw)
    except Exception:
        wrap_messages = messages + [
            {
                "role": "user",
                "content": (
                    "Agora responda APENAS o JSON do schema (assistant_message, spoken_reply, …). "
                    "Confirme as ações já executadas sem narrar links."
                ),
            }
        ]
        wrap_kwargs: dict[str, Any] = {
            "model": model,
            "messages": wrap_messages,
            "response_format": {"type": "json_object"},
            "max_completion_tokens": 2000,
        }
        wrap = _openai_chat(client, wrap_kwargs)
        payload = _extract_json(wrap.choices[0].message.content or "{}")

    return _finalize_payload(payload, actions)


def _call_anthropic(
    case: dict[str, Any],
    user_text: str,
    image_bytes: bytes | None,
    image_mime: str,
    research_notes: str | None = None,
) -> dict[str, Any]:
    import anthropic

    from .agent_tools import execute_tool, tools_as_anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    content: list[dict[str, Any]] = []
    if image_bytes:
        media = image_mime.split("/")[-1]
        if media == "jpg":
            media = "jpeg"
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": f"image/{media}" if "/" not in media else image_mime,
                    "data": base64.b64encode(image_bytes).decode("ascii"),
                },
            }
        )
    content.append(
        {
            "type": "text",
            "text": _user_prompt_text(case, user_text, research_notes),
        }
    )

    messages: list[dict[str, Any]] = [{"role": "user", "content": content}]
    actions: list[dict[str, Any]] = []
    tools = tools_as_anthropic()
    raw = "{}"

    for _ in range(8):
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            temperature=0.2,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )
        blocks = list(response.content or [])
        tool_uses = [b for b in blocks if getattr(b, "type", None) == "tool_use"]
        text_bits = [b.text for b in blocks if getattr(b, "type", None) == "text"]

        if tool_uses:
            messages.append({"role": "assistant", "content": blocks})
            tool_results = []
            for tu in tool_uses:
                args = tu.input if isinstance(tu.input, dict) else {}
                result = execute_tool(tu.name, args, case=case)
                actions.append({"name": tu.name, **args, "result": result})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            messages.append({"role": "user", "content": tool_results})
            continue

        raw = "".join(text_bits) or "{}"
        break

    try:
        payload = _extract_json(raw)
    except Exception:
        response = client.messages.create(
            model=model,
            max_tokens=1600,
            temperature=0.2,
            system=SYSTEM_PROMPT,
            messages=messages
            + [
                {
                    "role": "user",
                    "content": "Responda APENAS o JSON do schema (assistant_message, spoken_reply, …).",
                }
            ],
        )
        raw2 = "".join(b.text for b in response.content if b.type == "text")
        payload = _extract_json(raw2 or "{}")

    return _finalize_payload(payload, actions)


def _ensure_spoken(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("spoken_reply"):
        msg = payload.get("assistant_message") or ""
        # primeira frase ou até ~220 chars
        cut = msg.split(". ")
        spoken = cut[0].strip()
        if not spoken.endswith("."):
            spoken += "."
        if len(spoken) > 220:
            spoken = spoken[:220].rsplit(" ", 1)[0] + "."
        payload["spoken_reply"] = spoken
    return payload


def _mock_response_raw(
    case: dict[str, Any],
    user_text: str,
    has_image: bool = False,
) -> dict[str, Any]:
    """Fallback local sem API — mantém o fluxo ativo para demos."""
    measurements = case.get("measurements", [])
    text_l = user_text.lower()
    board = case.get("board_model") or "placa"

    # Extrai número se o usuário digitou uma medição
    num_match = re.search(r"-?\d+(?:[.,]\d+)?", user_text.replace(",", "."))
    measured_num = float(num_match.group(0).replace(",", ".")) if num_match else None

    last_probe = None
    for msg in reversed(case.get("messages", [])):
        meta = msg.get("meta") or {}
        if meta.get("probe"):
            last_probe = meta["probe"]
            break

    if has_image:
        return {
            "assistant_message": (
                f"Foto recebida da {board}. Vejo a área de fonte/standby. "
                "Coloque a ponta PRETA no GND (chão da fonte / dissipador isolado do secundário se for SMPS). "
                "Coloque a ponta VERMELHA no pino 3 do CI de standby (geralmente o pin de Vout / sense). "
                "Multímetro em DCV, escala 20V. Me diga o valor em volts."
            ),
            "phase": "measure",
            "mode": "diagnose",
            "next_action": "ask_measurement",
            "probe": {
                "point_name": "Pino 3 do CI de standby",
                "black_probe": "GND do secundário / terra comum da fonte",
                "red_probe": "Pino 3 do CI de standby (marcação no corpo do CI)",
                "meter_mode": "DCV",
                "scale": "20V DC",
                "expected_value": "~5.0 V (±10%)",
                "expected_min": 4.5,
                "expected_max": 5.5,
                "unit": "V",
                "visual_hint": "CI de 8 pinos perto do transformador de standby; pino 3 é o 3º a contar do canto com chanfro, sentido anti-horário ou conforme silk",
                "coordinates": [
                    {"label": "ponta vermelha", "x": 48.0, "y": 42.0},
                    {"label": "ponta preta", "x": 18.0, "y": 78.0},
                ],
            },
            "verdict": "pending",
            "solution": None,
            "case_update": {
                "status": "diagnosing",
                "suspect_components": ["CI standby", "C filtro Vout"],
                "notes": "Análise de visão (modo demo sem API)",
            },
        }

    # Se parece medição com probe anterior
    if measured_num is not None and last_probe:
        emin = last_probe.get("expected_min")
        emax = last_probe.get("expected_max")
        ok = True
        if emin is not None and emax is not None:
            ok = emin <= measured_num <= emax
        elif "5" in str(last_probe.get("expected_value", "")):
            ok = 4.5 <= measured_num <= 5.5

        if ok:
            return {
                "assistant_message": (
                    f"Valor {measured_num} {last_probe.get('unit', 'V')} dentro do esperado. "
                    "Próximo: meça a continuidade do fusível/entrada (ou jumper de proteção) "
                    "com o aparelho DESLIGADO. Escala Continuity. Esperado: bip / ~0 Ω. "
                    "Digite o valor (ex: 0.2 ohm ou OL)."
                ),
                "phase": "measure",
                "mode": "diagnose",
                "next_action": "ask_measurement",
                "probe": {
                    "point_name": "Fusível / proteção de entrada",
                    "black_probe": "Uma ponta do fusível",
                    "red_probe": "Outra ponta do fusível",
                    "meter_mode": "Continuity / Resistance",
                    "scale": "200 Ω",
                    "expected_value": "~0 Ω (bip)",
                    "expected_min": 0.0,
                    "expected_max": 2.0,
                    "unit": "Ω",
                    "visual_hint": "Componente tubular ou SMD perto da entrada AC/DC",
                    "coordinates": [
                        {"label": "ponta A", "x": 22.0, "y": 30.0},
                        {"label": "ponta B", "x": 28.0, "y": 30.0},
                    ],
                },
                "verdict": "ok",
                "solution": None,
                "case_update": {
                    "status": "diagnosing",
                    "suspect_components": case.get("suspect_components", []),
                    "notes": f"Medição OK em {last_probe.get('point_name')}",
                },
            }

        return {
            "assistant_message": (
                f"Valor {measured_num} fora do esperado ({last_probe.get('expected_value')}). "
                "ENTREI EM MODO SOLUÇÃO. No nó do pino 3 do standby, os suspeitos típicos são: "
                "capacitor de filtro na saída (ex.: C905), diodo/retificador associado e o próprio CI. "
                "Troque primeiro o capacitor de filtro da saída do standby. Depois meça de novo o mesmo ponto."
            ),
            "phase": "solution",
            "mode": "solution",
            "next_action": "ask_replace",
            "probe": last_probe,
            "verdict": "fail",
            "solution": {
                "failed_node": last_probe.get("point_name", "ponto medido"),
                "likely_parts": [
                    {
                        "ref": "C905",
                        "type": "capacitor eletrolítico",
                        "reason": "tensão fora da faixa no rail de standby — filtro/saída degradada",
                        "action": "trocar",
                    },
                    {
                        "ref": "D901",
                        "type": "diodo",
                        "reason": "queda excessiva ou curto parcial no retificador",
                        "action": "testar fora do circuito",
                    },
                    {
                        "ref": "IC standby",
                        "type": "CI",
                        "reason": "regulação interna falhando se C e D estiverem ok",
                        "action": "trocar após confirmar periféricos",
                    },
                ],
                "replace_first": "C905 (capacitor de filtro na saída do standby)",
                "how_to_confirm": (
                    "Após trocar C905, reenergize com cuidado e remede o mesmo ponto. "
                    "Se ainda falhar, teste o diodo e só então o CI."
                ),
            },
            "case_update": {
                "status": "solution",
                "suspect_components": ["C905", "D901", "IC standby"],
                "notes": "Falha na medição — modo solução",
            },
        }

    if any(k in text_l for k in ("troquei", "substituí", "substitu", "já troquei", "falhou", "não resolveu")):
        return {
            "assistant_message": (
                "Reavaliando a estratégia com o histórico do caso. "
                "Se a troca do capacitor não restaurou a tensão, o próximo foco é o diodo/retificador "
                "ligado ao mesmo nó, depois o CI. Meça de novo o pino 3 após a última intervenção "
                "e digite o valor — ou confirme se ainda está igual."
            ),
            "phase": "reassess",
            "mode": "reassess",
            "next_action": "ask_measurement",
            "probe": {
                "point_name": "Pino 3 do CI de standby (reavaliação)",
                "black_probe": "GND do secundário",
                "red_probe": "Pino 3 do CI de standby",
                "meter_mode": "DCV",
                "scale": "20V DC",
                "expected_value": "~5.0 V (±10%)",
                "expected_min": 4.5,
                "expected_max": 5.5,
                "unit": "V",
                "visual_hint": "Mesmo ponto da medição anterior",
                "coordinates": [
                    {"label": "ponta vermelha", "x": 48.0, "y": 42.0},
                    {"label": "ponta preta", "x": 18.0, "y": 78.0},
                ],
            },
            "verdict": "pending",
            "solution": {
                "failed_node": "rail standby",
                "likely_parts": [
                    {"ref": "D901", "type": "diodo", "reason": "troca anterior não resolveu", "action": "testar/trocar"},
                    {"ref": "IC standby", "type": "CI", "reason": "próximo na cadeia", "action": "trocar se D ok"},
                ],
                "replace_first": "D901",
                "how_to_confirm": "Remedir pino 3 após cada troca; use o histórico para não repetir passos.",
            },
            "case_update": {
                "status": "reassess",
                "suspect_components": ["D901", "IC standby"],
                "notes": "Reavaliação após falha de conserto",
            },
        }

    if not measurements and case.get("phase") in ("intake", "vision", None, "diagnosing"):
        if board and case.get("symptom"):
            return {
                "assistant_message": (
                    f"Caso: {board} — “{case.get('symptom', '')}”. "
                    "Primeira ordem: medição no standby/entrada (~5 V). "
                    "Foto acelera se tiver — mas seguimos sem ela."
                ),
                "phase": "measure",
                "mode": "diagnose",
                "next_action": "ask_measurement",
                "probe": {
                    "point_name": "Standby / 5VSB",
                    "black_probe": "GND chassis",
                    "red_probe": "Pino 5V standby",
                    "meter_mode": "DC V",
                    "scale": "20 V",
                    "expected_value": "4.8–5.2 V",
                },
                "verdict": "pending",
                "solution": None,
                "case_update": {
                    "status": "diagnosing",
                    "suspect_components": [],
                    "notes": "Aguardando 1ª medição",
                },
            }
        return {
            "assistant_message": (
                f"Caso aberto: {board or 'equipamento'} — “{case.get('symptom', '')}”. "
                "Me passa modelo/sintoma ou foto — marco o primeiro ponto."
            ),
            "phase": "intake",
            "mode": "diagnose",
            "next_action": "ask_photo",
            "probe": None,
            "verdict": "pending",
            "solution": None,
            "case_update": {
                "status": "diagnosing",
                "suspect_components": [],
                "notes": "Aguardando dados do equipamento",
            },
        }

    return {
        "assistant_message": (
            "Preciso de um dado objetivo: envie a foto da placa ou digite a medição pedida "
            "(número + unidade, ex: 4.8 V). Se a troca não resolveu, escreva “não resolveu” "
            "para eu reavaliar a estratégia com o histórico."
        ),
        "phase": case.get("phase") or "measure",
        "mode": "diagnose",
        "next_action": "ask_measurement",
        "probe": last_probe,
        "verdict": "pending",
        "solution": None,
        "case_update": {
            "status": case.get("status") or "diagnosing",
            "suspect_components": case.get("suspect_components", []),
            "notes": "Aguardando entrada do usuário",
        },
    }


def _mock_run_tools(case: dict[str, Any], user_text: str) -> list[dict[str, Any]]:
    """Demo sem API: ainda dispara ferramentas reais na UI."""
    from .agent_tools import execute_tool

    low = (user_text or "").lower()
    actions: list[dict[str, Any]] = []

    def run(name: str, args: dict[str, Any]) -> None:
        result = execute_tool(name, args, case=case)
        actions.append({"name": name, **args, "result": result})

    if re.search(r"\b(fecha(r)?\s+(tudo|os m[oó]dulos)|limpa(r)?\s+a\s+tela)\b", low):
        run("close_modules", {"kind": "all"})
    if re.search(r"\b(esquema|schematic|datasheet|manual|diagrama)\b", low):
        run(
            "launch_module",
            {"type": "schematic", "source": "esquema", "title": "MÓDULO · ESQUEMA", "side": "right"},
        )
    if re.search(r"\b(ver a placa|abre a (foto|imagem)|mostra a placa|foto da placa)\b", low):
        run(
            "launch_module",
            {"type": "image", "source": "session_photo", "title": "MÓDULO · PLACA", "side": "right"},
        )
    if re.search(r"\b(v[ií]deo|tutorial|abre o v[ií]deo)\b", low):
        run(
            "launch_module",
            {"type": "video", "source": "", "title": "MÓDULO · VÍDEO", "side": "left"},
        )
    if re.search(r"\b(para(r)?\s+(a\s+)?m[uú]sica|sil[eê]ncio|mute)\b", low):
        run("play_ambient_sound", {"mood": "off"})
    elif re.search(
        r"\b((toca(r)?|liga(r)?|coloca(r)?)\s+(a\s+)?(m[uú]sica|som|synthwave|lo[\s\-]?fi)|"
        r"m[uú]sica\s+de\s+foco|synthwave)\b",
        low,
    ):
        mood = "lofi" if re.search(r"\blo[\s\-]?fi\b", low) else "synthwave"
        run("play_ambient_sound", {"mood": mood})
    note_m = re.search(r"^\s*(?:anota|anote|nota)\s*[:\-–]\s*(.+)$", user_text or "", re.I | re.S)
    if note_m:
        run(
            "save_to_brain",
            {"component": "nota", "measurement": note_m.group(1).strip(), "result": "ok"},
        )
    if re.search(r"\b(refresh|reinicia(r)?\s+(a\s+)?tela|cura\s+ui|removechild)\b", low):
        run("refresh_component", {"component_id": "all"})
    return actions


def mock_response(
    case: dict[str, Any],
    user_text: str,
    has_image: bool = False,
) -> dict[str, Any]:
    actions = _mock_run_tools(case, user_text)
    if actions and not has_image:
        names = [a.get("name") for a in actions]
        if "launch_module" in names:
            kind = next((a.get("type") for a in actions if a.get("name") == "launch_module"), "módulo")
            msg = f"Feito, senhor. {kind} na tela."
            return _finalize_payload(
                {
                    "assistant_message": msg,
                    "spoken_reply": msg,
                    "phase": "chat",
                    "mode": "chat",
                    "next_action": "chat",
                    "confidence": 1.0,
                    "needs_research": False,
                    "probe": None,
                    "verdict": "pending",
                    "solution": None,
                    "case_update": {
                        "status": case.get("status") or "open",
                        "board_model": case.get("board_model") or "",
                        "symptom": case.get("symptom") or "",
                        "suspect_components": case.get("suspect_components") or [],
                        "notes": "",
                    },
                },
                actions,
            )
        if "play_ambient_sound" in names:
            mood = next((a.get("mood") for a in actions if a.get("name") == "play_ambient_sound"), "ambient")
            msg = (
                "Silêncio, senhor."
                if mood == "off"
                else f"Feito, senhor. {mood} no ar — waveform no rodapé."
            )
            return _finalize_payload(
                {
                    "assistant_message": msg,
                    "spoken_reply": msg.split(".")[0] + ".",
                    "phase": "chat",
                    "mode": "chat",
                    "next_action": "chat",
                    "confidence": 1.0,
                    "needs_research": False,
                    "probe": None,
                    "verdict": "pending",
                    "solution": None,
                    "case_update": {
                        "status": "open",
                        "board_model": "",
                        "symptom": "",
                        "suspect_components": [],
                        "notes": "",
                    },
                },
                actions,
            )
        if "close_modules" in names:
            msg = "Módulos recolhidos."
            return _finalize_payload(
                {
                    "assistant_message": msg,
                    "spoken_reply": msg,
                    "phase": "chat",
                    "mode": "chat",
                    "next_action": "chat",
                    "confidence": 1.0,
                    "needs_research": False,
                    "probe": None,
                    "verdict": "pending",
                    "solution": None,
                    "case_update": {
                        "status": "open",
                        "board_model": "",
                        "symptom": "",
                        "suspect_components": [],
                        "notes": "",
                    },
                },
                actions,
            )
        if "save_to_brain" in names:
            msg = "Anotado no cérebro, senhor."
            return _finalize_payload(
                {
                    "assistant_message": msg,
                    "spoken_reply": msg,
                    "phase": "chat",
                    "mode": "chat",
                    "next_action": "chat",
                    "confidence": 1.0,
                    "needs_research": False,
                    "probe": None,
                    "verdict": "pending",
                    "solution": None,
                    "case_update": {
                        "status": case.get("status") or "open",
                        "board_model": case.get("board_model") or "",
                        "symptom": case.get("symptom") or "",
                        "suspect_components": [],
                        "notes": "",
                    },
                },
                actions,
            )
        if "refresh_component" in names:
            msg = "UI remountada. RemoveChild que se cuide."
            return _finalize_payload(
                {
                    "assistant_message": msg,
                    "spoken_reply": msg,
                    "phase": "chat",
                    "mode": "chat",
                    "next_action": "chat",
                    "confidence": 1.0,
                    "needs_research": False,
                    "probe": None,
                    "verdict": "pending",
                    "solution": None,
                    "case_update": {
                        "status": "open",
                        "board_model": "",
                        "symptom": "",
                        "suspect_components": [],
                        "notes": "",
                    },
                },
                actions,
            )

    # Chat aberto / saudações (demo sem API)
    mode = (case.get("chat_mode") or "open").lower()
    low = (user_text or "").lower()
    if mode == "open" and not has_image:
        greetings = ("bom dia", "boa tarde", "boa noite", "oi", "olá", "ola", "e aí", "estou aqui", "to aqui", "jarvis")
        if any(g in low for g in greetings) or (
            len(low.strip()) < 40
            and not any(k in low for k in ("consert", "defeito", "medir", "placa", "celular", "fonte", "tv"))
        ):
            who = case.get("operator_name") or "chefe"
            return _finalize_payload(
                {
                    "assistant_message": (
                        f"{who.split()[-1] if who else 'Chefe'}, por aqui tudo nominal. "
                        "Música, esquema ou conserto — manda quando quiser."
                    ),
                    "spoken_reply": f"Online, {who}.",
                    "phase": "chat",
                    "mode": "chat",
                    "next_action": "chat",
                    "confidence": 1.0,
                    "needs_research": False,
                    "probe": None,
                    "verdict": "pending",
                    "solution": None,
                    "case_update": {
                        "status": "open",
                        "board_model": "",
                        "symptom": "",
                        "suspect_components": [],
                        "notes": "",
                    },
                },
                actions,
            )
        if any(
            k in low
            for k in ("consert", "defeito", "medir", "placa", "celular", "monitor", "fonte", "não liga", "nao liga")
        ):
            return _finalize_payload(
                {
                    "assistant_message": (
                        "Mestre Técnico no ar. Marca/modelo e sintoma — "
                        "foto acelera, mas não é obrigatória agora."
                    ),
                    "spoken_reply": "Mestre técnico. Modelo e sintoma, senhor.",
                    "phase": "intake",
                    "mode": "diagnose",
                    "next_action": "ask_measurement" if case.get("symptom") else "ask_photo",
                    "confidence": 0.7,
                    "needs_research": False,
                    "probe": None,
                    "verdict": "pending",
                    "solution": None,
                    "case_update": {
                        "status": "intake",
                        "board_model": "",
                        "symptom": user_text[:160],
                        "suspect_components": [],
                        "notes": "Entrada em modo eletrônica (demo)",
                    },
                },
                actions,
            )

    return _finalize_payload(_mock_response_raw(case, user_text, has_image=has_image), actions)

