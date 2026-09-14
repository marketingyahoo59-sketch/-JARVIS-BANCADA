"""
Agente de Diagnóstico Eletrônico Ativo — Streamlit
O usuário é as mãos; a IA é o cérebro do conserto.
"""

from __future__ import annotations

import io
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

from agent.diagnostic import DiagnosticAgent
from agent.memory import CaseMemory

st.set_page_config(
    page_title="Agente de Diagnóstico Eletrônico",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path(__file__).resolve().parent / "data" / "cases"
UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def agent() -> DiagnosticAgent:
    if "agent" not in st.session_state:
        st.session_state.agent = DiagnosticAgent(CaseMemory(DATA_DIR))
    return st.session_state.agent


def ensure_session() -> None:
    st.session_state.setdefault("case_id", None)
    st.session_state.setdefault("last_image_bytes", None)
    st.session_state.setdefault("last_image_name", None)


def annotate_image(image_bytes: bytes, coordinates: list[dict]) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    colors = {"ponta vermelha": (220, 40, 40), "ponta preta": (30, 30, 30), "default": (20, 120, 220)}
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for item in coordinates or []:
        label = str(item.get("label") or "ponto")
        x = float(item.get("x", 50)) / 100.0 * w
        y = float(item.get("y", 50)) / 100.0 * h
        key = label.lower()
        color = colors["ponta vermelha"] if "vermelha" in key or "red" in key else (
            colors["ponta preta"] if "preta" in key or "black" in key else colors["default"]
        )
        r = max(8, min(w, h) // 40)
        draw.ellipse((x - r, y - r, x + r, y + r), outline=color, width=max(2, r // 3))
        draw.line((x - r * 1.6, y, x + r * 1.6, y), fill=color, width=max(2, r // 4))
        draw.line((x, y - r * 1.6, x, y + r * 1.6), fill=color, width=max(2, r // 4))
        draw.text((x + r + 4, y - r), label, fill=color, font=font)
    return img


def render_probe_card(probe: dict | None) -> None:
    if not probe:
        return
    st.markdown("#### Ordem de medição")
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"**Ponto:** {probe.get('point_name', '—')}")
        st.write(f"**Ponta preta:** {probe.get('black_probe', '—')}")
        st.write(f"**Ponta vermelha:** {probe.get('red_probe', '—')}")
    with c2:
        st.write(f"**Modo:** {probe.get('meter_mode', '—')}")
        st.write(f"**Escala:** {probe.get('scale', '—')}")
        st.write(f"**Esperado:** {probe.get('expected_value', '—')}")
    if probe.get("visual_hint"):
        st.info(probe["visual_hint"])


def render_solution(solution: dict | None) -> None:
    if not solution:
        return
    st.error("Modo solução — valor fora do esperado")
    st.write(f"**Nó com falha:** {solution.get('failed_node', '—')}")
    st.write(f"**Trocar primeiro:** {solution.get('replace_first', '—')}")
    parts = solution.get("likely_parts") or []
    if parts:
        st.markdown("**Componentes ligados a este ponto:**")
        for p in parts:
            st.markdown(
                f"- `{p.get('ref', '?')}` ({p.get('type', '?')}): "
                f"{p.get('reason', '')} → **{p.get('action', '')}**"
            )
    if solution.get("how_to_confirm"):
        st.warning(solution["how_to_confirm"])


def sidebar_cases(ag: DiagnosticAgent) -> None:
    st.sidebar.title("Casos salvos")
    info = ag.provider_info()
    if info["mock"]:
        st.sidebar.warning(
            "Sem API key — rodando em **modo demo** (lógica local). "
            "Configure `.env` com OPENAI_API_KEY ou ANTHROPIC_API_KEY."
        )
    else:
        st.sidebar.success(f"LLM ativo: **{info['active']}**")

    cases = ag.list_cases()
    if not cases:
        st.sidebar.caption("Nenhum caso ainda.")
    else:
        labels = {
            c["case_id"]: f"{c['board_model']} · {c['status']} · {c['measurements']} med."
            for c in cases
        }
        choice = st.sidebar.selectbox(
            "Abrir caso",
            options=["(novo)"] + list(labels.keys()),
            format_func=lambda x: "(novo caso)" if x == "(novo)" else labels.get(x, x),
        )
        if choice != "(novo)" and st.sidebar.button("Carregar caso", use_container_width=True):
            st.session_state.case_id = choice
            st.rerun()

    if st.session_state.case_id and st.sidebar.button("Encerrar / novo caso", use_container_width=True):
        st.session_state.case_id = None
        st.session_state.last_image_bytes = None
        st.session_state.last_image_name = None
        st.rerun()


def intake_form(ag: DiagnosticAgent) -> None:
    st.markdown("## Agente de Diagnóstico Eletrônico")
    st.markdown(
        "Você é as **mãos**. Eu sou o **cérebro** do conserto: "
        "peço uma medição por vez, interpreto o valor e digo a peça a trocar."
    )
    with st.form("intake"):
        board = st.text_input("Modelo da placa", placeholder="Ex: Fonte TV Philco PTV32G50 / Placa PCI-MAIN-XXXX")
        symptom = st.text_area(
            "Sintoma",
            placeholder="Ex: Não liga, LED standby apaga, sem 5V, cheiro de queimado na fonte…",
            height=100,
        )
        submitted = st.form_submit_button("Iniciar diagnóstico", type="primary", use_container_width=True)
    if submitted:
        if not board.strip() or not symptom.strip():
            st.error("Informe o modelo da placa e o sintoma.")
            return
        result = ag.start_case(board, symptom)
        st.session_state.case_id = result["case"]["case_id"]
        st.rerun()


def case_view(ag: DiagnosticAgent) -> None:
    case = ag.load_case(st.session_state.case_id)
    if not case:
        st.error("Caso não encontrado.")
        st.session_state.case_id = None
        return

    left, right = st.columns([1.35, 1])

    with left:
        st.markdown(f"### {case['board_model']}")
        st.caption(
            f"Caso `{case['case_id']}` · status **{case.get('status')}** · "
            f"fase **{case.get('phase')}** · revisões de estratégia: {case.get('strategy_revisions', 0)}"
        )
        st.markdown(f"**Sintoma:** {case['symptom']}")

        st.divider()
        for msg in case.get("messages", []):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                meta = msg.get("meta") or {}
                if meta.get("probe") and msg["role"] == "assistant":
                    render_probe_card(meta["probe"])
                if meta.get("solution") and meta.get("verdict") == "fail":
                    render_solution(meta["solution"])

        # Última probe/solução destacada no rodapé do chat
        last_meta = {}
        for msg in reversed(case.get("messages", [])):
            if msg.get("role") == "assistant" and msg.get("meta"):
                last_meta = msg["meta"]
                break

        st.divider()
        st.markdown("#### Sua resposta")
        photo = st.file_uploader(
            "Foto da placa (opcional nesta mensagem)",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"upload_{case['case_id']}_{len(case.get('messages', []))}",
        )
        with st.form("reply", clear_on_submit=True):
            default_hint = "Digite a medição (ex: 4.8 V) ou descreva o que fez (ex: troquei C905, não resolveu)"
            if last_meta.get("next_action") == "ask_photo":
                default_hint = "Envie a foto acima e confirme com ‘foto enviada’"
            user_text = st.text_input("Mensagem / valor medido", placeholder=default_hint)
            send = st.form_submit_button("Enviar ao agente", type="primary", use_container_width=True)

        if send:
            if not user_text.strip() and photo is None:
                st.warning("Digite uma medição/mensagem ou anexe uma foto.")
            else:
                image_bytes = None
                image_name = None
                image_mime = "image/jpeg"
                text = user_text.strip() or "Analise a foto anexada e diga a próxima medição."
                if photo is not None:
                    image_bytes = photo.getvalue()
                    image_name = photo.name
                    mime = photo.type or "image/jpeg"
                    image_mime = mime
                    st.session_state.last_image_bytes = image_bytes
                    st.session_state.last_image_name = image_name
                    dest = UPLOAD_DIR / f"{case['case_id']}_{image_name}"
                    dest.write_bytes(image_bytes)
                with st.spinner("Agente analisando…"):
                    ag.handle_user(
                        case,
                        text,
                        image_bytes=image_bytes,
                        image_name=image_name,
                        image_mime=image_mime,
                    )
                st.rerun()

    with right:
        st.markdown("### Memória do caso")
        measures = case.get("measurements", [])
        if measures:
            st.dataframe(
                [
                    {
                        "Ponto": m.get("point"),
                        "Esperado": m.get("expected"),
                        "Medido": m.get("measured"),
                        "Veredito": m.get("verdict"),
                    }
                    for m in measures
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Nenhuma medição registrada ainda.")

        suspects = case.get("suspect_components") or []
        if suspects:
            st.markdown("**Suspeitos:** " + ", ".join(f"`{s}`" for s in suspects))

        if st.session_state.last_image_bytes:
            st.markdown("### Foto + marcação das pontas")
            coords = []
            if last_meta.get("probe"):
                coords = last_meta["probe"].get("coordinates") or []
            if not coords and case.get("probe_hints"):
                coords = (case["probe_hints"][-1] or {}).get("coordinates") or []
            if coords:
                annotated = annotate_image(st.session_state.last_image_bytes, coords)
                st.image(annotated, caption="Cruzes = onde colocar as pontas", use_container_width=True)
            else:
                st.image(
                    st.session_state.last_image_bytes,
                    caption=st.session_state.last_image_name or "placa",
                    use_container_width=True,
                )
        elif case.get("images"):
            st.caption(f"{len(case['images'])} análise(s) de imagem no histórico deste caso.")

        notes = case.get("solution_notes") or []
        if notes:
            with st.expander("Notas de solução / reavaliação"):
                for n in notes[-8:]:
                    st.write(n)


def main() -> None:
    ensure_session()
    ag = agent()
    sidebar_cases(ag)
    if st.session_state.case_id:
        case_view(ag)
    else:
        intake_form(ag)


if __name__ == "__main__":
    main()
