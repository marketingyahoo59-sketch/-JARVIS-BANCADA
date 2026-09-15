"""
JARVIS de Bancada — HUD estilo Homem de Ferro.
Diagnóstico eletrônico com voz, visão, pesquisa e memória.
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
    page_icon="🦾",
    layout="wide",
    initial_sidebar_state="collapsed",
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

HUD_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;800&family=Rajdhani:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Rajdhani', sans-serif !important; }

.stApp {
  background:
    radial-gradient(1100px 520px at 8% -8%, rgba(245,179,1,.18), transparent 55%),
    radial-gradient(900px 480px at 100% 0%, rgba(0,209,255,.16), transparent 52%),
    radial-gradient(700px 420px at 50% 115%, rgba(56,189,248,.10), transparent 55%),
    linear-gradient(165deg, #03060d 0%, #07111f 45%, #0a1628 100%) !important;
  color: #E8F3FF;
}

header[data-testid="stHeader"] { background: transparent !important; }
#MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; height: 0; }

.block-container {
  padding-top: .85rem !important;
  padding-bottom: 2.2rem !important;
  max-width: 1180px !important;
}

.j-shell {
  position: sticky; top: 0; z-index: 80;
  margin-bottom: 1rem;
  padding: .85rem 1rem;
  border-radius: 18px;
  border: 1px solid rgba(0,209,255,.38);
  background: linear-gradient(135deg, rgba(5,14,28,.94), rgba(12,28,48,.9));
  box-shadow: 0 0 0 1px rgba(245,179,1,.14), 0 16px 48px rgba(0,0,0,.45),
              inset 0 0 36px rgba(0,209,255,.06);
  backdrop-filter: blur(12px);
  animation: jpulse 4.8s ease-in-out infinite;
}
@keyframes jpulse {
  0%,100% { box-shadow: 0 0 0 1px rgba(245,179,1,.14), 0 16px 48px rgba(0,0,0,.45), inset 0 0 36px rgba(0,209,255,.06); }
  50% { box-shadow: 0 0 0 1px rgba(0,209,255,.4), 0 16px 56px rgba(0,209,255,.14), inset 0 0 44px rgba(245,179,1,.08); }
}
.j-row { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
.j-brand { display:flex; align-items:center; gap:12px; }
.j-arc {
  width: 44px; height: 44px; border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #fff 0 8%, #7DF9FF 10% 28%, #00D1FF 32% 58%, #0077A8 62% 100%);
  box-shadow: 0 0 22px rgba(0,209,255,.9), inset 0 0 12px rgba(255,255,255,.55);
  animation: arc 2.1s ease-in-out infinite;
}
@keyframes arc {
  0%,100% { transform: scale(1); filter: brightness(1); }
  50% { transform: scale(1.08); filter: brightness(1.22); }
}
.j-brand h1 {
  margin:0; font-family:'Orbitron',sans-serif; font-size:1.05rem; letter-spacing:.14em;
  color:#F5B301; text-shadow: 0 0 16px rgba(245,179,1,.45);
}
.j-brand p { margin:0; color:#8FB6D8; font-size:.78rem; letter-spacing:.16em; text-transform:uppercase; }

.j-hero {
  position:relative; overflow:hidden; border-radius:22px; margin-bottom:1rem;
  padding:1.45rem 1.25rem; border:1px solid rgba(0,209,255,.28);
  background:
    linear-gradient(120deg, rgba(0,209,255,.08), transparent 42%),
    linear-gradient(300deg, rgba(245,179,1,.10), transparent 48%),
    rgba(6,14,28,.78);
}
.j-hero::before {
  content:""; position:absolute; inset:0; pointer-events:none;
  background-image:
    linear-gradient(rgba(0,209,255,.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,209,255,.07) 1px, transparent 1px);
  background-size: 34px 34px;
  mask-image: linear-gradient(180deg, rgba(0,0,0,.5), transparent 88%);
  animation: drift 16s linear infinite;
}
@keyframes drift { from { background-position:0 0,0 0; } to { background-position:34px 34px,34px 34px; } }
.j-hero h2 {
  position:relative; margin:0 0 .35rem; font-family:'Orbitron',sans-serif;
  font-size:clamp(1.25rem, 3.4vw, 1.9rem); color:#EAF7FF; letter-spacing:.05em;
}
.j-hero p { position:relative; margin:0; color:#9EBFDA; font-size:1.05rem; line-height:1.35; max-width:40rem; }

.j-chip {
  display:inline-flex; align-items:center; gap:8px; padding:.35rem .8rem; border-radius:999px;
  border:1px solid rgba(0,209,255,.35); background:rgba(0,40,60,.55); color:#7DF9FF;
  font-family:'Orbitron',sans-serif; font-size:.72rem; letter-spacing:.08em;
}
.j-chip.on { border-color:#22c55e; color:#86efac; box-shadow:0 0 14px rgba(34,197,94,.25); }
.j-chip.busy { border-color:#F5B301; color:#FFE08A; }
.j-chip.talk { border-color:#38bdf8; color:#7DD3FC; }

.j-panel {
  border:1px solid rgba(0,209,255,.22); border-radius:16px; padding:1rem 1.05rem;
  background:rgba(7,16,32,.72); box-shadow: inset 0 0 28px rgba(0,209,255,.04); margin-bottom:.85rem;
}
.j-panel h3 {
  margin:0 0 .5rem; font-family:'Orbitron',sans-serif; font-size:.82rem;
  letter-spacing:.12em; color:#F5B301; text-transform:uppercase;
}

.stButton > button {
  border-radius:12px !important;
  border:1px solid rgba(245,179,1,.45) !important;
  background: linear-gradient(135deg, rgba(245,179,1,.96), rgba(255,213,106,.88)) !important;
  color:#0a0f18 !important; font-family:'Orbitron',sans-serif !important;
  font-weight:700 !important; letter-spacing:.05em !important;
  box-shadow: 0 0 18px rgba(245,179,1,.25) !important;
}
div[data-testid="stChatMessage"] {
  background: rgba(8,18,34,.72) !important;
  border: 1px solid rgba(0,209,255,.18) !important;
  border-radius: 14px !important;
}

@media (max-width: 768px) {
  .block-container { padding-left:.65rem !important; padding-right:.65rem !important; }
  .j-shell { border-radius:14px; padding:.7rem; }
  .j-brand h1 { font-size:.92rem; }
  .j-hero { padding:1.1rem 1rem; border-radius:16px; }
  .j-hero h2 { font-size:1.15rem; }
}
</style>
"""


def pt(mapa: dict[str, str], valor: str | None, padrao: str = "—") -> str:
    if not valor:
        return padrao
    return mapa.get(valor, valor)


def inject_hud() -> None:
    st.markdown(HUD_CSS, unsafe_allow_html=True)
    components.html(
        """
        <script>
        try {
          const d = window.parent.document;
          let link = d.querySelector('link[rel="manifest"]');
          if (!link) { link = d.createElement('link'); link.rel='manifest'; d.head.appendChild(link); }
          link.href = '/app/static/manifest.json';
          if ('serviceWorker' in window.parent.navigator) {
            window.parent.navigator.serviceWorker.register('/app/static/sw.js').catch(()=>{});
          }
        } catch (e) {}
        </script>
        """,
        height=0,
    )


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
        "last_voice_hash": "",
        "agent_speaking": False,
        "voice_status": "idle",
        "safety_ack": False,
        "last_manual_audio_hash": "",
        "nav": "bancada",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def top_menu() -> str:
    info = get_agent().provider_info()
    model = info.get("model") or ("demo" if info.get("mock") else "IA")
    st.markdown(
        f"""
        <div class="j-shell"><div class="j-row">
          <div class="j-brand">
            <div class="j-arc"></div>
            <div><h1>JARVIS</h1><p>de bancada · {model}</p></div>
          </div>
        </div></div>
        """,
        unsafe_allow_html=True,
    )
    labels = {
        "bancada": "🦾 Bancada",
        "casos": "📁 Casos",
        "falhas": "🧰 Falhas",
        "seguranca": "🛡️ Segurança",
        "sistemas": "🛰️ Sistemas",
    }
    cols = st.columns(len(labels))
    for col, (key, label) in zip(cols, labels.items()):
        with col:
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state.nav = key
                st.rerun()
    return st.session_state.nav


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
        st.warning(f"Voz indisponível: {exc}")
    finally:
        st.session_state.agent_speaking = False
        st.session_state.voice_status = "listening" if st.session_state.listen_on else "idle"


def render_probe_card(probe: dict | None) -> None:
    if not probe or not (probe.get("point_name") or probe.get("name")):
        return
    st.markdown('<div class="j-panel"><h3>Ordem de medição</h3>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"**Ponto:** {probe.get('point_name') or probe.get('name') or '—'}")
        st.write(f"**Ponta preta:** {probe.get('black_probe', '—')}")
        st.write(f"**Ponta vermelha:** {probe.get('red_probe', '—')}")
    with c2:
        st.write(f"**Modo:** {probe.get('meter_mode') or probe.get('mode') or '—'}")
        st.write(f"**Escala:** {probe.get('scale', '—')}")
        st.write(f"**Esperado:** {probe.get('expected_value') or probe.get('expected') or '—'}")
    if probe.get("visual_hint"):
        st.info(probe["visual_hint"])
    st.markdown("</div>", unsafe_allow_html=True)


def render_solution(solution: dict | None) -> None:
    if not solution:
        return
    st.markdown('<div class="j-panel"><h3>Modo solução</h3>', unsafe_allow_html=True)
    st.error("Valor fora do esperado")
    st.write(f"**Nó com falha:** {solution.get('failed_node', '—')}")
    st.write(f"**Trocar primeiro:** {solution.get('replace_first') or solution.get('replace_first') or '—'}")
    parts = solution.get("likely_parts") or []
    for p in parts:
        st.markdown(
            f"- `{p.get('ref', '?')}` ({p.get('type', '?')}): "
            f"{p.get('reason', '')} → **{p.get('action', '')}**"
        )
    if solution.get("how_to_confirm"):
        st.warning(solution["how_to_confirm"])
    st.markdown("</div>", unsafe_allow_html=True)


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
    with st.spinner("JARVIS sincronizando sensores…"):
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
            st.error(f"Falha de enlace com a IA: {exc}")
            st.stop()
    if result.get("awaiting_confirm"):
        st.info("Aguardando confirmação da medição.")
    if result.get("safety_brief"):
        st.caption(f"🛡️ {result['safety_brief']}")
    play_agent_voice(result.get("spoken_reply") or result.get("message") or "")
    st.rerun()


def consume_continuous_voice(key: str) -> str | None:
    if not st.session_state.listen_on:
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
    mapping = {
        "idle": ("Parado", ""),
        "listening": ("Ouvindo", "on"),
        "processing": ("Processando", "busy"),
        "speaking": ("Falando", "talk"),
    }
    text, cls = mapping.get(status, (status, ""))
    st.markdown(f'<span class="j-chip {cls}">● SISTEMA · {text}</span>', unsafe_allow_html=True)


def compact_controls() -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.session_state.voice_out = st.toggle("JARVIS fala", value=st.session_state.voice_out)
    with c2:
        st.session_state.listen_on = st.toggle("Escuta contínua", value=st.session_state.listen_on)
    with c3:
        st.session_state.safety_ack = st.toggle("Segurança OK", value=st.session_state.safety_ack)


def page_sistemas(ag: DiagnosticAgent) -> None:
    info = ag.provider_info()
    st.markdown(
        """
        <div class="j-hero">
          <h2>SISTEMAS ONLINE</h2>
          <p>Núcleo cognitivo, visão, voz e memória de falhas — status da armadura de bancada.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_status_chip()
    compact_controls()
    cols = st.columns(3)
    cols[0].metric("Provedor", (info.get("active") or "—").upper())
    cols[1].metric("Modelo", info.get("model") or "—")
    cols[2].metric("Modo", "DEMO" if info.get("mock") else "COMBATE")
    st.caption("No celular: Chrome → menu → Instalar app (PWA).")


def page_seguranca() -> None:
    st.markdown(
        """
        <div class="j-hero">
          <h2>PROTOCOLO DE SEGURANÇA</h2>
          <p>Antes de energizar a curiosidade, trave o protocolo. Bancada sem acidente.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"🛡️ {safety_brief('intake')}")
    for item in safety_checklist():
        st.markdown(
            f'<div class="j-panel"><h3>{item["title"]}</h3><p>{item["detail"]}</p></div>',
            unsafe_allow_html=True,
        )
    st.session_state.safety_ack = st.checkbox(
        "Li e aceito os avisos desta sessão",
        value=st.session_state.safety_ack,
    )


def page_falhas() -> None:
    st.markdown(
        """
        <div class="j-hero">
          <h2>ARQUIVO DE FALHAS</h2>
          <p>Memória coletiva de consertos — o que já caiu, o que já foi trocado.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    fails = list_failures(30)
    if not fails:
        st.info("Nenhuma falha resolvida salva ainda.")
        return
    for f in fails:
        st.markdown(
            f'<div class="j-panel"><h3>{f.get("board_model", "?")}</h3>'
            f'<p>{f.get("symptom", "")} → <b>{f.get("replaced_part", "?")}</b>'
            f' · nó {f.get("failed_node", "—")}</p></div>',
            unsafe_allow_html=True,
        )


def page_casos(ag: DiagnosticAgent) -> None:
    st.markdown(
        """
        <div class="j-hero">
          <h2>CASOS NA MEMÓRIA</h2>
          <p>Retome um diagnóstico ou inicie um novo enlace com a placa.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("＋ Novo caso na bancada", use_container_width=True):
        st.session_state.case_id = None
        st.session_state.nav = "bancada"
        st.rerun()
    cases = ag.list_cases()
    if not cases:
        st.caption("Nenhum caso ainda.")
        return
    for c in cases:
        cols = st.columns([4, 1])
        cols[0].markdown(
            f"**{c.get('board_model', '?')}** · {pt(STATUS_PT, c.get('status'))} · "
            f"{c.get('measurements', 0)} med. · `{c.get('case_id')}`"
        )
        if cols[1].button("Abrir", key=f"open_{c['case_id']}", use_container_width=True):
            st.session_state.case_id = c["case_id"]
            st.session_state.nav = "bancada"
            st.rerun()


def intake_form(ag: DiagnosticAgent) -> None:
    st.markdown(
        """
        <div class="j-hero">
          <h2>SISTEMAS À SUA DISPOSIÇÃO</h2>
          <p>Diga o modelo da placa e o sintoma. Eu vejo, pesquiso, guio o multímetro e falo o próximo passo —
          como se a bancada ganhasse um J.A.R.V.I.S.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_status_chip()
    compact_controls()
    st.caption(f"🛡️ {safety_brief('intake')}")
    if not st.session_state.safety_ack:
        st.warning("Ative **Segurança OK** antes de iniciar.")

    st.markdown('<div class="j-panel"><h3>Canal de voz</h3>', unsafe_allow_html=True)
    heard = consume_continuous_voice(key="listen_intake")
    if heard and st.session_state.safety_ack:
        st.success(f"Ouvi: “{heard}”")
        with st.spinner("Abrindo enlace do caso…"):
            try:
                intake = extract_intake_from_speech(heard)
                board = intake.get("board_model") or "placa"
                symptom = intake.get("symptom") or heard
                result = ag.start_case(board, symptom)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Falha: {exc}")
                st.stop()
        st.session_state.case_id = result["case"]["case_id"]
        play_agent_voice(result.get("spoken_reply") or result.get("message") or "")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

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
                        board = intake.get("board_model") or "placa"
                        symptom = intake.get("symptom") or transcript
                        result = ag.start_case(board, symptom)
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Falha: {exc}")
                        st.stop()
                st.session_state.case_id = result["case"]["case_id"]
                play_agent_voice(result.get("spoken_reply") or result.get("message") or "")
                st.rerun()

        with st.form("intake"):
            board = st.text_input("Modelo da placa")
            symptom = st.text_area("Sintoma", height=90)
            ok = st.form_submit_button("Iniciar diagnóstico", type="primary", use_container_width=True)
        if ok:
            if not st.session_state.safety_ack:
                st.error("Confirme o protocolo de segurança.")
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

    st.markdown(
        f"""
        <div class="j-hero">
          <h2>{case.get('board_model', 'PLACA')}</h2>
          <p>{case.get('symptom', '')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        f"Caso `{case['case_id']}` · **{pt(STATUS_PT, case.get('status'))}** · "
        f"**{pt(PHASE_PT, case.get('phase'))}** · "
        f"reavaliações: {case.get('strategy_revisions', 0)}"
    )
    render_status_chip()
    compact_controls()
    st.caption(f"🛡️ {safety_brief(case.get('phase'))}")

    if st.button("Encerrar / novo caso"):
        st.session_state.case_id = None
        st.session_state.last_image_bytes = None
        st.session_state.last_voice_hash = ""
        st.rerun()

    left, right = st.columns([1.35, 1], gap="large")
    with left:
        if st.session_state.last_tts_bytes:
            st.markdown('<div class="j-panel"><h3>Canal de áudio</h3>', unsafe_allow_html=True)
            st.audio(st.session_state.last_tts_bytes, format="audio/mp3")
            st.markdown("</div>", unsafe_allow_html=True)

        if case.get("pending_confirm"):
            st.warning("Confirme a medição: diga **confirmo** ou **não** se errou.")

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

        st.markdown('<div class="j-panel"><h3>Fale com o JARVIS</h3>', unsafe_allow_html=True)
        heard = consume_continuous_voice(key=f"listen_case_{case['case_id']}")
        if heard:
            st.success(f"Ouvi: “{heard}”")
            submit_user_turn(ag, case, heard)
        st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("Foto, esquema/PDF, áudio ou texto"):
            photo = st.file_uploader(
                "Foto da placa", type=["jpg", "jpeg", "png", "webp"], key=f"photo_{case['case_id']}"
            )
            doc = st.file_uploader(
                "Esquema / datasheet (PDF ou TXT)",
                type=["pdf", "txt", "md"],
                key=f"doc_{case['case_id']}",
            )
            if doc is not None and st.button("Anexar documento", use_container_width=True):
                with st.spinner("Lendo documento…"):
                    try:
                        result = ag.attach_document(case, doc.name, doc.getvalue())
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Documento: {exc}")
                        st.stop()
                preview = extract_text_from_bytes(doc.name, doc.getvalue())[:400]
                st.caption(f"Trecho: {preview}…")
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
                send = st.form_submit_button("Enviar", use_container_width=True)
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

        with st.expander("Marcar resolvido (banco de falhas)"):
            part = st.text_input("Peça que resolveu", placeholder="Ex: C905")
            notes = st.text_input("Nota (opcional)")
            if st.button("Salvar no arquivo de falhas", type="primary"):
                if not part.strip():
                    st.error("Informe a peça.")
                else:
                    ag.resolve_case(case, part.strip(), notes.strip())
                    st.success("Salvo.")
                    play_agent_voice(f"Caso resolvido. Salvei a troca de {part.strip()}.")
                    st.rerun()

    with right:
        st.markdown('<div class="j-panel"><h3>Memória do caso</h3>', unsafe_allow_html=True)
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
        st.markdown("</div>", unsafe_allow_html=True)

        suspects = case.get("suspect_components") or []
        if suspects:
            st.markdown("**Suspeitos:** " + ", ".join(f"`{s}`" for s in suspects))
        docs = case.get("documents") or []
        if docs:
            st.markdown("**Documentos:** " + ", ".join(f"`{d.get('filename')}`" for d in docs))

        if st.session_state.last_image_bytes:
            st.markdown('<div class="j-panel"><h3>Visão tática</h3>', unsafe_allow_html=True)
            coords = []
            if last_meta.get("probe"):
                coords = last_meta["probe"].get("coordinates") or []
            if not coords and case.get("probe_hints"):
                last_hint = case["probe_hints"][-1] or {}
                coords = last_hint.get("coordinates") or []
            if coords:
                annotated = annotate_board(st.session_state.last_image_bytes, coords)
                st.image(annotated, caption="Cruzes = pontas", use_container_width=True)
                zoom = zoom_around_probes(st.session_state.last_image_bytes, coords)
                if zoom is not None:
                    st.image(zoom, caption="Zoom do ponto", use_container_width=True)
            else:
                st.image(
                    st.session_state.last_image_bytes,
                    caption=st.session_state.last_image_name or "placa",
                    use_container_width=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

        sims = find_similar(str(case.get("board_model") or ""), str(case.get("symptom") or ""))
        if sims:
            st.markdown('<div class="j-panel"><h3>Parecidos no arquivo</h3>', unsafe_allow_html=True)
            for f in sims[:5]:
                st.caption(
                    f"{f.get('board_model')} · {f.get('symptom')} → **{f.get('replaced_part')}**"
                )
            st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    ensure_session()
    inject_hud()
    ag = get_agent()
    nav = top_menu()

    if nav == "seguranca":
        page_seguranca()
    elif nav == "falhas":
        page_falhas()
    elif nav == "casos":
        page_casos(ag)
    elif nav == "sistemas":
        page_sistemas(ag)
    else:
        if st.session_state.case_id:
            case_view(ag)
        else:
            intake_form(ag)


if __name__ == "__main__":
    main()
