"""Pesquisa web para apoiar o diagnóstico quando o modelo/sintoma é específico."""

from __future__ import annotations

from typing import Any


def research_electronics(query: str, max_results: int = 5) -> str:
    """Busca referências públicas (esquemas, falhas comuns, fóruns) e resume em texto."""
    q = (query or "").strip()
    if not q:
        return ""
    try:
        try:
            from ddgs import DDGS
        except Exception:
            from duckduckgo_search import DDGS
    except Exception:
        return ""

    snippets: list[str] = []
    searches = [
        f"{q} TV fonte SMPS não liga defeito",
        f"{q} placa eletrônica diagnóstico",
        f"{q} standby voltage short",
    ]
    try:
        with DDGS() as ddgs:
            for s in searches:
                hits = list(
                    ddgs.text(s, max_results=max(2, max_results // 2), region="br-pt")
                )
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
        snippets = snippets[:max_results]
    except Exception as exc:  # noqa: BLE001
        return f"(pesquisa indisponível: {exc})"

    if not snippets:
        return "(nenhum resultado útil encontrado na pesquisa)"
    return "\n".join(snippets)


def research_for_case(case: dict[str, Any], user_text: str = "") -> str:
    board = case.get("board_model") or ""
    symptom = case.get("symptom") or ""
    query = f"{board} {symptom} {user_text}".strip()
    return research_electronics(query)
