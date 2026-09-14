"""
JARVIS de Bancada — Agente de Diagnóstico Eletrônico
Escuta contínua + fala automática + pesquisa quando precisa.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

from agent.listen_component import continuous_listen
from agent.memory import CaseMemory
from agent.voice import extract_intake_from_speech, speak_text, transcribe_audio

st.set_page_config(
    page_title="JARVIS de Bancada",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path(__file__).resolve().parent / "data" / "cases"
UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

STATUS_PT = {
    "intake": "abertura",
    "diagnosing": "diagnosticando",
    "solution": "solução",
    "reassess": "reavaliação",
    "resolved": "resolvido",
    "abandoned": "abandonado",
}
PHASE_PT = {
    "intake": "abertura",
    "vision": "análise da foto",
    "measure": "medição",
    "solution": "solução",
    "reassess": "reavaliação",
    "done": "concluído",
}
VERDICT_PT = {
    "ok": "OK",
    "fail": "FALHOU",
    "pending": "pendente",
    "unknown": "indefinido",
}
PROVIDER_PT = {
    "openai": "OpenAI (GPT-4o)",
    "anthropic": "Claude 3.5 Sonnet",
}


def pt(mapa: dict[str, str], valor: str | None, padrao: str = "—") -> str:
    if not valor:
        return padrao
    return mapa.get(valor, valor)


def get_agent() -> DiagnosticAgent:
    if "agent" not in st.session_state:
        st.session_state.agent = DiagnosticAgent(CaseMemory(DATA_DIR))
    return st.session_state.agent


def ensure_session() -> None:
    st.session_state.setdefault("case_id", None)
    st.session_state.setdefault("last_image_bytes", None)
    st.session_state.setdefault("last_image_name", None)
    st.session_state.setdefault("last_tts_bytes", None)
    st.session_state.setdefault("voice_out", True)
    st.session_state.setdefault("listen_on", True)
    st.session_state.setdefault("pending_transcript", "")
    st.session_state.setdefault("last_voice_hash", "")
    st.session_state.setdefault("agent_speaking", False)


def annotate_image(image_bytes: bytes, coordinates: list[dict]) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    colors = {
        "ponta vermelha": (220, 40, 40),
        "ponta preta": (30, 30, 30),
        "default": (20, 120, 220),
    }
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for item in coordinates or []:
        label = str(item.get("label") or "ponto")
        x = float(item.get("x", 50)) / 100.0 * w
        y = float(item.get("y", 50)) / 100.0 * h
        key = label.lower()
        color = (
            colors["ponta vermelha"]
            if "vermelha" in key or "red" in key
            else colors["ponta preta"]
            if "preta" in key or "black" in key
            else colors["default"]
        )
        r = max(8, min(w, h) // 40)
        draw.ellipse((x - r, y - r, x + r, y + r), outline=color, width=max(2, r // 3))
        draw.line((x - r * 1.6, y, x + r * 1.6, y), fill=color, width=max(2, r // 4))
        draw.line((x, y - r * 1.6, x, y + r * 1.6), fill=color, width=max(2, r // 4))
        draw.text((x + r + 4, y - r), label, fill=color, font=font)
    return img


def play_agent_voice(text: str) -> None:
    if not st.session_state.voice_out or not (text or "").strip():
        return
    try:
        st.session_state.agent_speaking = True
        audio = speak_text(text)
        st.session_state.last_tts_bytes = audio
        st.audio(audio, format="audio/mp3", autoplay=True)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Não consegui gerar a voz do agente: {exc}")
    finally:
        st.session_state.agent_speaking = False


def render_probe_card(probe: dict | None) -> None:
    if not probe or not probe.get("point_name"):
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


def _voice_hash(text: str) -> str:
    return hashlib.sha1(text.strip().lower().encode("utf-8")).hexdigest()


def submit_user_turn(
    ag: DiagnosticAgent,
    case: dict,
    text: str,
    image_bytes: bytes | None = None,
    image_name: str | None = None,
    image_mime: str = "image/jpeg",
) -> None:
    st.session_state.case_id = case["case_id"]
    with st.spinner("JARVIS analisando…"):
        try:
            result = ag.handle_user(
                case,
                text,
                image_bytes=image_bytes,
                image_name=image_name,
                image_mime=image_mime,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha ao falar com a IA: {exc}")
            st.stop()
    play_agent_voice(result.get("spoken_reply") or result.get("message") or "")
    st.rerun()


def consume_continuous_voice(key: str) -> str | None:
    """Escuta contínua: devolve texto novo quando o usuário termina de falar."""
    if not st.session_state.listen_on:
        st.info("Escuta contínua desligada. Ligue na barra lateral ou use o gravador abaixo.")
        return None
    transcript = continuous_listen(
        active=True,
        paused=bool(st.session_state.agent_speaking),
        key=key,
    )
    if not transcript:
        return None
    digest = _voice_hash(transcript)
    if digest == st.session_state.last_voice_hash:
        return None
    st.session_state.last_voice_hash = digest
    return transcript


def sidebar_cases(ag: DiagnosticAgent) -> None:
    st.sidebar.title("JARVIS de Bancada")
    info = ag.provider_info()
    if info.get("mock"):
        st.sidebar.warning(
            "Sem API key — modo demo. Configure `OPENAI_API_KEY` no `.env`."
        )
    else:
        nome = pt(PROVIDER_PT, info.get("active"), "IA")
        st.sidebar.success(f"IA ativa: **{nome}**")

    st.session_state.voice_out = st.sidebar.toggle(
        "Agente fala as respostas",
        value=st.session_state.voice_out,
        help="Lê a ordem em voz alta (TTS).",
    )
    st.session_state.listen_on = st.sidebar.toggle(
        "Escuta contínua (mãos livres)",
        value=st.session_state.listen_on,
        help="Ouve sem apertar botão. Detecta quando você termina a frase.",
    )

    cases = ag.list_cases()
    if not cases:
        st.sidebar.caption("Nenhum caso ainda.")
    else:
        labels = {
            c["case_id"]: (
                f"{c['board_model']} · {pt(STATUS_PT, c.get('status'))} · "
                f"{c['measurements']} medições"
            )
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

    if st.session_state.case_id and st.sidebar.button(
        "Encerrar e começar novo caso", use_container_width=True
    ):
        st.session_state.case_id = None
        st.session_state.last_image_bytes = None
        st.session_state.last_image_name = None
        st.session_state.last_tts_bytes = None
        st.session_state.pending_transcript = ""
        st.session_state.last_voice_hash = ""
        st.rerun()


def intake_form(ag: DiagnosticAgent) -> None:
    st.markdown("## JARVIS de Bancada")
    st.markdown(
        "Fale naturalmente: **modelo da placa + sintoma**. "
        "Eu escuto até você terminar a frase, analiso e respondo falando."
    )

    st.markdown("### Microfone contínuo")
    heard = consume_continuous_voice(key="listen_intake")
    if heard:
        st.success(f"Ouvi: “{heard}”")
        with st.spinner("Entendendo e abrindo o caso…"):
            try:
                intake = extract_intake_from_speech(heard)
                result = ag.start_case(intake["board_model"], intake["symptom"])
            except Exception as exc:  # noqa: BLE001
                st.error(f"Falha ao iniciar: {exc}")
                st.stop()
        st.session_state.case_id = result["case"]["case_id"]
        play_agent_voice(result.get("spoken_reply") or result.get("message") or "")
        st.rerun()

    with st.expander("Alternativa: gravar um áudio ou digitar"):
        voice = st.audio_input("Gravação manual (opcional)")
        if voice is not None:
            # auto-processa sem botão extra
            digest = hashlib.sha1(voice.getvalue()).hexdigest()
            if digest != st.session_state.get("last_manual_audio_hash"):
                st.session_state.last_manual_audio_hash = digest
                with st.spinner("Transcrevendo…"):
                    try:
                        transcript = transcribe_audio(
                            voice.getvalue(), filename=voice.name or "inicio.wav"
                        )
                        intake = extract_intake_from_speech(transcript)
                        result = ag.start_case(intake["board_model"], intake["symptom"])
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Falha: {exc}")
                        st.stop()
                st.session_state.case_id = result["case"]["case_id"]
                play_agent_voice(result.get("spoken_reply") or result.get("message") or "")
                st.rerun()

        with st.form("intake"):
            board = st.text_input("Modelo da placa", placeholder="Ex: Philco PTV32 / fonte SMPS")
            symptom = st.text_area("Sintoma", placeholder="Ex: Não liga, LED apaga…", height=90)
            submitted = st.form_submit_button("Iniciar", type="primary", use_container_width=True)
        if submitted:
            if not board.strip() or not symptom.strip():
                st.error("Informe placa e sintoma.")
                return
            result = ag.start_case(board, symptom)
            st.session_state.case_id = result["case"]["case_id"]
            play_agent_voice(result.get("spoken_reply") or result.get("message") or "")
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
            f"Caso `{case['case_id']}` · situação **{pt(STATUS_PT, case.get('status'))}** · "
            f"etapa **{pt(PHASE_PT, case.get('phase'))}** · "
            f"reavaliações: {case.get('strategy_revisions', 0)}"
        )
        st.markdown(f"**Sintoma:** {case['symptom']}")

        if st.session_state.last_tts_bytes:
            st.markdown("#### Agente falando")
            st.audio(st.session_state.last_tts_bytes, format="audio/mp3")

        st.divider()
        for msg in case.get("messages", []):
            papel = "assistant" if msg["role"] == "assistant" else "user"
            with st.chat_message(papel):
                autor = "JARVIS" if msg["role"] == "assistant" else "Você"
                st.caption(autor)
                st.markdown(msg["content"])
                meta = msg.get("meta") or {}
                if meta.get("probe") and msg["role"] == "assistant":
                    render_probe_card(meta["probe"])
                if meta.get("solution") and meta.get("verdict") == "fail":
                    render_solution(meta["solution"])

        last_meta: dict = {}
        for msg in reversed(case.get("messages", [])):
            if msg.get("role") == "assistant" and msg.get("meta"):
                last_meta = msg["meta"]
                break

        st.divider()
        st.markdown("#### Fale com o JARVIS")
        if last_meta.get("next_action") == "ask_photo":
            st.caption("Pode anexar a foto e dizer “foto enviada”.")
        else:
            st.caption('Fale naturalmente: “deu 4 vírgula 8 volts”, “o que é esse CI?”, “troquei e não resolveu”.')

        heard = consume_continuous_voice(key=f"listen_case_{case['case_id']}")
        if heard:
            st.success(f"Ouvi: “{heard}”")
            submit_user_turn(ag, case, heard)

        with st.expander("Foto, áudio manual ou texto"):
            photo = st.file_uploader(
                "Foto da placa",
                type=["jpg", "jpeg", "png", "webp"],
                key=f"photo_{case['case_id']}",
            )
            manual = st.audio_input("Gravação manual (se a escuta contínua falhar)")
            if manual is not None:
                digest = hashlib.sha1(manual.getvalue()).hexdigest()
                if digest != st.session_state.get("last_manual_audio_hash"):
                    st.session_state.last_manual_audio_hash = digest
                    with st.spinner("Transcrevendo…"):
                        try:
                            transcript = transcribe_audio(
                                manual.getvalue(), filename=manual.name or "fala.wav"
                            )
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"Áudio: {exc}")
                            st.stop()
                    image_bytes = None
                    image_name = None
                    image_mime = "image/jpeg"
                    if photo is not None:
                        image_bytes = photo.getvalue()
                        image_name = photo.name
                        image_mime = photo.type or "image/jpeg"
                        st.session_state.last_image_bytes = image_bytes
                        st.session_state.last_image_name = image_name
                        (UPLOAD_DIR / f"{case['case_id']}_{image_name}").write_bytes(image_bytes)
                    submit_user_turn(
                        ag,
                        case,
                        transcript,
                        image_bytes=image_bytes,
                        image_name=image_name,
                        image_mime=image_mime,
                    )

            with st.form("reply", clear_on_submit=True):
                user_text = st.text_input(
                    "Mensagem / valor medido",
                    value=st.session_state.pending_transcript,
                    placeholder="Digite se preferir",
                )
                send = st.form_submit_button("Enviar texto/foto", use_container_width=True)
            if send:
                if not user_text.strip() and photo is None:
                    st.warning("Digite algo ou anexe foto.")
                else:
                    image_bytes = None
                    image_name = None
                    image_mime = "image/jpeg"
                    text = user_text.strip() or "Analise a foto anexada e diga a próxima medição."
                    if photo is not None:
                        image_bytes = photo.getvalue()
                        image_name = photo.name
                        image_mime = photo.type or "image/jpeg"
                        st.session_state.last_image_bytes = image_bytes
                        st.session_state.last_image_name = image_name
                        (UPLOAD_DIR / f"{case['case_id']}_{image_name}").write_bytes(image_bytes)
                    st.session_state.pending_transcript = ""
                    submit_user_turn(
                        ag,
                        case,
                        text,
                        image_bytes=image_bytes,
                        image_name=image_name,
                        image_mime=image_mime,
                    )

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
                        "Resultado": pt(VERDICT_PT, m.get("verdict")),
                    }
                    for m in measures
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Nenhuma medição ainda.")

        suspects = case.get("suspect_components") or []
        if suspects:
            st.markdown("**Suspeitos:** " + ", ".join(f"`{s}`" for s in suspects))

        if st.session_state.last_image_bytes:
            st.markdown("### Foto + marcação")
            coords = []
            if last_meta.get("probe"):
                coords = last_meta["probe"].get("coordinates") or []
            if not coords and case.get("probe_hints"):
                coords = (case["probe_hints"][-1] or {}).get("coordinates") or []
            if coords:
                st.image(
                    annotate_image(st.session_state.last_image_bytes, coords),
                    caption="Cruzes = pontas",
                    use_container_width=True,
                )
            else:
                st.image(
                    st.session_state.last_image_bytes,
                    caption=st.session_state.last_image_name or "placa",
                    use_container_width=True,
                )

        notes = case.get("solution_notes") or []
        if notes:
            with st.expander("Notas / reavaliação"):
                for n in notes[-8:]:
                    st.write(n)


def main() -> None:
    ensure_session()
    ag = get_agent()
    sidebar_cases(ag)
    if st.session_state.case_id:
        case_view(ag)
    else:
        intake_form(ag)


if __name__ == "__main__":
    main()
