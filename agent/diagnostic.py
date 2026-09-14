"""Orquestração do agente de diagnóstico ativo."""

from __future__ import annotations

from typing import Any

from .llm import call_llm, provider_status
from .memory import CaseMemory


class DiagnosticAgent:
    def __init__(self, memory: CaseMemory | None = None) -> None:
        self.memory = memory or CaseMemory()

    def provider_info(self) -> dict[str, Any]:
        return provider_status()

    def start_case(self, board_model: str, symptom: str) -> dict[str, Any]:
        case = self.memory.create(board_model=board_model.strip(), symptom=symptom.strip())
        opening = (
            f"Placa: **{case['board_model']}**. Sintoma: **{case['symptom']}**.\n\n"
            "Vou guiar o diagnóstico um passo por vez. "
            "Envie uma foto nítida da placa para eu indicar onde colocar as pontas do multímetro."
        )
        self.memory.add_message(case, "assistant", opening, meta={"phase": "vision"})
        case["phase"] = "vision"
        case["status"] = "diagnosing"
        self.memory.save(case)

        # Primeira ordem estruturada via LLM/mock
        result = call_llm(
            case,
            user_text=(
                f"Início do caso. Modelo da placa: {board_model}. "
                f"Sintoma: {symptom}. Peça a foto e prepare o primeiro passo."
            ),
        )
        return self._apply_result(case, result, user_visible=False)

    def load_case(self, case_id: str) -> dict[str, Any] | None:
        return self.memory.load(case_id)

    def list_cases(self) -> list[dict[str, Any]]:
        return self.memory.list_cases()

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

        prompt = user_text
        if image_bytes:
            prompt = (
                f"{user_text}\n\n"
                "[O usuário anexou uma foto da placa. Analise a imagem, "
                "indique onde colocar as pontas (descrição + coordenadas 0–100) "
                "e peça UMA medição específica.]"
            )

        result = call_llm(case, prompt, image_bytes=image_bytes, image_mime=image_mime)

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

        return self._apply_result(case, result, user_visible=True)

    def _apply_result(
        self,
        case: dict[str, Any],
        result: dict[str, Any],
        user_visible: bool = True,
    ) -> dict[str, Any]:
        message = result.get("assistant_message") or "Sem resposta do agente."
        phase = result.get("phase") or case.get("phase") or "measure"
        mode = result.get("mode") or "diagnose"
        probe = result.get("probe")
        verdict = result.get("verdict") or "pending"
        solution = result.get("solution")
        update = result.get("case_update") or {}

        case["phase"] = phase
        if update.get("status"):
            case["status"] = update["status"]
        if update.get("suspect_components") is not None:
            case["suspect_components"] = update["suspect_components"]
        if update.get("notes"):
            case.setdefault("solution_notes", []).append(update["notes"])

        # Registra medição se o último user message parece ter valor e há verdict ok/fail
        if verdict in ("ok", "fail") and probe:
            last_user = None
            for msg in reversed(case.get("messages", [])):
                if msg.get("role") == "user":
                    last_user = msg.get("content", "")
                    break
            if last_user:
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
                },
            )
        else:
            # Atualiza última mensagem do assistente se já criamos opening
            if case.get("messages") and case["messages"][-1]["role"] == "assistant":
                case["messages"][-1]["content"] = message
                case["messages"][-1]["meta"] = {
                    "phase": phase,
                    "mode": mode,
                    "probe": probe,
                    "verdict": verdict,
                    "solution": solution,
                    "next_action": result.get("next_action"),
                }
            self.memory.save(case)

        self.memory.save(case)
        return {
            "case": case,
            "message": message,
            "phase": phase,
            "mode": mode,
            "probe": probe,
            "verdict": verdict,
            "solution": solution,
            "next_action": result.get("next_action"),
        }
