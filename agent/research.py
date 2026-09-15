"""Pesquisa web ativa — manuais, esquemas e defeitos comuns."""

from __future__ import annotations

from typing import Any


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

    try:
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
                    if line not in snippets:
                        snippets.append(line)
                if len(snippets) >= max_results:
                    break
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
    max_results: int = 8,
) -> str:
    """Pesquisa ativa: manuais, esquemas elétricos e defeitos comuns do aparelho."""
    device = (board_model or "").strip()
    sym = (symptom or "").strip()
    if not device and not sym:
        return ""

    base = f"{device} {sym}".strip()
    queries = [
        f"{device} manual serviço PDF",
        f"{device} service manual schematic",
        f"{device} esquema elétrico diagrama",
        f"{device} {sym} defeito comum",
        f"{device} common failure repair",
        f"{base} fonte SMPS não liga",
        f"{device} datasheet power board",
    ]
    snippets = _search_batch(queries, max_results=max_results)
    if not snippets:
        return "(nenhum manual/esquema/defeito comum encontrado ainda)"

    header = (
        "PESQUISA ATIVA NA WEB (manuais / esquemas / defeitos comuns):\n"
        f"Alvo: {device or '—'} | Sintoma: {sym or '—'}\n"
        "Use isto para liderar: cite o defeito mais citado e proponha o 1º teste."
    )
    return header + "\n" + "\n".join(snippets)


def research_for_case(case: dict[str, Any], user_text: str = "") -> str:
    """Pesquisa para o caso — profunda se já houver modelo."""
    board = case.get("board_model") or ""
    symptom = case.get("symptom") or ""
    if board.strip():
        deep = research_device_deep(board, symptom or user_text)
        # reforço com a fala atual
        extra_q = f"{board} {symptom} {user_text}".strip()
        extra = research_electronics(extra_q, max_results=3) if user_text else ""
        parts = [p for p in (deep, extra) if p]
        return "\n\n".join(parts)
    query = f"{board} {symptom} {user_text}".strip()
    return research_electronics(query)
