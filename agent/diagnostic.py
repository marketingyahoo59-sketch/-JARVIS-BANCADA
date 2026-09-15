"""Orquestração do agente de diagnóstico ativo (JARVIS de bancada)."""

from __future__ import annotations

import re
from typing import Any

from .docs import docs_context_from_case, extract_text_from_bytes, save_case_doc
from .failures import add_resolved_failure, similar_as_context
from .learning_db import (
    build_diagnostic_map,
    learned_as_context,
    map_as_context,
    remember_resolution,
)
from .llm import call_llm, provider_status
from .memory import CaseMemory
from .profile import address_user
from .research import research_for_case
from .safety import safety_brief


def _brain_context(case: dict[str, Any], user_text: str = "", *, force_research: bool = False) -> str:
    """Pesquisa web + memória SQLite + mapa + banco JSON + docs."""
    board = str(case.get("board_model") or "")
    symptom = str(case.get("symptom") or "")
    parts: list[str] = []

    research = ""
    if force_research or board or case.get("chat_mode") == "electronics":
        research = research_for_case(case, user_text)
        if research:
            case["last_research"] = research[:4000]
            parts.append(research)

    learned = learned_as_context(board, symptom)
    if learned:
        case["learned_hint"] = learned
        parts.append(learned)

    bank = similar_as_context(board, symptom)
    if bank:
        parts.append(bank)

    # Mantém / atualiza mapa de diagnóstico
    if case.get("chat_mode") == "electronics" and (board or symptom):
        hint = ""
        if research:
            # primeira linha útil após o header
            for line in research.splitlines():
                if line.startswith("- "):
                    hint = line[2:220]
                    break
        if not case.get("diagnostic_map") or case["diagnostic_map"].get("device") != (board or "aparelho"):
            case["diagnostic_map"] = build_diagnostic_map(board, symptom, hint)
        else:
            case["diagnostic_map"]["research_hint"] = hint or case["diagnostic_map"].get("research_hint", "")
            case["diagnostic_map"]["symptom"] = symptom or case["diagnostic_map"].get("symptom")
        parts.append(map_as_context(case.get("diagnostic_map")))

    docs = docs_context_from_case(case)
    if docs:
        parts.append(docs)
    return "\n\n".join(parts)


def find_learned_brief(case: dict[str, Any]) -> str:
    """Uma frase curta da memória SQLite para o anúncio de liderança."""
    from .learning_db import find_learned

    sims = find_learned(
        str(case.get("board_model") or ""),
        str(case.get("symptom") or ""),
        limit=1,
    )
    if not sims:
        return ""
    it = sims[0]
    part = it.get("replaced_part") or "a peça indicada"
    return f"funcionou trocar **{part}**"


ELECTRONICS_RE = re.compile(
    r"\b("
    r"consertar|consert|reparar|defeito|defeituos|medir|medi[cç][aã]o|mult[ií]metro|"
    r"placa|celular|telem[oó]vel|monitor|fonte|tv\b|televis|n[aã]o\s*liga|nao\s*liga|"
    r"queimou|curto|diagn[oó]stico|soldar|capacitor|resistor|volta(gem)?|"
    r"continuidad|ohm|amp[eè]re|fus[ií]vel|ci\b|smd|bancada"
    r")\b",
    re.I,
)
RESUME_RE = re.compile(
    r"\b("
    r"continu|ontem|anteontem|outro\s+dia|mesmo\s+caso|mesma\s+placa|"
    r"voltar|retomar|retoma|placa\s+de\s+ontem|onde\s+paramos|de\s+onde\s+parei"
    r")\b",
    re.I,
)
GREETING_RE = re.compile(
    r"^\s*("
    r"ol[aá]|oi\b|e\s*a[ií]|hey|bom\s*dia|boa\s*tarde|boa\s*noite|"
    r"estou\s*aqui|to\s*aqui|tô\s*aqui|presente|salve|fala\b|jarvis\b"
    r")([\s!,.?]|$)",
    re.I,
)


def is_electronics_intent(text: str) -> bool:
    return bool(ELECTRONICS_RE.search(text or ""))


def is_resume_intent(text: str) -> bool:
    return bool(RESUME_RE.search(text or ""))


def is_greeting(text: str) -> bool:
    t = (text or "").strip()
    if len(t) > 80:
        return False
    return bool(GREETING_RE.search(t))



CONFIRM_WORDS = (
    "confirmo",
    "confirmado",
    "confirma",
    "isso mesmo",
    "está certo",
    "esta certo",
    "pode seguir",
    "sim, confirma",
    "sim confirma",
    "ok confirma",
)


class DiagnosticAgent:
    def __init__(self, memory: CaseMemory | None = None) -> None:
        self.memory = memory or CaseMemory()

    def provider_info(self) -> dict[str, Any]:
        return provider_status()

    def start_case(self, board_model: str, symptom: str) -> dict[str, Any]:
        case = self.memory.create(board_model=board_model.strip(), symptom=symptom.strip())
        case["status"] = "diagnosing"
        case["phase"] = "intake"
        case["chat_mode"] = "electronics"
        extra = _brain_context(case, force_research=True)
        self.memory.save(case)
        safety = safety_brief("intake")

        result = call_llm(
            case,
            user_text=(
                f"Início do caso no Modo Mestre Técnico. Modelo: {board_model}. "
                f"Sintoma: {symptom}. Você já tem pesquisa/memória no contexto. "
                "Liderança: diga o que pesquisou, o defeito mais comum e proponha o Passo 1 "
                "(foto da placa) + a 1ª medição se já souber o ponto. "
                f"Aviso breve de segurança: {safety}"
            ),
            research_notes=extra or None,
        )
        out = self._apply_result(case, result, user_visible=True)
        out["safety_brief"] = safety
        out["diagnostic_map"] = case.get("diagnostic_map")
        return out

    def load_case(self, case_id: str) -> dict[str, Any] | None:
        return self.memory.load(case_id)

    def list_cases(self) -> list[dict[str, Any]]:
        return self.memory.list_cases()

    def attach_document(
        self,
        case: dict[str, Any],
        filename: str,
        data: bytes,
    ) -> dict[str, Any]:
        path = save_case_doc(case["case_id"], filename, data)
        excerpt = extract_text_from_bytes(filename, data)
        case.setdefault("documents", []).append(
            {
                "filename": filename,
                "path": str(path),
                "excerpt": excerpt[:8000],
            }
        )
        self.memory.save(case)
        self.memory.add_message(
            case,
            "user",
            f"[Documento anexado: {filename}]",
            meta={"document": filename},
        )
        result = call_llm(
            case,
            user_text=(
                f"O usuário anexou o documento/esquema “{filename}”. "
                "Use o conteúdo (se houver texto) para orientar o próximo passo de medição. "
                "Peça UMA medição objetiva."
            ),
            research_notes=docs_context_from_case(case),
        )
        return self._apply_result(case, result, user_visible=True)

    def resolve_case(
        self,
        case: dict[str, Any],
        replaced_part: str,
        notes: str = "",
    ) -> dict[str, Any]:
        case["status"] = "resolved"
        case["phase"] = "done"
        failed_node = ""
        for n in reversed(case.get("solution_notes") or []):
            if isinstance(n, dict) and n.get("failed_node"):
                failed_node = str(n["failed_node"])
                break
        board = str(case.get("board_model") or "")
        symptom = str(case.get("symptom") or "")
        measurements = list(case.get("measurements") or [])
        entry = add_resolved_failure(
            board_model=board,
            symptom=symptom,
            failed_node=failed_node or "nó não informado",
            replaced_part=replaced_part,
            notes=notes,
            measurements=measurements,
        )
        learned = remember_resolution(
            board_model=board,
            symptom=symptom,
            failed_node=failed_node or "",
            replaced_part=replaced_part,
            notes=notes,
            measurements=measurements,
        )
        self.memory.add_message(
            case,
            "assistant",
            (
                f"Caso marcado como resolvido. Peça trocada: **{replaced_part}**. "
                "Salvei no banco de falhas e na memória de aprendizado (SQLite) — "
                "na próxima vez que aparecer um aparelho parecido, eu já sugiro o que funcionou."
            ),
            meta={
                "phase": "done",
                "mode": "diagnose",
                "verdict": "ok",
                "bank_id": entry["id"],
                "learned_id": learned["id"],
            },
        )
        self.memory.save(case)
        return {"case": case, "bank_entry": entry, "learned_entry": learned}


    def open_session(self, operator_name: str | None = None) -> dict[str, Any]:
        """Sessão de chat aberto (sem formulário de placa/sintoma)."""
        who = operator_name or address_user()
        case = self.memory.create(
            board_model="",
            symptom="",
            chat_mode="open",
            operator_name=who,
        )
        hour = __import__("datetime").datetime.now().hour
        greet = "Bom dia" if hour < 12 else ("Boa tarde" if hour < 18 else "Boa noite")
        msg = (
            f"{greet}, {who}. Sistemas online — sou o seu Cérebro de Engenharia Eletrônica. "
            "Pode papear à vontade (piada inclusa). "
            "Quando for consertar algo, eu entro no **Modo Mestre Técnico**: pesquiso manuais, "
            "monto o mapa de diagnóstico e lidero ponto a ponto."
        )
        spoken = (
            f"{greet}, {who}. Estou online. Pode falar comigo. "
            "Para conserto, diga o aparelho e o defeito — eu pesquiso e assumo o diagnóstico."
        )
        self.memory.add_message(
            case,
            "assistant",
            msg,
            meta={
                "phase": "chat",
                "mode": "chat",
                "spoken_reply": spoken,
                "next_action": "chat",
                "verdict": "pending",
            },
        )
        self.memory.save(case)
        return {
            "case": case,
            "message": msg,
            "spoken_reply": spoken,
            "phase": "chat",
            "mode": "chat",
            "probe": None,
            "verdict": "pending",
            "solution": None,
            "next_action": "chat",
        }

    def activate_electronics(
        self,
        case: dict[str, Any],
        user_text: str,
        *,
        announce: bool = True,
    ) -> dict[str, Any]:
        """Liga Modo Mestre Técnico a partir de um chat aberto."""
        case["chat_mode"] = "electronics"
        case["status"] = "diagnosing"
        case["phase"] = "intake"
        try:
            from .voice import extract_intake_from_speech

            intake = extract_intake_from_speech(user_text)
            if intake.get("board_model") and not case.get("board_model"):
                case["board_model"] = intake["board_model"]
            if intake.get("symptom") and not case.get("symptom"):
                case["symptom"] = intake["symptom"]
        except Exception:
            pass
        if not case.get("symptom") and len(user_text.strip()) > 8:
            case["symptom"] = user_text.strip()[:200]

        # Pesquisa ativa + mapa + memória assim que entra no modo
        _brain_context(case, user_text, force_research=bool(case.get("board_model")))
        self.memory.save(case)

        if announce:
            board = case.get("board_model") or "o equipamento"
            learned = find_learned_brief(case)
            research_hint = ""
            dm = case.get("diagnostic_map") or {}
            if dm.get("research_hint"):
                research_hint = str(dm["research_hint"])[:160]
            if learned:
                note = (
                    f"**Modo Mestre Técnico** ligado. Em aparelhos como {board}, "
                    f"já aprendemos que a solução {learned}. "
                    "Vamos confirmar no mapa: foto da placa e a 1ª medição. "
                )
            elif research_hint:
                note = (
                    f"**Modo Mestre Técnico**. Pesquisei sobre {board}. "
                    f"Pista forte: {research_hint}. Vamos testar? "
                    "Me mande a foto da placa e seguimos o Passo 1 do mapa. "
                )
            else:
                note = (
                    f"**Modo Mestre Técnico** ativado para {board}. "
                    "Vou liderar: Passo 1 análise visual (foto da placa), "
                    "depois medições básicas, depois componentes. "
                )
            case.setdefault("_electronics_announce", note)
        return case

    def try_resume_case(self, user_text: str) -> dict[str, Any] | None:
        """Recupera caso recente quando o usuário pede para continuar."""
        if not is_resume_intent(user_text):
            return None
        candidates = self.memory.find_resumable(user_text)
        # prefer electronics with board/measurements
        for item in candidates:
            cid = item.get("case_id")
            if not cid:
                continue
            loaded = self.memory.load(cid)
            if not loaded:
                continue
            if loaded.get("messages"):
                return loaded
        # fallback: most recent non-empty
        for item in self.memory.list_cases():
            if item.get("status") in {"resolved", "abandoned"}:
                continue
            loaded = self.memory.load(item["case_id"])
            if loaded and loaded.get("messages"):
                return loaded
        return None

    def handle_user(
        self,
        case: dict[str, Any],
        user_text: str,
        image_bytes: bytes | None = None,
        image_name: str | None = None,
        image_mime: str = "image/jpeg",
    ) -> dict[str, Any]:
        meta: dict[str, Any] = {}
        if image_name:
            meta["image"] = image_name
        self.memory.add_message(case, "user", user_text, meta=meta or None)

        # Retomar caso anterior ("placa de ontem", "continuando"…)
        if is_resume_intent(user_text) and case.get("chat_mode") == "open" and not case.get("board_model"):
            resumed = self.try_resume_case(user_text)
            if resumed and resumed.get("case_id") != case.get("case_id"):
                board = resumed.get("board_model") or "placa"
                symptom = resumed.get("symptom") or "—"
                msg = (
                    f"Recuperei o caso **{board}** ({symptom}). "
                    f"Última atualização: {str(resumed.get('updated_at') or '')[:19]}. "
                    "Seguimos de onde paramos — me diga a última medição ou mande uma foto nova."
                )
                spoken = f"Recuperei o caso {board}. Continuamos de onde paramos."
                resumed["chat_mode"] = "electronics"
                self.memory.add_message(
                    resumed,
                    "assistant",
                    msg,
                    meta={"phase": resumed.get("phase"), "mode": "diagnose", "spoken_reply": spoken},
                )
                self.memory.save(resumed)
                return {
                    "case": resumed,
                    "message": msg,
                    "spoken_reply": spoken,
                    "phase": resumed.get("phase"),
                    "mode": "diagnose",
                    "probe": None,
                    "verdict": "pending",
                    "solution": None,
                    "next_action": "ask_measurement",
                    "switched_case_id": resumed["case_id"],
                }

        # Gatilho: consertar / defeito / medir / placa / celular…
        if case.get("chat_mode") != "electronics" and (
            is_electronics_intent(user_text) or image_bytes is not None
        ):
            self.activate_electronics(case, user_text, announce=True)

        # Confirmação pendente de medição antes do modo solução
        pending = case.get("pending_confirm")
        if pending and self._is_confirm(user_text):
            return self._finalize_confirmed_fail(case, pending)
        if pending and self._is_deny(user_text):
            case["pending_confirm"] = None
            self.memory.save(case)
            msg = (
                "Ok, cancelei a confirmação. Me diga de novo o valor medido com cuidado "
                "(ponto + número + unidade)."
            )
            self.memory.add_message(
                case,
                "assistant",
                msg,
                meta={"phase": "measure", "mode": "diagnose", "verdict": "pending", "spoken_reply": msg},
            )
            return {
                "case": case,
                "message": msg,
                "spoken_reply": msg,
                "phase": "measure",
                "mode": "diagnose",
                "probe": pending.get("probe"),
                "verdict": "pending",
                "solution": None,
                "next_action": "ask_measurement",
            }

        prompt = user_text
        if image_bytes:
            prompt = (
                f"{user_text}\n\n"
                "[O usuário anexou uma foto da placa. Analise a imagem, "
                "indique onde colocar as pontas (descrição + coordenadas 0–100) "
                "e peça UMA medição específica. Inclua aviso curto de segurança.]"
            )

        lowered = user_text.lower()
        needs_from_llm = bool(case.get("_needs_research"))
        case["_needs_research"] = False
        should_research = (
            case.get("chat_mode") == "electronics"
            or needs_from_llm
            or bool(case.get("board_model"))
            or any(
                k in lowered
                for k in (
                    "?",
                    "o que é",
                    "por que",
                    "porque",
                    "esquema",
                    "datasheet",
                    "pesquisa",
                    "manual",
                    "não sei",
                    "nao sei",
                    "procura",
                    "busca",
                    "defeito comum",
                )
            )
        )
        extra = _brain_context(case, user_text, force_research=should_research)

        result = call_llm(
            case,
            prompt,
            image_bytes=image_bytes,
            image_mime=image_mime,
            research_notes=extra or None,
        )
        if result.get("needs_research"):
            case["_needs_research"] = True
            # reforço imediato se o modelo pediu e ainda não pesquisamos de verdade
            if not extra or "(pesquisa indisponível" in extra:
                extra2 = _brain_context(case, user_text, force_research=True)
                if extra2 and extra2 != extra:
                    result = call_llm(
                        case,
                        prompt
                        + "\n\n[Pesquisa reforçada acabou de chegar — use-a para liderar o próximo teste.]",
                        image_bytes=image_bytes,
                        image_mime=image_mime,
                        research_notes=extra2,
                    )

        if image_bytes and image_name:
            probe = result.get("probe") or {}
            coords = probe.get("coordinates") or []
            self.memory.add_image_note(
                case,
                filename=image_name,
                analysis=result.get("assistant_message", ""),
                probe_targets=[
                    {
                        "point_name": probe.get("point_name"),
                        "visual_hint": probe.get("visual_hint"),
                        "coordinates": coords,
                        "black_probe": probe.get("black_probe"),
                        "red_probe": probe.get("red_probe"),
                    }
                ]
                if probe
                else None,
            )

        # Intercepta FAIL: pede confirmação antes de entrar em solução
        if (result.get("verdict") == "fail") and result.get("solution"):
            return self._request_measurement_confirm(case, result, user_text)

        out = self._apply_result(case, result, user_visible=True)
        out["safety_brief"] = safety_brief(out.get("phase"))
        return out

    def _is_confirm(self, text: str) -> bool:
        t = (text or "").strip().lower()
        return any(w in t for w in CONFIRM_WORDS) or t in {"sim", "s", "ok", "certo", "isso"}

    def _is_deny(self, text: str) -> bool:
        t = (text or "").strip().lower()
        return any(w in t for w in ("não", "nao", "errado", "errei", "repete", "de novo", "denovo"))

    def _request_measurement_confirm(
        self,
        case: dict[str, Any],
        result: dict[str, Any],
        measured: str,
    ) -> dict[str, Any]:
        probe = result.get("probe") or {}
        point = probe.get("point_name") or "ponto"
        expected = probe.get("expected_value") or "?"
        msg = (
            f"Antes de ir para o modo solução, confirma: no **{point}** você mediu "
            f"**{measured.strip()}** (esperado {expected})? "
            "Responda **confirmo** para eu indicar a peça, ou **não** se errou a medição."
        )
        spoken = (
            f"Confirma: no {point} você mediu {measured.strip()}? "
            "Diga confirmo para eu indicar a peça, ou não se a medição estiver errada."
        )
        case["pending_confirm"] = {
            "measured": measured,
            "probe": probe,
            "solution": result.get("solution"),
            "result": result,
        }
        case["phase"] = "measure"
        self.memory.add_message(
            case,
            "assistant",
            msg,
            meta={
                "phase": "measure",
                "mode": "diagnose",
                "probe": probe,
                "verdict": "pending",
                "solution": None,
                "next_action": "ask_confirm",
                "spoken_reply": spoken,
                "awaiting_confirm": True,
            },
        )
        self.memory.save(case)
        return {
            "case": case,
            "message": msg,
            "spoken_reply": spoken,
            "phase": "measure",
            "mode": "diagnose",
            "probe": probe,
            "verdict": "pending",
            "solution": None,
            "next_action": "ask_confirm",
            "awaiting_confirm": True,
            "safety_brief": safety_brief("measure"),
        }

    def _finalize_confirmed_fail(self, case: dict[str, Any], pending: dict[str, Any]) -> dict[str, Any]:
        result = dict(pending.get("result") or {})
        result["verdict"] = "fail"
        result["mode"] = "solution"
        result["phase"] = "solution"
        result["next_action"] = "ask_replace"
        result["probe"] = pending.get("probe")
        result["solution"] = pending.get("solution")
        # reforça mensagem
        sol = pending.get("solution") or {}
        replace = sol.get("replace_first") or "a peça indicada"
        result["assistant_message"] = (
            f"Confirmado. Valor fora do esperado. Modo solução: troque primeiro **{replace}**. "
            f"{sol.get('how_to_confirm') or ''} "
            f"{safety_brief('solution')}"
        ).strip()
        result["spoken_reply"] = (
            f"Confirmado. Entre em modo solução e troque primeiro {replace}."
        )
        case["pending_confirm"] = None
        out = self._apply_result(case, result, user_visible=True)
        out["safety_brief"] = safety_brief("solution")
        return out

    def _apply_result(
        self,
        case: dict[str, Any],
        result: dict[str, Any],
        user_visible: bool = True,
    ) -> dict[str, Any]:
        message = result.get("assistant_message") or "Sem resposta do agente."
        spoken = (result.get("spoken_reply") or message or "").strip()
        phase = result.get("phase") or case.get("phase") or "measure"
        mode = result.get("mode") or "diagnose"
        probe = result.get("probe")
        verdict = result.get("verdict") or "pending"
        solution = result.get("solution")
        update = result.get("case_update") or {}

        case["phase"] = phase
        if update.get("status"):
            case["status"] = update["status"]
        if update.get("board_model"):
            case["board_model"] = update["board_model"]
        if update.get("symptom"):
            case["symptom"] = update["symptom"]
        if update.get("suspect_components") is not None:
            case["suspect_components"] = update["suspect_components"]
        if update.get("notes"):
            case.setdefault("solution_notes", []).append(update["notes"])
        # LLM pode pedir troca para electronics via next_action
        if result.get("next_action") in {"ask_photo", "ask_measurement", "ask_replace"}:
            case["chat_mode"] = "electronics"
        # Prefixo de anúncio do modo Mestre Técnico (uma vez)
        announce = case.pop("_electronics_announce", None)
        if announce and not (
            message.startswith("Modo Especialista")
            or message.startswith("**Modo Mestre")
            or "Modo Mestre Técnico" in message[:80]
        ):
            message = announce + message
            spoken = (announce.replace("**", "").split(".")[0] + ". " + spoken).strip()

        # Atualiza passo do mapa de diagnóstico
        step = result.get("diagnostic_step")
        if step and case.get("diagnostic_map"):
            try:
                case["diagnostic_map"]["current_step"] = max(1, min(3, int(step)))
            except (TypeError, ValueError):
                pass
        if image_bytes and case.get("diagnostic_map"):
            # foto recebida → pode avançar para medições se ainda no passo 1
            if int(case["diagnostic_map"].get("current_step") or 1) == 1:
                case["diagnostic_map"]["current_step"] = 2
        if verdict in ("ok", "fail") and case.get("diagnostic_map"):
            cur = int(case["diagnostic_map"].get("current_step") or 1)
            if cur == 2 and verdict == "ok":
                case["diagnostic_map"]["current_step"] = 3
            elif cur == 2 and verdict == "fail":
                case["diagnostic_map"]["current_step"] = 3

        if verdict in ("ok", "fail") and probe:
            last_user = None
            for msg in reversed(case.get("messages", [])):
                if msg.get("role") == "user":
                    last_user = msg.get("content", "")
                    break
            if last_user and not re.search(r"confirm", last_user, re.I):
                self.memory.add_measurement(
                    case,
                    point=probe.get("point_name") or "ponto",
                    expected=str(probe.get("expected_value") or ""),
                    measured=last_user,
                    verdict=verdict,
                    notes=(solution or {}).get("replace_first", "") if verdict == "fail" else "",
                )

        if mode == "reassess" or phase == "reassess":
            case["strategy_revisions"] = int(case.get("strategy_revisions") or 0) + 1

        if solution and verdict == "fail":
            case.setdefault("solution_notes", []).append(
                {
                    "failed_node": solution.get("failed_node"),
                    "replace_first": solution.get("replace_first"),
                    "likely_parts": solution.get("likely_parts", []),
                }
            )

        if user_visible or not case.get("messages"):
            self.memory.add_message(
                case,
                "assistant",
                message,
                meta={
                    "phase": phase,
                    "mode": mode,
                    "probe": probe,
                    "verdict": verdict,
                    "solution": solution,
                    "next_action": result.get("next_action"),
                    "spoken_reply": spoken,
                },
            )
        else:
            if case.get("messages") and case["messages"][-1]["role"] == "assistant":
                case["messages"][-1]["content"] = message
                case["messages"][-1]["meta"] = {
                    "phase": phase,
                    "mode": mode,
                    "probe": probe,
                    "verdict": verdict,
                    "solution": solution,
                    "next_action": result.get("next_action"),
                    "spoken_reply": spoken,
                }
            self.memory.save(case)

        self.memory.save(case)
        return {
            "case": case,
            "message": message,
            "spoken_reply": spoken,
            "phase": phase,
            "mode": mode,
            "probe": probe,
            "verdict": verdict,
            "solution": solution,
            "next_action": result.get("next_action"),
            "diagnostic_map": case.get("diagnostic_map"),
        }
