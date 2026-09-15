#!/usr/bin/env python3
"""Integra HUD modular no app.py."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
HUD = ROOT / "agent" / "hud_modules.py"

# Alinhar chaves de imagem com o app
ht = HUD.read_text()
ht = ht.replace("last_image_bytes", "last_image_bytes").replace("last_image_name", "last_image_name")
# Forçar last_image_* (ensure_session do app)
for a, b in [
    ("last_image_bytes", "last_image_bytes"),
    ("last_image_name", "last_image_name"),
]:
    ht = ht.replace(a, b)
# Se ainda houver last_image, converter
ht = ht.replace("last_image_bytes", "last_image_bytes")
ht = re.sub(r"last_image_(bytes|name)", r"last_image_\1", ht)
HUD.write_text(ht)

src = APP.read_text()

# --- imports ---
if "from agent.hud_modules import" not in src:
    for anchor in ("from agent.voice import", "from agent.vision import", "from agent.safety import"):
        if anchor in src:
            src = src.replace(
                anchor,
                "from agent.hud_modules import (\n"
                "    apply_hud_intents,\n"
                "    detect_hud_intents,\n"
                "    ensure_hud_state,\n"
                "    render_music_dock,\n"
                "    render_zone_modules,\n"
                ")\n"
                + anchor,
                1,
            )
            break
    else:
        raise SystemExit("import anchor not found")

EXTRA_CSS = """
/* ===== DASHBOARD MODULAR ===== */
.j-zone { min-height: 200px; margin-bottom: .7rem; }
.j-zone-title {
  font-family: 'Orbitron', sans-serif; font-size: .62rem; letter-spacing: .16em;
  color: var(--orange); margin-bottom: .4rem; text-shadow: 0 0 10px rgba(255,170,0,.35);
}
.j-module {
  border: 1px solid rgba(0,242,255,.35); border-radius: 14px;
  background: rgba(0,242,255,.05); backdrop-filter: blur(12px);
  box-shadow: 0 0 24px rgba(0,242,255,.18), inset 0 0 28px rgba(0,242,255,.04);
  padding: .75rem .85rem; margin-bottom: .65rem; transform-origin: center;
}
.j-module-empty {
  border-style: dashed; opacity: .75; min-height: 110px;
  display:flex; align-items:center; justify-content:center; text-align:center;
  color:#8fd; font-size:.9rem;
}
.j-module-bar {
  display:flex; justify-content:space-between; align-items:center;
  font-family:'Orbitron',sans-serif; font-size:.68rem; letter-spacing:.12em;
  color: var(--cyan); margin-bottom:.55rem; text-shadow:0 0 10px rgba(0,242,255,.4);
}
.j-module-id { color: var(--orange); opacity:.8; font-size:.58rem; }
.pop-in { animation: popIn .55s cubic-bezier(.16,1,.3,1) both; }
@keyframes popIn {
  0% { opacity:0; transform:scale(.55) translateY(12px); filter:blur(4px); }
  100% { opacity:1; transform:none; filter:none; }
}
.j-schematic svg { width:100%; height:auto; display:block; }
.j-schematic p { color:#9ecfe0; font-size:.85rem; margin:.4rem 0 0; }
.j-video {
  position:relative; width:100%; padding-top:56.25%; border-radius:10px; overflow:hidden;
  border:1px solid rgba(0,242,255,.3); box-shadow:0 0 18px rgba(0,242,255,.2);
}
.j-video iframe { position:absolute; inset:0; width:100%; height:100%; border:0; }
.hud-particles {
  position:absolute; inset:0; opacity:.55; pointer-events:none;
  background-image:
    radial-gradient(1px 1px at 20% 30%, rgba(0,242,255,.55), transparent),
    radial-gradient(1px 1px at 70% 60%, rgba(255,170,0,.45), transparent),
    radial-gradient(1.5px 1.5px at 40% 80%, rgba(0,242,255,.35), transparent),
    radial-gradient(1px 1px at 85% 20%, rgba(0,242,255,.5), transparent);
  animation: particleDrift 18s linear infinite;
}
@keyframes particleDrift {
  from { transform:translateY(0); opacity:.4; }
  50% { opacity:.7; }
  to { transform:translateY(-24px); opacity:.4; }
}
.hud-noise {
  position:absolute; inset:0; pointer-events:none; opacity:.35;
  background: repeating-linear-gradient(
    0deg, transparent, transparent 2px, rgba(0,242,255,.03) 2px, rgba(0,242,255,.03) 4px
  );
  animation: noiseShift 6s linear infinite;
}
@keyframes noiseShift { from { transform:translateY(0);} to { transform:translateY(4px);} }
.j-arc.busy {
  box-shadow: 0 0 28px rgba(255,170,0,.95), inset 0 0 14px rgba(255,255,255,.55);
  animation: arc 0.7s ease-in-out infinite;
}
.j-arc.busy::after { border-color: rgba(255,170,0,.75); animation: spin 2.2s linear infinite; }
.j-cascade { display:flex; flex-wrap:wrap; gap:8px; margin:.35rem 0 .85rem; }
.j-cascade span {
  font-family:'Orbitron',sans-serif; font-size:.58rem; letter-spacing:.1em;
  padding:.28rem .55rem; border-radius:8px; border:1px solid rgba(0,242,255,.28);
  background:rgba(0,242,255,.05); color:#9ef; animation: cascadeIn .35s ease both;
}
.j-cascade span:nth-child(2){animation-delay:.05s}
.j-cascade span:nth-child(3){animation-delay:.1s}
.j-cascade span:nth-child(4){animation-delay:.15s}
@keyframes cascadeIn { from{opacity:0;transform:translateY(-6px);} to{opacity:1;transform:none;} }
.j-music-wrap { position:relative; z-index:2; margin:.5rem 0 .25rem; }
.j-cmd-title {
  font-family:'Orbitron',sans-serif; font-size:.65rem; letter-spacing:.16em;
  color: var(--cyan); margin:.2rem 0 .5rem;
}
"""

if ".j-zone {" not in src:
    src = src.replace("</style>\n\"\"\"", EXTRA_CSS + "</style>\n\"\"\"", 1)

if "hud-particles" not in src:
    src = src.replace(
        '<div class="hud-scanline"></div>',
        '<div class="hud-scanline"></div>\n'
        '          <div class="hud-noise"></div>\n'
        '          <div class="hud-particles"></div>',
        1,
    )

if '"hud_modules"' not in src:
    src = src.replace(
        '"_pending_voice": None,',
        '"_pending_voice": None,\n'
        '        "hud_modules": [],\n'
        '        "music_on": False,\n'
        '        "music_track": 0,',
        1,
    )

# Cascata no top_menu
needle = (
    "    if chosen in keys:\n"
    "        st.session_state.nav = chosen\n"
    "    return st.session_state.nav"
)
if needle in src and "j-cascade" not in src[src.find("def top_menu") : src.find("def top_menu") + 5000]:
    src = src.replace(
        needle,
        "    if chosen in keys:\n"
        "        st.session_state.nav = chosen\n"
        "    cascade = {\n"
        '        "bancada": ["CHAT", "MÓDULOS", "MIC", "MÍDIA"],\n'
        '        "casos": ["ABERTOS", "RESOLVIDOS", "RETOMAR"],\n'
        '        "falhas": ["BANCO", "PARECIDOS", "APRENDER"],\n'
        '        "seguranca": ["CHECKLIST", "ALERTAS"],\n'
        '        "sistemas": ["CPU", "RAM", "ENLACE", "GCS"],\n'
        '        "config": ["PERFIL", "VOZ", "MODELO"],\n'
        "    }.get(st.session_state.nav, [])\n"
        "    if cascade:\n"
        '        chips = "".join(f"<span>{c}</span>" for c in cascade)\n'
        '        st.markdown(f\'<div class="j-cascade">{chips}</div>\', unsafe_allow_html=True)\n'
        "    return st.session_state.nav",
        1,
    )

# Arc busy class — injetar variável perto do markdown do shell
if 'arc_cls = "busy"' not in src:
    # inserir antes do st.markdown do shell no top_menu
    src = src.replace(
        '    st.markdown(\n        f"""\n        <div class="j-shell">',
        '    arc_cls = "busy" if st.session_state.get("voice_status") == "processing" else ""\n'
        "    st.markdown(\n"
        '        f"""\n'
        '        <div class="j-shell">',
        1,
    )
    src = src.replace('<div class="j-arc"></div>', '<div class="j-arc {arc_cls}"></div>', 1)

# submit_user_turn interceptor
speaking = "agent_speaking" if "agent_speaking" in src else "agent_speaking"
voice_fn = "play_agent_voice" if "def play_agent_voice" in src else "play_agent_voice"
if "detect_hud_intents(" not in src:
    new_head = f'''def submit_user_turn(
    ag: DiagnosticAgent,
    case: dict,
    text: str,
    image_bytes: bytes | None = None,
    image_name: str | None = None,
    image_mime: str = "image/jpeg",
) -> None:
    st.session_state.case_id = case["case_id"]
    if image_bytes:
        st.session_state.last_image_bytes = image_bytes
        st.session_state.last_image_name = image_name or "placa.jpg"

    # HUD modular: música / módulos flutuantes sem trocar de página.
    ensure_hud_state()
    intents = detect_hud_intents(text)
    if intents.get("music_on") is not None or intents.get("open") or intents.get("close_all"):
        apply_hud_intents(intents, case)
    if intents.get("handled_ui_only") and image_bytes is None:
        reply = intents.get("reply") or "HUD atualizado."
        spoken = intents.get("spoken") or reply
        try:
            ag.memory.add_message(case, "user", text)
            ag.memory.add_message(
                case,
                "assistant",
                reply,
                meta={{"phase": "chat", "mode": "chat", "spoken_reply": spoken, "hud": True}},
            )
        except Exception:
            pass
        {voice_fn}(spoken)
        st.session_state.voice_status = "listening" if st.session_state.listen_on else "idle"
        st.session_state.{speaking} = False
        st.rerun()
        return

    # Pausa o microfone ANTES do spinner — evita erro React removeChild
    # e impede nova fala enquanto a IA pensa.
    st.session_state.voice_status = "processing"
    st.session_state.{speaking} = True
    with st.spinner("JARVIS sincronizando…"):
'''
    src2, n = re.subn(
        r"def submit_user_turn\([\s\S]*?with st\.spinner\([^\n]+\):\n",
        new_head,
        src,
        count=1,
    )
    if n != 1:
        raise SystemExit(f"submit_user_turn replace failed n={n}")
    src = src2

# Layout 3 colunas
if "render_zone_modules(\"left\")" not in src and "render_zone_modules('left')" not in src:
    m = re.search(r"    left, right = st\.columns\([^\n]+\)\n    with left:\n", src)
    if not m:
        raise SystemExit("chat columns not found")
    src = (
        src[: m.start()]
        + "    st.markdown(\n"
        + "        '<div class=\"j-cmd-title\">ZONA DE COMANDO · ANÁLISE · TELEMETRIA</div>',\n"
        + "        unsafe_allow_html=True,\n"
        + "    )\n"
        + "    left, center, right = st.columns([1.05, 1.45, 1.05], gap=\"medium\")\n"
        + "    with left:\n"
        + "        render_zone_modules(\"left\")\n"
        + "    with center:\n"
        + "        st.markdown(\n"
        + "            '<div class=\"j-cmd-title\">ZONA DE COMANDO · CHAT</div>',\n"
        + "            unsafe_allow_html=True,\n"
        + "        )\n"
        + src[m.end() :]
    )
    # prepend zone modules on right before telemetry panel
    if "render_zone_modules(\"right\")" not in src:
        src = src.replace(
            "    with right:\n        # Painel holográfico de telemetria",
            "    with right:\n"
            "        render_zone_modules(\"right\")\n"
            "        # Painel holográfico de telemetria",
            1,
        )

# Music dock no fim de open_chat_view
if "render_music_dock()" not in src:
    m = re.search(r"\ndef (mount_listen_slot|render_audio_slot|consume_continuous_voice)\(", src)
    if not m:
        raise SystemExit("anchor after open_chat_view not found")
    src = (
        src[: m.start()]
        + "\n    st.markdown('<div class=\"j-music-wrap\">', unsafe_allow_html=True)\n"
        + "    render_music_dock()\n"
        + '    st.markdown("</div>", unsafe_allow_html=True)\n'
        + src[m.start() :]
    )

src = src.replace(
    "HUD holográfico na bancada — parceiro, não robô. Mande foto quando quiser.",
    "Dashboard modular estilo Homem de Ferro — módulos flutuam, chat fica. Mande foto quando quiser.",
)
src = src.replace(
    "Atalhos: <b>anota:</b> … · <b>próxima etapa</b> · retomar “placa de ontem”.</p>",
    "Atalhos: <b>música de foco</b> · <b>abre o esquema</b> · <b>ver a placa</b> · "
    "<b>abre o vídeo</b> · <b>anota:</b> …</p>",
)

APP.write_text(src)
ast.parse(src)
print("OK app.py")
for s in [
    "detect_hud_intents",
    "render_zone_modules",
    "render_music_dock",
    "left, center, right",
    "hud-particles",
    "j-zone",
]:
    print(f"  {s}: {s in src}")

ast.parse(HUD.read_text())
print("OK hud_modules.py")
print("image keys", set(re.findall(r"last_\w+_(?:bytes|name)", HUD.read_text())))
