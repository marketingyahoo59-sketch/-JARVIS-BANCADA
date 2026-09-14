"""Checklist de segurança para bancada eletrônica."""

from __future__ import annotations

SAFETY_ITEMS = [
    {
        "id": "unplug",
        "title": "Desconecte da tomada",
        "detail": "Antes de continuidade/resistência ou solda, tire da rede elétrica.",
    },
    {
        "id": "caps",
        "title": "Capacitores da fonte",
        "detail": "Em SMPS, capacitores do primário podem ficar carregados. Descarregue com resistor adequado.",
    },
    {
        "id": "isolation",
        "title": "Isolamento / terra",
        "detail": "Em medições com aparelho ligado, use cuidado com terra/chassis. Prefira pontas isoladas.",
    },
    {
        "id": "esd",
        "title": "Estática (ESD)",
        "detail": "Toque massa da bancada antes de mexer em CIs sensíveis; evite carpete seco.",
    },
    {
        "id": "one_hand",
        "title": "Regra de uma mão",
        "detail": "Com circuito energizado, evite caminho braço–braço pelo peito.",
    },
    {
        "id": "meter_mode",
        "title": "Escala do multímetro",
        "detail": "Confirme DCV/ACV/ohm antes de medir. Escala errada queima fusível do instrumento.",
    },
]


def safety_brief(phase: str | None = None) -> str:
    """Texto curto de segurança conforme a etapa."""
    if phase in {"measure", "vision"}:
        return (
            "Segurança: confirme a escala do multímetro. "
            "Se for continuidade/ohm, desligue da tomada. "
            "Capacitores de fonte podem estar carregados."
        )
    if phase == "solution":
        return (
            "Segurança: desligue da tomada antes de soldar/trocar peça. "
            "Descarregue capacitores do primário se for fonte SMPS."
        )
    return (
        "Segurança básica: tomada desligada para testes de ohm/continuidade; "
        "cuidado com capacitores carregados e isolamento."
    )


def safety_checklist() -> list[dict[str, str]]:
    return list(SAFETY_ITEMS)
