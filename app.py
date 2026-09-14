"""
JARVIS de Bancada — diagnóstico eletrônico com voz, visão, pesquisa e memória.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from agent.diagnostic import DiagnosticAgent
from agent.docs import extract_text_from_bytes
from agent.failures import find_similar, list_failures
from agent.listen_component import continuous_listen
from agent.memory import CaseMemory
from agent.safety import safety_brief, safety_checklist
from agent.vision import annotate_board, zoom_around_probes
from agent.voice import extract_intake_from_speech, speak_text, transcribe_audio

st.set_page_config(
    page_title="JARVIS de Bancada",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# PWA hooks (manifest + service worker)
components.html(
    """
    <script>
    try {
      const link = window.parent.document.querySelector('link[rel="manifest"]') || window.parent.document.createElement('link');
      link.rel = 'manifest';
      link.href = '/app/static/manifest.json';
      window.parent.document.head.appendChild(link);
      if ('serviceWorker' in window.parent.navigator) {
        window.parent.navigator.serviceWorker.register('/app/static/sw.js').catch(()=>{});
      }
    } catch (e) {}
    </script>
    """,
    height=0,
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
VERDICT_PT = {"ok": "OK", "fail": "FALHOU", "pending": "pendente", "unknown": "indefinido"}
PROVIDER_PT = {"openai": "OpenAI (GPT-4o)", "anthropic": "Claude 3.5 Sonnet"}


def pt(mapa: dict[str, str], valor: str | None, padrao: str = "—") -> str:
    if not valor:
        return padrao
    return mapa.get(valor, valor)


def get_agent() -> DiagnosticAgent:
    if "agent" not in st.session_state:
        st.session_state.agent = DiagnosticAgent(CaseMemory(DATA_DIR))
    return st.session_state.agent


def ensure_session() -> None:
    defaults = {
        "case_id": None,
        "last_image_bytes": None,
        "last_image_name": None,
        "last_tts_bytes": None,
        "voice_out": True,
        "listen_on": True,
        "pending_transcript": "",
        "last_voice_hash": "",
        "agent_speaking": False,
        "voice_status": "idle",
        "safety_ack": False,
        "last_manual_audio_hash": "",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def play_agent_voice(text: str) -> None:
    if not st.session_state.voice_out or not (text or "").strip():
        return
    st.session_state.voice_status = "speaking"
    st.session_state.agent_speaking = True
    try:
        audio = speak_text(text)
        st.session_state.last_tts_bytes = audio
        st.audio(audio, format="audio/mp3", autoplay=True)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Voz indisponível (API/fallback): {exc}")
    finally:
        st.session_state.agent_speaking = False
        st.session_state.voice_status = "listening" if st.session_state.listen_on else "idle"


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
    st.session_state.voice_status = "processing"
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
            st.session_state.voice_status = "listening"
            st.error(f"Falha ao falar com a IA: {exc}")
            st.stop()
    if result.get("awaiting_confirm"):
        st.info("Aguardando sua confirmação da medição.")
    if result.get("safety_brief"):
        st.caption(f"🛡️ {result['safety_brief']}")
    play_agent_voice(result.get("spoken_reply") or result.get("message") or "")
    st.rerun()


def consume_continuous_voice(key: str) -> str | None:
    if not st.session_state.listen_on:
        st.info("Escuta contínua desligada. Ligue na barra lateral.")
        return None
    st.session_state.voice_status = (
        "speaking" if st.session_state.agent_speaking else "listening"
    )
    transcript = continuous_listen(
        active=True,
        paused=bool(st.session_state.agent_speaking),
        agent_speaking=bool(st.session_state.agent_speaking),
        key=key,
    )
    if not transcript:
        return None
    digest = _voice_hash(transcript)
    if digest == st.session_state.last_voice_hash:
        return None
    st.session_state.last_voice_hash = digest
    st.session_state.voice_status = "processing"
    return transcript


def render_status_chip() -> None:
    status = st.session_state.get("voice_status", "idle")
    labels = {
        "idle": "⚪ Parado",
        "listening": "🟢 Ouvindo",
        "processing": "🟡 Processando",
        "speaking": "🔵 Falando",
    }
    st.markdown(f"**Status:** {labels.get(status, status)}")


def sidebar_cases(ag: DiagnosticAgent) -> None:
    st.sidebar.title("JARVIS de Bancada")
    info = ag.provider_info()
    if info.get("mock"):
        st.sidebar.warning("Sem API key — modo demo.")
    else:
        st.sidebar.success(f"IA ativa: **{pt(PROVIDER_PT, info.get('active'), 'IA')}**")

    st.session_state.voice_out = st.sidebar.toggle(
        "Agente fala as respostas", value=st.session_state.voice_out
    )
    st.session_state.listen_on = st.sidebar.toggle(
        "Escuta contínua (mãos livres)", value=st.session_state.listen_on
    )

    with st.sidebar.expander("Checklist de segurança"):
        for item in safety_checklist():
            st.markdown(f"**{item['title']}** — {item['detail']}")
        st.session_state.safety_ack = st.checkbox(
            "Li os avisos de segurança desta sessão",
            value=st.session_state.safety_ack,
        )

    with st.sidebar.expander("Banco de falhas resolvidas"):
        fails = list_failures(12)
        if not fails:
            st.caption("Nenhum caso resolvido salvo ainda.")
        else:
            for f in fails:
                st.markdown(
                    f"- `{f.get('board_model')}` · {f.get('symptom')} → **{f.get('replaced_part')}**"
                )

    cases = ag.list_cases()
    if cases:
        labels = {
            c["case_id"]: (
                f"{c['board_model']} · {pt(STATUS_PT, c.get('status'))} · "
                f"{c['measurements']} med."
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
    else:
        st.sidebar.caption("Nenhum caso ainda.")

    if st.session_state.case_id and st.sidebar.button(
        "Encerrar / novo caso", use_container_width=True
    ):
        for k in (
            "case_id",
            "last_image_bytes",
            "last_image_name",
            "last_tts_bytes",
            "pending_transcript",
            "last_voice_hash",
        ):
            st.session_state[k] = None if k != "pending_transcript" and k != "last_voice_hash" else ""
        st.session_state.case_id = None
        st.rerun()

    st.sidebar.caption("No celular: abra no Chrome → menu → Instalar app (PWA).")


def intake_form(ag: DiagnosticAgent) -> None:
    st.markdown("## JARVIS de Bancada")
    st.markdown(
        "Assistente estilo Homem de Ferro para eletrônica: escuta, vê a placa, pesquisa e fala."
    )
    render_status_chip()
    st.caption(f"🛡️ {safety_brief('intake')}")

    if not st.session_state.safety_ack:
        st.warning("Marque o checklist de segurança na barra lateral antes de começar.")

    st.markdown("### Microfone contínuo")
    heard = consume_continuous_voice(key="listen_intake")
    if heard and st.session_state.safety_ack:
        st.success(f"Ouvi: “{heard}”")
        with st.spinner("Abrindo caso…"):
            try:
                intake = extract_intake_from_speech(heard)
                result = ag.start_case(intake["board_model"], intake["symptom"])
            except Exception as exc:  # noqa: BLE001
                st.error(f"Falha: {exc}")
                st.stop()
        st.session_state.case_id = result["case"]["case_id"]
        play_agent_voice(result.get("spoken_reply") or result.get("message") or "")
        st.rerun()

    with st.expander("Alternativa: áudio manual ou texto"):
        voice = st.audio_input("Gravação manual")
        if voice is not None and st.session_state.safety_ack:
            digest = hashlib.sha1(voice.getvalue()).hexdigest()
            if digest != st.session_state.last_manual_audio_hash:
                st.session_state.last_manual_audio_hash = digest
                st.session_state.voice_status = "processing"
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
            board = st.text_input("Modelo da placa")
            symptom = st.text_area("Sintoma", height=90)
            ok = st.form_submit_button("Iniciar", type="primary", use_container_width=True)
        if ok:
            if not st.session_state.safety_ack:
                st.error("Confirme o checklist de segurança na lateral.")
                return
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
            f"Caso `{case['case_id']}` · **{pt(STATUS_PT, case.get('status'))}** · "
            f"**{pt(PHASE_PT, case.get('phase'))}** · "
            f"reavaliações: {case.get('strategy_revisions', 0)}"
        )
        st.markdown(f"**Sintoma:** {case['symptom']}")
        render_status_chip()
        st.caption(f"🛡️ {safety_brief(case.get('phase'))}")

        if st.session_state.last_tts_bytes:
            st.markdown("#### Agente falando")
            st.audio(st.session_state.last_tts_bytes, format="audio/mp3")

        if case.get("pending_confirm"):
            st.warning(
                "Confirme a medição: diga **confirmo** para ir ao modo solução, ou **não** se errou."
            )

        st.divider()
        for msg in case.get("messages", []):
            papel = "assistant" if msg["role"] == "assistant" else "user"
            with st.chat_message(papel):
                st.caption("JARVIS" if msg["role"] == "assistant" else "Você")
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
        heard = consume_continuous_voice(key=f"listen_case_{case['case_id']}")
        if heard:
            st.success(f"Ouvi: “{heard}”")
            submit_user_turn(ag, case, heard)

        with st.expander("Foto, esquema/PDF, áudio ou texto"):
            photo = st.file_uploader(
                "Foto da placa", type=["jpg", "jpeg", "png", "webp"], key=f"photo_{case['case_id']}"
            )
            doc = st.file_uploader(
                "Esquema / datasheet (PDF ou TXT)",
                type=["pdf", "txt", "md"],
                key=f"doc_{case['case_id']}",
            )
            if doc is not None and st.button("Anexar documento ao caso", use_container_width=True):
                with st.spinner("Lendo documento…"):
                    try:
                        result = ag.attach_document(case, doc.name, doc.getvalue())
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Documento: {exc}")
                        st.stop()
                preview = extract_text_from_bytes(doc.name, doc.getvalue())[:400]
                st.caption(f"Trecho lido: {preview}…")
                play_agent_voice(result.get("spoken_reply") or result.get("message") or "")
                st.rerun()

            manual = st.audio_input("Gravação manual")
            if manual is not None:
                digest = hashlib.sha1(manual.getvalue()).hexdigest()
                if digest != st.session_state.last_manual_audio_hash:
                    st.session_state.last_manual_audio_hash = digest
                    st.session_state.voice_status = "processing"
                    with st.spinner("Transcrevendo…"):
                        try:
                            transcript = transcribe_audio(
                                manual.getvalue(), filename=manual.name or "fala.wav"
                            )
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"Áudio: {exc}")
                            st.stop()
                    image_bytes = image_name = None
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
                user_text = st.text_input("Mensagem / valor medido")
                send = st.form_submit_button("Enviar texto/foto", use_container_width=True)
            if send:
                if not user_text.strip() and photo is None:
                    st.warning("Digite algo ou anexe foto.")
                else:
                    image_bytes = image_name = None
                    image_mime = "image/jpeg"
                    text = user_text.strip() or "Analise a foto e diga a próxima medição."
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
                        text,
                        image_bytes=image_bytes,
                        image_name=image_name,
                        image_mime=image_mime,
                    )

        with st.expander("Marcar caso como resolvido (salva no banco de falhas)"):
            part = st.text_input("Peça que resolveu", placeholder="Ex: C905 / CI standby")
            notes = st.text_input("Nota (opcional)")
            if st.button("Salvar no banco de falhas", type="primary"):
                if not part.strip():
                    st.error("Informe a peça.")
                else:
                    ag.resolve_case(case, part.strip(), notes.strip())
                    st.success("Salvo no banco de falhas.")
                    play_agent_voice(f"Caso resolvido. Salvei a troca de {part.strip()} no banco.")
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

        docs = case.get("documents") or []
        if docs:
            st.markdown("**Documentos:** " + ", ".join(f"`{d.get('filename')}`" for d in docs))

        if st.session_state.last_image_bytes:
            st.markdown("### Foto + marcação")
            coords = []
            if last_meta.get("probe"):
                coords = last_meta["probe"].get("coordinates") or []
            if not coords and case.get("probe_hints"):
                last_hint = case["probe_hints"][-1] or {}
                coords = last_hint.get("coordinates") or []
            if coords:
                annotated = annotate_board(st.session_state.last_image_bytes, coords)
                st.image(annotated, caption="Cruzes = onde colocar as pontas", use_container_width=True)
                zoom = zoom_around_probes(st.session_state.last_image_bytes, coords)
                if zoom is not None:
                    st.markdown("#### Zoom da área")
                    st.image(zoom, caption="Região ampliada do ponto de teste", use_container_width=True)
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

        sims = find_similar(str(case.get("board_model") or ""), str(case.get("symptom") or ""))
        if sims:
            st.markdown("### Parecidos no banco")
            for f in sims[:5]:
                st.caption(
                    f"{f.get('board_model')} · {f.get('symptom')} → **{f.get('replaced_part')}**"
                )


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
