"""Classificação de intenção — social/ambient vs técnico (prioridade do Jarvis)."""

from __future__ import annotations

import re
from typing import Any

SOCIAL_RE = re.compile(
    r"^\s*("
    r"ol[aá]|oi\b|e\s*a[ií]|hey|bom\s*dia|boa\s*tarde|boa\s*noite|"
    r"estou\s*aqui|to\s*aqui|tô\s*aqui|presente|salve|fala\b|jarvis\b|"
    r"obrigad|valeu|brigad|tchau|at[eé]\s*logo|como\s*vai|"
    r"piada|conta\s*uma|me\s*faz\s*rir|blz|beleza|suave"
    r")([\s!,.?]|$)",
    re.I,
)
AMBIENT_ON_RE = re.compile(
    r"\b("
    r"(toca(r)?|liga(r)?|coloca(r)?|bota(r)?|p[oõ]e(r)?)\s+(a\s+)?(m[uú]sica|som|trilha|synthwave|lo[\s\-]?fi|ambiente)|"
    r"\b(m[uú]sica|synthwave|lo[\s\-]?fi)\s+(de\s+)?foco\b|"
    r"\bm[uú]sica\s+de\s+(foco|trabalho|ambiente)\b|"
    r"\bsynthwave\s+no\s+ar\b"
    r")\b",
    re.I,
)
AMBIENT_OFF_RE = re.compile(
    r"\b(para(r)?\s+(a\s+)?m[uú]sica|sil[eê]ncio|mute|sem m[uú]sica|desliga(r)?\s+(a\s+)?m[uú]sica)\b",
    re.I,
)
TECH_RE = re.compile(
    r"\b("
    r"consertar|consert|reparar|defeito|defeituos|medir|medi[cç][aã]o|mult[ií]metro|"
    r"celular|telem[oó]vel|monitor|fonte|tv\b|televis|n[aã]o\s*liga|nao\s*liga|"
    r"queimou|curto|diagn[oó]stico|soldar|capacitor|resistor|volta(gem)?|"
    r"continuidad|ohm|amp[eè]re|fus[ií]vel|ci\b|smd|bancada|"
    r"tens[aã]o|standby|5v|12v|3v3|componente|troca(r)?\s+a?\s*pe[cç]a|"
    r"n[aã]o\s*resolveu|nao\s*resolveu|especialista"
    r")\b",
    re.I,
)
TECH_PLACA_RE = re.compile(
    r"\b("
    r"placa\s+(com|sem|n[aã]o|queim|defeit)|"
    r"foto\s+da\s+placa|an[aá]lise\s+(da\s+)?placa|"
    r"modelo\s+da\s+placa|placa\s+m[aã]e|"
    r"consertar\s+(a\s+)?placa|defeito\s+(na|da)\s+placa"
    r")\b",
    re.I,
)
UI_MODULE_RE = re.compile(
    r"\b("
    r"abre(r)?\s+o\s+(esquema|v[ií]deo|m[oó]dulo)|"
    r"ver\s+a\s+placa|mostra(r)?\s+a\s+placa|foto\s+da\s+placa|"
    r"abre\s+a\s+(foto|imagem)|an[aá]lise\s+visual|"
    r"esquema|schematic|datasheet|manual|diagrama|"
    r"v[ií]deo|tutorial|abre\s+o\s+v[ií]deo|"
    r"fecha(r)?\s+(tudo|os?\s+m[oó]dulos)|limpa(r)?\s+a\s+tela"
    r")\b",
    re.I,
)

KIND_SOCIAL = "social"
KIND_AMBIENT = "ambient"
KIND_UI = "ui"
KIND_TECH = "tech"
KIND_MIXED = "mixed"


def classify_message(text: str) -> dict[str, Any]:
    """Prioridade: social/ambient puro não entra em fluxo de conserto."""
    t = (text or "").strip()
    out: dict[str, Any] = {
        "primary": KIND_SOCIAL,
        "is_social": False,
        "is_ambient": False,
        "is_ui": False,
        "is_technical": False,
        "ambient_on": None,
        "blocks_electronics_activation": False,
        "skip_photo_pressure": False,
    }
    if not t:
        out["primary"] = KIND_SOCIAL
        out["is_social"] = True
        out["blocks_electronics_activation"] = True
        out["skip_photo_pressure"] = True
        return out

    social = bool(SOCIAL_RE.search(t)) or (
        len(t) < 45
        and not TECH_RE.search(t)
        and not TECH_PLACA_RE.search(t)
        and not UI_MODULE_RE.search(t)
        and not AMBIENT_ON_RE.search(t)
    )
    ambient_on = AMBIENT_ON_RE.search(t)
    ambient_off = AMBIENT_OFF_RE.search(t)
    ambient = bool(ambient_on or ambient_off)
    ui = bool(UI_MODULE_RE.search(t))
    technical = bool(TECH_RE.search(t) or TECH_PLACA_RE.search(t))

    out["is_social"] = social
    out["is_ambient"] = ambient
    out["is_ui"] = ui
    out["is_technical"] = technical
    if ambient_off:
        out["ambient_on"] = False
    elif ambient_on:
        out["ambient_on"] = True

    if technical:
        out["primary"] = KIND_MIXED if (social or ambient or ui) else KIND_TECH
    elif ambient:
        out["primary"] = KIND_AMBIENT
    elif ui:
        out["primary"] = KIND_UI
    else:
        out["primary"] = KIND_SOCIAL

    # Social/ambient puro: não ativa Mestre Técnico nem pressiona foto
    if not technical:
        out["blocks_electronics_activation"] = True
        out["skip_photo_pressure"] = True

    return out


def social_reply(text: str, operator: str = "chefe") -> tuple[str, str]:
    """Resposta curta para saudação/social — sem pedir foto."""
    t = (text or "").lower()
    who = (operator or "chefe").split()[-1]
    if "bom dia" in t:
        msg = f"Bom dia, {who}. Centro de comando online — manda quando quiser."
    elif "boa tarde" in t:
        msg = f"Boa tarde, {who}. Tudo pronto por aqui."
    elif "boa noite" in t:
        msg = f"Boa noite, {who}. HUD nominal."
    elif any(x in t for x in ("obrigad", "valeu", "brigad")):
        msg = "Disponha, senhor."
    elif any(x in t for x in ("piada", "rir")):
        msg = "Humor reservado para depois do café — mas estou online, senhor."
    elif any(x in t for x in ("tchau", "até logo", "ate logo")):
        msg = "Até logo. HUD em standby."
    else:
        msg = (
            f"{who}, por aqui tudo nominal. "
            "Fala o que precisar — música, esquema ou conserto quando quiser."
        )
    spoken = msg.split(".")[0] + "."
    return msg, spoken
