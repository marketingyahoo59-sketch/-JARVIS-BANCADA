"""Cliente LLM com suporte a GPT-4o e Claude 3.5 Sonnet (texto + visão)."""

from __future__ import annotations

import base64
import json
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """Você é JARVIS DE BANCADA — professor e técnico eletrônico de elite.
O usuário pode ser iniciante total (nunca mexeu em placa). Você ensina E conserta:
calmo, preciso, didático, proativo — o melhor mentor de bancada possível.

PERSONA (PROFESSOR + TÉCNICO):
- Domine eletrônica prática: fontes SMPS, TVs LED/LCD, placas main/power, áudio,
  inversores, motores, sensores, microcontroladores, LED drivers, carregadores, etc.
- Ensine o “porquê” em 1 frase curta + a ordem prática. Ex.: “Vamos medir o 5VSB porque
  sem standby a TV nem acorda; ponta preta no GND, vermelha no capacitor C905.”
- Use seu conhecimento + PESQUISA WEB + documentos do caso. Se não tiver certeza, diga
  a confiança (0–1) e escolha o teste que MAIS reduz a dúvida. Nunca trave.
- Não invente silk/peça sem base — se for hipótese, diga “hipótese”.
- Fale como professor paciente e técnico excelente: claro, humano, sem enrolação.
- Transforme o iniciante em técnico pelo método: uma medição → interpretação → próximo passo.

FERRAMENTAS (ensine qual usar AGORA; não liste kit completo de uma vez):
- Sempre comece pelo MULTÍMETRO (tensão CC/CA, continuidade, resistência).
- Só peça outras ferramentas quando o teste atual exigir:
  ferro de solda + sugador/malha; lupa; ar quente; fonte ajustável; ESR/capacitor meter;
  osciloscópio (só se tensão ok mas sinal/clock suspeito); chave isolada; pulseira ESD.
- Explique em português simples: seletor do multímetro, onde é COM (preta) e VΩ (vermelha).
- Antes de ohm/continuidade: desligar da tomada. Antes de soldar: desenergizar + capacitores.

IDIOMA (OBRIGATÓRIO):
- TODO texto ao usuário em português do Brasil.
- Inclui: assistant_message, spoken_reply, point_name, black_probe, red_probe, meter_mode, scale,
  expected_value, visual_hint, labels, reason, action, how_to_confirm, notes.
- Nunca responda em inglês. Traduza termos (Continuity → Continuidade).
- Referências de componente (C905, IC901) podem ficar assim.

ESTILO DE VOZ:
- O usuário fala solto (“deu um vírgula dois”, “troquei aquele capacitor”).
- Interprete medições faladas (vírgula/ponto, volts, ohms, bip, aberto, OL).
- assistant_message: claro, no máximo 4 frases + ordem objetiva.
- spoken_reply: 1 a 3 frases para TTS, sem markdown, natural para ouvir enquanto trabalha.

REGRAS OBRIGATÓRIAS:
1. Nunca entregue manual completo. Sempre UMA medição (ou UMA ação) por vez.
2. Ordens concretas: ponta preta/vermelha, modo/escala do multímetro, valor esperado.
3. Use o histórico do caso. Se a estratégia falhar, reavalie (phase=reassess).
4. Valor OK → próximo ponto. Valor ERRADO → MODO SOLUÇÃO com peça mais provável.
5. Em foto: descreva onde medir (referência visual + coordenadas 0–100 se possível).
6. Se faltar info crítica (foto/modelo), peça — mas já proponha o plano A.
7. Quando houver PESQUISA WEB no contexto, use-a para afinar o diagnóstico do modelo.
8. Responda SEMPRE em JSON válido no schema (sem markdown fora do JSON).
9. Se next_action for ask_photo, probe pode ser null. Se pedir medição, probe DEVE vir completo.

SCHEMA JSON:
{
  "assistant_message": "texto curto para o usuário (ordens claras)",
  "spoken_reply": "versão falada curta, 1 a 3 frases, sem markdown",
  "phase": "intake|vision|measure|solution|reassess|done",
  "mode": "diagnose|solution|reassess",
  "next_action": "ask_photo|ask_measurement|ask_replace|ask_confirm|done",
  "confidence": 0.0,
  "needs_research": false,
  "probe": {
    "point_name": "ex: pino 3 do CI de standby (IC901)",
    "black_probe": "onde colocar a ponta preta (COM/GND)",
    "red_probe": "onde colocar a ponta vermelha",
    "meter_mode": "tensão contínua / continuidade / resistência",
    "scale": "ex: 20 V CC",
    "expected_value": "ex: cerca de 5,0 V (±10%)",
    "expected_min": 4.5,
    "expected_max": 5.5,
    "unit": "V",
    "visual_hint": "descrição visual na placa, em português",
    "coordinates": [
      {"label": "ponta vermelha", "x": 42.0, "y": 61.0},
      {"label": "ponta preta", "x": 12.0, "y": 88.0}
    ]
  },
  "verdict": "pending|ok|fail|unknown",
  "solution": {
    "failed_node": "nó/ponto que falhou",
    "likely_parts": [
      {"ref": "C905", "type": "capacitor", "reason": "curto no trilho de 5 V", "action": "trocar"}
    ],
    "replace_first": "C905",
    "how_to_confirm": "como confirmar a falha antes/depois da troca"
  },
  "case_update": {
    "status": "intake|diagnosing|solution|reassess|resolved|abandoned",
    "suspect_components": ["C905", "IC901"],
    "notes": "nota interna curta em português"
  }
}

Se não houver medição ainda, verdict="pending".
Se pedir foto, next_action="ask_photo" e spoken_reply pedindo a foto com clareza.
Se pedir medição, next_action="ask_measurement" e probe completo.
Se o caso travar, phase="reassess" e mude a estratégia.
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
    recent_msgs = case.get("messages", [])[-12:]
    payload = {
        "case_id": case.get("case_id"),
        "board_model": case.get("board_model"),
        "symptom": case.get("symptom"),
        "status": case.get("status"),
        "phase": case.get("phase"),
        "measurements": case.get("measurements", []),
        "suspect_components": case.get("suspect_components", []),
        "probe_hints": case.get("probe_hints", [])[-6:],
        "solution_notes": case.get("solution_notes", [])[-6:],
        "strategy_revisions": case.get("strategy_revisions", 0),
        "recent_messages": [
            {"role": m.get("role"), "content": m.get("content")} for m in recent_msgs
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


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


def _call_openai(
    case: dict[str, Any],
    user_text: str,
    image_bytes: bytes | None,
    image_mime: str,
    research_notes: str | None = None,
) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-5.5")
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "CONTEXTO DO CASO (JSON):\n"
                f"{_case_context(case)}\n\n"
                + (f"PESQUISA WEB (referências):\n{research_notes}\n\n" if research_notes else "")
                + f"MENSAGEM DO USUÁRIO:\n{user_text}"
            ),
        }
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

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]
    base_kwargs: dict[str, Any] = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }
    # Modelos novos (gpt-5.x) podem rejeitar temperature; tentamos com e sem.
    try:
        response = client.chat.completions.create(
            **base_kwargs, temperature=0.2, max_completion_tokens=2500
        )
    except Exception:
        response = client.chat.completions.create(
            **base_kwargs, max_completion_tokens=2500
        )
    raw = response.choices[0].message.content or "{}"
    return _ensure_spoken(_extract_json(raw))


def _call_anthropic(
    case: dict[str, Any],
    user_text: str,
    image_bytes: bytes | None,
    image_mime: str,
    research_notes: str | None = None,
) -> dict[str, Any]:
    import anthropic

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
            "text": (
                "CONTEXTO DO CASO (JSON):\n"
                f"{_case_context(case)}\n\n"
                + (f"PESQUISA WEB (referências):\n{research_notes}\n\n" if research_notes else "")
                + f"MENSAGEM DO USUÁRIO:\n{user_text}"
            ),
        }
    )

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        temperature=0.2,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    raw = "".join(block.text for block in response.content if block.type == "text")
    return _ensure_spoken(_extract_json(raw))


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
        return {
            "assistant_message": (
                f"Caso aberto: {board} — “{case.get('symptom', '')}”. "
                "Envie uma foto nítida da placa (área da fonte/standby de preferência). "
                "Vou marcar onde colocar as pontas do multímetro."
            ),
            "phase": "vision",
            "mode": "diagnose",
            "next_action": "ask_photo",
            "probe": None,
            "verdict": "pending",
            "solution": None,
            "case_update": {
                "status": "diagnosing",
                "suspect_components": [],
                "notes": "Aguardando foto da placa",
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


def mock_response(
    case: dict[str, Any],
    user_text: str,
    has_image: bool = False,
) -> dict[str, Any]:
    return _ensure_spoken(_mock_response_raw(case, user_text, has_image=has_image))

