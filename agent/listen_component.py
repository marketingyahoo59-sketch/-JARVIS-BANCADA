"""Escuta contínua — DESATIVADA (anti-crash).

O iframe Streamlit custom component causava NotFoundError: removeChild
no React do frontend (Cloud Run). Mantemos a API para não quebrar imports,
mas NÃO montamos componente nenhum. Use st.audio_input no app.
"""

from __future__ import annotations


def continuous_listen(
    *,
    active: bool = True,
    paused: bool = False,
    agent_speaking: bool = False,
    key: str = "jarvis_listen_stable",
) -> str | None:
    """No-op estável: nunca monta iframe → sem removeChild."""
    _ = (active, paused, agent_speaking, key)
    return None
