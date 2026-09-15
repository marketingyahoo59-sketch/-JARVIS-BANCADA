"""Pesquisa web ativa — manuais, esquemas e defeitos comuns."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

# Cache simples em memória do processo (evita 7 buscas a cada frase).
_RESEARCH_CACHE: dict[str, str] = {}


def _ddgs():
    try:
        from ddgs import DDGS

        return DDGS
    except Exception:
        from duckduckgo_search import DDGS

        return DDGS


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
                        ddgs.text(q, max_results=max(2, max_results // 2), region="br-pt")
                    )
                except Exception:
                    continue
                for hit in hits:
                    title = (hit.get("title") or "").strip()
                    body = (hit.get("body") or hit.get("snippet") or "").strip()
                    href = (hit.get("href") or "").strip()
                    if not body and not title:
                        continue
                    line = f"- {title}: {body}" + (f" ({href})" if href else "")
                    if line not in out:
                        out.append(line)
                if len(out) >= max_results:
                    break
        return out

    try:
        # Timeout curto — resposta rápida na bancada (Cloud Run/local).
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_run)
            snippets = fut.result(timeout=6)
    except FuturesTimeout:
        return ["(pesquisa web demorou demais — sigo com conhecimento técnico)"]
    except Exception as exc:  # noqa: BLE001
        return [f"(pesquisa indisponível: {exc})"]
    return snippets[:max_results]


def research_electronics(query: str, max_results: int = 5) -> str:
    """Busca genérica de apoio ao diagnóstico."""
    q = (query or "").strip()
    if not q:
        return ""
    searches = [
        f"{q} TV fonte SMPS não liga defeito",
        f"{q} placa eletrônica diagnóstico",
        f"{q} standby voltage short",
    ]
    snippets = _search_batch(searches, max_results=max_results)
    if not snippets:
        return "(nenhum resultado útil encontrado na pesquisa)"
    return "\n".join(snippets)


def research_device_deep(
    board_model: str,
    symptom: str = "",
    *,
    max_results: int = 5,
) -> str:
    """Pesquisa ativa: manuais, esquemas elétricos e defeitos comuns do aparelho."""
    device = (board_model or "").strip()
    sym = (symptom or "").strip()
    if not device and not sym:
        return ""

    cache_key = f"deep::{device.lower()}::{sym.lower()}"
    if cache_key in _RESEARCH_CACHE:
        return _RESEARCH_CACHE[cache_key]

    # Poucas queries = menos latência (1ª resposta mais rápida).
    queries = [
        f"{device} {sym} defeito comum repair".strip(),
        f"{device} service manual schematic",
    ]
    snippets = _search_batch(queries, max_results=min(max_results, 4))
    if not snippets:
        result = "(nenhum manual/esquema/defeito comum encontrado ainda)"
    else:
        header = (
            "PESQUISA ATIVA NA WEB (manuais / esquemas / defeitos comuns):\n"
            f"Alvo: {device or '—'} | Sintoma: {sym or '—'}\n"
            "Use isto para liderar: cite o defeito mais citado e proponha o 1º teste."
        )
        result = header + "\n" + "\n".join(snippets)
    _RESEARCH_CACHE[cache_key] = result
    return result


def research_for_case(case: dict[str, Any], user_text: str = "") -> str:
    """Pesquisa para o caso — profunda se já houver modelo (com cache)."""
    board = case.get("board_model") or ""
    symptom = case.get("symptom") or ""
    # Reusa pesquisa já feita neste caso (não refaz a cada “bom dia”).
    cached = (case.get("last_research") or "").strip()
    if cached and board.strip() and len(cached) > 80:
        return cached
    if board.strip():
        return research_device_deep(board, symptom or user_text)
    query = f"{board} {symptom} {user_text}".strip()
    return research_electronics(query)
