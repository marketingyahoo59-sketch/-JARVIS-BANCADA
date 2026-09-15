"""Pesquisa web técnica — manuais, esquemas e defeitos (com filtro anti-lixo)."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any
from urllib.parse import urlparse

# Cache simples em memória do processo (evita buscas a cada frase).
_RESEARCH_CACHE: dict[str, str] = {}

# Modelos genéricos demais → NÃO pesquisar (gera lixo tipo Teams/Windows).
_GENERIC_DEVICE = re.compile(
    r"^(?:"
    r"o\s+equipamento|equipamento|aparelho|dispositivo|placa|a\s+placa|"
    r"tv|monitor|fonte|celular|board|device|unknown|n/?a|—"
    r")$",
    re.I,
)

_JUNK_HOST = re.compile(
    r"(microsoft\.com|office\.com|teams\.microsoft|learn\.microsoft|"
    r"answers\.microsoft|community\.hub|windowscentral|xbox\.com|"
    r"facebook\.com|instagram\.com|tiktok\.com|pinterest\.|"
    r"twitter\.com|x\.com|reddit\.com/r/(?!electronics|AskElectronics|repair)|"
    r"linkedin\.com|booking\.com|amazon\.(com|com\.br)/dp)",
    re.I,
)

_JUNK_TEXT = re.compile(
    r"(0xcaa|teams|outlook|onedrive|windows\s*hello|conta\s+microsoft|"
    r"login\s+windows|assinatura\s+office|netflix|spotify|"
    r"how\s+to\s+fix\s+a\s+girl|horoscope)",
    re.I,
)

_TECH_HINT = re.compile(
    r"(schematic|service\s*manual|datasheet|circuito|esquema|fonte|smps|"
    r"standby|capacitor|mosfet|smd|pcb|board|repair|defeito|não\s*liga|"
    r"nao\s*liga|fuse|fusível|voltage|tensão|eletr[oô]nic)",
    re.I,
)


def _ddgs():
    try:
        from ddgs import DDGS

        return DDGS
    except Exception:
        from duckduckgo_search import DDGS

        return DDGS


def is_researchable_device(board_model: str) -> bool:
    """True só se houver modelo/marca concreto o bastante para busca técnica."""
    device = (board_model or "").strip()
    if len(device) < 4:
        return False
    if _GENERIC_DEVICE.match(device):
        return False
    # Precisa de letra+número ou pelo menos 2 tokens (ex.: "Samsung UN32", "placa Fonte XYZ")
    tokens = [t for t in re.split(r"\s+", device) if t]
    has_alnum = bool(re.search(r"[A-Za-z].*\d|\d.*[A-Za-z]", device))
    if has_alnum:
        return True
    if len(tokens) >= 2 and len(device) >= 8:
        return True
    return False


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _is_junk(title: str, body: str, href: str) -> bool:
    blob = f"{title} {body} {href}"
    if _JUNK_HOST.search(href) or _JUNK_HOST.search(_host(href)):
        return True
    if _JUNK_TEXT.search(blob):
        return True
    return False


def _is_useful(title: str, body: str) -> bool:
    blob = f"{title} {body}"
    return bool(_TECH_HINT.search(blob))


def _search_batch(queries: list[str], max_results: int = 6) -> list[str]:
    snippets: list[str] = []
    try:
        DDGS = _ddgs()
    except Exception:
        return ["(biblioteca de busca indisponível)"]

    def _run() -> list[str]:
        out: list[str] = []
        with DDGS() as ddgs:
            for q in queries:
                try:
                    hits = list(
                        ddgs.text(q, max_results=max(3, max_results), region="br-pt")
                    )
                except Exception:
                    continue
                for hit in hits:
                    title = (hit.get("title") or "").strip()
                    body = (hit.get("body") or hit.get("snippet") or "").strip()
                    href = (hit.get("href") or "").strip()
                    if not body and not title:
                        continue
                    if _is_junk(title, body, href):
                        continue
                    if not _is_useful(title, body):
                        continue
                    line = f"- {title}: {body}" + (f" ({href})" if href else "")
                    if line not in out:
                        out.append(line)
                if len(out) >= max_results:
                    break
        return out

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_run)
            snippets = fut.result(timeout=6)
    except FuturesTimeout:
        return ["(pesquisa web demorou demais — sigo com conhecimento técnico)"]
    except Exception as exc:  # noqa: BLE001
        return [f"(pesquisa indisponível: {exc})"]
    return snippets[:max_results]


def _tech_queries(device: str, symptom: str) -> list[str]:
    sym = symptom.strip()
    base = device.strip()
    # Operadores / termos técnicos (manuais e esquemas, não blogs genéricos).
    queries = [
        f'{base} "service manual" OR schematic OR "circuit diagram"',
        f"{base} {sym} repair OR defect OR short OR standby".strip(),
        f"{base} esquema elétrico OR manual de serviço OR datasheet",
    ]
    if sym:
        queries.append(f"{base} {sym} capacitor OR MOSFET OR fuse OR SMPS")
    return queries


def research_electronics(query: str, max_results: int = 5) -> str:
    """Busca genérica — só se a query já trouxer modelo concreto."""
    q = (query or "").strip()
    if not q or len(q) < 8:
        return ""
    # Extrai um “device” bruto da query; se for genérico, aborta.
    if not is_researchable_device(q) and not re.search(
        r"[A-Za-z].*\d|\d.*[A-Za-z]", q
    ):
        return (
            "(sem modelo concreto — peço marca/modelo da placa antes de pesquisar na web)"
        )
    searches = _tech_queries(q, "")
    snippets = _search_batch(searches, max_results=max_results)
    if not snippets:
        return "(nenhum resultado técnico útil — tente modelo + sintoma mais específicos)"
    return "\n".join(snippets)


def research_device_deep(
    board_model: str,
    symptom: str = "",
    *,
    max_results: int = 5,
) -> str:
    """Pesquisa ativa: manuais, esquemas e defeitos — só com modelo real."""
    device = (board_model or "").strip()
    sym = (symptom or "").strip()
    if not is_researchable_device(device):
        return (
            "(pesquisa web adiada: preciso da marca/modelo da placa ou aparelho. "
            "Ex.: 'Samsung UN32J4300', 'fonte Philco PBF', 'placa inverter LG'. "
            "Sem isso a busca devolve lixo genérico.)"
        )

    cache_key = f"deep::{device.lower()}::{sym.lower()}"
    if cache_key in _RESEARCH_CACHE:
        return _RESEARCH_CACHE[cache_key]

    queries = _tech_queries(device, sym)
    snippets = _search_batch(queries, max_results=min(max_results, 5))
    if not snippets:
        result = (
            f"(nenhum manual/esquema útil para “{device}” ainda — "
            "sigo no mapa visual + medições)"
        )
    else:
        header = (
            "PESQUISA TÉCNICA NA WEB (manuais / esquemas / defeitos):\n"
            f"Alvo: {device} | Sintoma: {sym or '—'}\n"
            "Ignore qualquer resultado que não seja eletrônica de conserto. "
            "Cite só pistas técnicas e proponha o 1º teste."
        )
        result = header + "\n" + "\n".join(snippets)
    _RESEARCH_CACHE[cache_key] = result
    return result


def research_for_case(case: dict[str, Any], user_text: str = "") -> str:
    """Pesquisa para o caso — só com modelo concreto (com cache)."""
    board = str(case.get("board_model") or "").strip()
    symptom = str(case.get("symptom") or "").strip()
    cached = (case.get("last_research") or "").strip()
    if cached and is_researchable_device(board) and len(cached) > 80:
        # Não reusa cache de “adiada” / lixo antigo
        if "pesquisa web adiada" not in cached.lower() and "0xcaa" not in cached.lower():
            return cached
    if is_researchable_device(board):
        return research_device_deep(board, symptom or user_text)
    # Sem modelo: NÃO pesquisa com texto genérico do usuário.
    return (
        "(pesquisa web adiada: diga a marca/modelo do aparelho ou da placa "
        "para eu buscar manual/esquema de verdade.)"
    )
