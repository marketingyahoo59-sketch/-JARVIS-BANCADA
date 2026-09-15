"""HUD modular estilo Homem de Ferro — módulos flutuantes, mídia e intenções."""

from __future__ import annotations

import re
import uuid
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

MUSIC_STREAMS = [
    "https://ice4.somafm.com/defcon-128-mp3",
    "https://ice6.somafm.com/dronezone-128-mp3",
]

DEFAULT_VIDEO = "https://www.youtube.com/embed/8YQoa_RhGgU"

MUSIC_ON_RE = re.compile(
    r"\b(m[uú]sica|synthwave|lo[\s\-]?fi|lof[iy]|foco|trabalhar|bora trabalhar|ambiente)\b",
    re.I,
)
MUSIC_OFF_RE = re.compile(
    r"\b(para(r)?\s+(a\s+)?m[uú]sica|sil[eê]ncio|mute|sem m[uú]sica|desliga(r)?\s+(a\s+)?m[uú]sica)\b",
    re.I,
)
BOARD_RE = re.compile(
    r"\b(placa|foto da placa|ver a placa|abre a (foto|imagem)|mostra a placa|an[aá]lise visual)\b",
    re.I,
)
SCHEMA_RE = re.compile(
    r"\b(esquema|schematic|datasheet|manual|diagrama|abre o esquema)\b",
    re.I,
)
VIDEO_RE = re.compile(
    r"\b(v[ií]deo|tutorial|como trocar|capacitor|abre o v[ií]deo)\b",
    re.I,
)
CLOSE_RE = re.compile(
    r"\b("
    r"fecha(r)?\s+(o[s]?\s+|a[s]?\s+)?(m[oó]dulos?|v[ií]deos?|esquemas?|placas?|janelas?)|"
    r"limpa(r)?\s+(a\s+)?tela|"
    r"fecha\s+tudo"
    r")\b",
    re.I,
)
TECH_RE = re.compile(
    r"\b(medir|tens[aã]o|ohm|defeito|n[aã]o liga|diagn[oó]stico|consertar)\b",
    re.I,
)


def ensure_hud_state() -> None:
    st.session_state.setdefault("hud_modules", [])
    st.session_state.setdefault("music_on", False)
    st.session_state.setdefault("music_track", 0)


def open_module(
    *,
    kind: str,
    title: str,
    side: str = "right",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_hud_state()
    mods = [
        m
        for m in list(st.session_state.hud_modules)
        if not (m.get("kind") == kind and m.get("side") == side)
    ]
    mod = {
        "id": uuid.uuid4().hex[:8],
        "kind": kind,
        "title": title,
        "side": side,
        "payload": payload or {},
    }
    mods.append(mod)
    st.session_state.hud_modules = mods
    return mod


def close_modules(*, kind: str | None = None, side: str | None = None) -> None:
    ensure_hud_state()
    if kind is None and side is None:
        st.session_state.hud_modules = []
        return
    st.session_state.hud_modules = [
        m
        for m in list(st.session_state.hud_modules)
        if not (
            (kind is None or m.get("kind") == kind)
            and (side is None or m.get("side") == side)
        )
    ]


def detect_hud_intents(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    out: dict[str, Any] = {
        "music_on": None,
        "open": [],
        "close_all": False,
        "handled_ui_only": False,
        "reply": "",
        "spoken": "",
    }
    if not t:
        return out

    if CLOSE_RE.search(t) and not any(
        (BOARD_RE.search(t), SCHEMA_RE.search(t), VIDEO_RE.search(t), MUSIC_ON_RE.search(t))
    ):
        out["close_all"] = True
        out["reply"] = "Módulos recolhidos. Chat central permanece ativo."
        out["spoken"] = "Módulos fechados."
        out["handled_ui_only"] = True
        return out

    if MUSIC_OFF_RE.search(t):
        out["music_on"] = False
        out["reply"] = "Áudio de ambiente desligado."
        out["spoken"] = "Música desligada."
    elif MUSIC_ON_RE.search(t):
        out["music_on"] = True
        out["reply"] = (
            "Música de foco iniciada — waveform neon no rodapé. "
            "Peça esquema, placa ou vídeo sem sair do chat."
        )
        out["spoken"] = "Música iniciada."

    if BOARD_RE.search(t):
        out["open"].append("board")
    if SCHEMA_RE.search(t):
        out["open"].append("schematic")
    if VIDEO_RE.search(t):
        out["open"].append("video")

    if out["music_on"] is not None and not out["open"] and not TECH_RE.search(t):
        out["handled_ui_only"] = True
    elif out["open"] and not TECH_RE.search(t):
        parts = []
        if "board" in out["open"]:
            parts.append("módulo da placa à direita")
        if "schematic" in out["open"]:
            parts.append("esquema técnico à direita")
        if "video" in out["open"]:
            parts.append("vídeo de referência à esquerda")
        base = (out["reply"] + " ").lstrip()
        out["reply"] = base + "Abrindo " + ", ".join(parts) + ". Chat continua no centro."
        out["spoken"] = (out["spoken"] + " Módulos no ar.").strip() or "Módulos no ar."
        out["handled_ui_only"] = True

    return out


def apply_hud_intents(intents: dict[str, Any], case: dict[str, Any] | None = None) -> None:
    ensure_hud_state()
    if intents.get("close_all"):
        close_modules()
    if intents.get("music_on") is True:
        st.session_state.music_on = True
    elif intents.get("music_on") is False:
        st.session_state.music_on = False

    case = case or {}
    for kind in intents.get("open") or []:
        if kind == "board":
            open_module(
                kind="board",
                title="MÓDULO · PLACA",
                side="right",
                payload={
                    "has_image": bool(st.session_state.get("last_image_bytes")),
                    "name": st.session_state.get("last_image_name") or "placa",
                    "board": case.get("board_model") or "",
                },
            )
        elif kind == "schematic":
            open_module(
                kind="schematic",
                title="MÓDULO · ESQUEMA",
                side="right",
                payload={
                    "board": case.get("board_model") or "equipamento",
                    "symptom": case.get("symptom") or "",
                },
            )
        elif kind == "video":
            open_module(
                kind="video",
                title="MÓDULO · VÍDEO",
                side="left",
                payload={"url": DEFAULT_VIDEO, "label": "Tutorial de referência"},
            )


def render_music_dock() -> None:
    """Player + waveform sempre montado (iframe isolado = sem removeChild no React pai)."""
    ensure_hud_state()
    active = bool(st.session_state.music_on)
    track = int(st.session_state.music_track) % len(MUSIC_STREAMS)
    src = MUSIC_STREAMS[track]
    status = "SYNTHWAVE · ON" if active else "STANDBY"
    dot = "#00f2ff" if active else "#445566"
    glow = "0 0 12px #00f2ff" if active else "none"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>
html,body{{margin:0;background:transparent;overflow:hidden;font-family:Rajdhani,sans-serif;}}
.dock{{display:flex;align-items:center;gap:12px;height:70px;padding:8px 14px;
background:linear-gradient(90deg,rgba(0,0,0,.55),rgba(0,242,255,.08),rgba(0,0,0,.55));
border:1px solid rgba(0,242,255,.35);border-radius:12px;
box-shadow:0 0 20px rgba(0,242,255,.2), inset 0 0 24px rgba(0,242,255,.05);}}
.lbl{{color:#ffaa00;font-size:10px;letter-spacing:.14em;min-width:90px;}}
.lbl b{{display:block;color:#00f2ff;font-size:11px;margin-top:2px;}}
canvas{{flex:1;height:44px;width:100%;}}
.dot{{width:8px;height:8px;border-radius:50%;background:{dot};box-shadow:{glow};}}
</style></head><body>
<div class="dock">
  <div class="dot"></div>
  <div class="lbl">AMBIENTE<audio id="a" crossorigin="anonymous" preload="none" src="{src}"></audio>
  <b>{status}</b></div>
  <canvas id="c"></canvas>
</div>
<script>
const active = {"true" if active else "false"};
const audio = document.getElementById('a');
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
function resize(){{
  canvas.width = Math.max(100, canvas.clientWidth) * devicePixelRatio;
  canvas.height = Math.max(40, canvas.clientHeight) * devicePixelRatio;
}}
resize(); window.addEventListener('resize', resize);
let analyser=null, data=null;
function drawIdle(pulse){{
  const w=canvas.width,h=canvas.height; ctx.clearRect(0,0,w,h);
  const n=36, t=Date.now()/450;
  for(let i=0;i<n;i++){{
    const x=(i+0.5)*w/n;
    const amp = pulse ? (0.22+0.18*Math.sin(t+i*0.35)) : 0.1;
    const bh=amp*h;
    ctx.fillStyle='rgba(0,242,255,0.55)';
    ctx.fillRect(x-2,(h-bh)/2,3,bh);
  }}
  if(!analyser) requestAnimationFrame(()=>drawIdle(!!active));
}}
function tick(){{
  if(!analyser){{ drawIdle(true); return; }}
  analyser.getByteFrequencyData(data);
  const w=canvas.width,h=canvas.height; ctx.clearRect(0,0,w,h);
  const n=data.length, bar=w/n;
  for(let i=0;i<n;i++){{
    const v=data[i]/255, bh=Math.max(2,v*h);
    const g=ctx.createLinearGradient(0,0,0,h);
    g.addColorStop(0,'#ffaa00'); g.addColorStop(1,'#00f2ff');
    ctx.fillStyle=g; ctx.fillRect(i*bar,(h-bh)/2,Math.max(2,bar-1),bh);
  }}
  requestAnimationFrame(tick);
}}
async function boot(){{
  if(!active){{ drawIdle(false); return; }}
  try {{
    const ac = new (window.AudioContext||window.webkitAudioContext)();
    const srcNode = ac.createMediaElementSource(audio);
    analyser = ac.createAnalyser(); analyser.fftSize = 128;
    srcNode.connect(analyser); analyser.connect(ac.destination);
    data = new Uint8Array(analyser.frequencyBinCount);
    await audio.play();
    tick();
  }} catch(e) {{
    drawIdle(true);
    try {{ await audio.play(); }} catch(_e) {{}}
  }}
}}
boot();
</script></body></html>"""
    components.html(html, height=78, scrolling=False)


def render_module_card(mod: dict[str, Any]) -> None:
    from .event_bus import refresh_token

    kind = mod.get("kind")
    title = mod.get("title") or "MÓDULO"
    payload = mod.get("payload") or {}
    side = str(mod.get("side") or "right")
    tok = refresh_token(side)
    st.markdown(
        f'<div class="j-module pop-in"><div class="j-module-bar"><span>{title}</span>'
        f'<span class="j-module-id">{mod.get("id", "")}</span></div>',
        unsafe_allow_html=True,
    )
    if kind == "board":
        if st.session_state.get("last_image_bytes"):
            st.image(
                st.session_state.last_image_bytes,
                caption=payload.get("name") or "placa",
                use_container_width=True,
            )
            st.caption("Módulo de análise visual — peça o próximo ponto no chat.")
        else:
            st.info("Sem foto ainda — envie a imagem da placa no chat e peça de novo.")
    elif kind == "schematic":
        board = str(payload.get("board") or "equipamento")[:28]
        symptom = str(payload.get("symptom") or "—")[:40]
        st.markdown(
            f"""
            <div class="j-schematic">
              <svg viewBox="0 0 320 180" xmlns="http://www.w3.org/2000/svg">
                <rect x="8" y="8" width="304" height="164" fill="none" stroke="#00f2ff" stroke-width="1.5" opacity=".7"/>
                <text x="16" y="28" fill="#ffaa00" font-size="11" font-family="monospace">SCH · {board}</text>
                <rect x="40" y="50" width="70" height="40" fill="none" stroke="#00f2ff"/>
                <text x="50" y="74" fill="#00f2ff" font-size="10">SMPS</text>
                <rect x="130" y="55" width="50" height="30" fill="none" stroke="#ffaa00"/>
                <text x="138" y="74" fill="#ffaa00" font-size="10">5VSB</text>
                <circle cx="220" cy="70" r="14" fill="none" stroke="#00f2ff"/>
                <text x="212" y="74" fill="#00f2ff" font-size="9">IC</text>
                <line x1="110" y1="70" x2="130" y2="70" stroke="#00f2ff"/>
                <line x1="180" y1="70" x2="206" y2="70" stroke="#00f2ff"/>
                <text x="16" y="160" fill="#88ffdd" font-size="10">Sintoma: {symptom}</text>
              </svg>
              <p>Mapa esquemático de trabalho — anexe o PDF real no chat se tiver.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif kind == "video":
        url = payload.get("url") or DEFAULT_VIDEO
        st.markdown(
            f'<div class="j-video"><iframe src="{url}" title="ref" '
            f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" '
            f'allowfullscreen loading="lazy"></iframe></div>',
            unsafe_allow_html=True,
        )
        st.caption(payload.get("label") or "Referência")
    else:
        st.caption(str(payload))

    if st.button(
        "Fechar módulo",
        key=f"close_mod_{mod.get('id')}_r{tok}",
        use_container_width=True,
    ):
        close_modules(kind=kind, side=mod.get("side"))
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_zone_modules(side: str) -> None:
    """Zona sempre montada (vazia ou com módulos) — DOM estável."""
    ensure_hud_state()
    mods = [m for m in list(st.session_state.hud_modules) if m.get("side") == side]
    label = "ZONA ANÁLISE · ESQ" if side == "left" else "ZONA ANÁLISE · DIR"
    st.markdown(
        f'<div class="j-zone"><div class="j-zone-title">{label}</div>',
        unsafe_allow_html=True,
    )
    if not mods:
        st.markdown(
            '<div class="j-module j-module-empty pop-in">'
            "<p>Slot holográfico em espera.<br/>"
            "Diga <b>abre o esquema</b>, <b>ver a placa</b> ou <b>abre o vídeo</b>.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        for mod in mods:
            render_module_card(mod)
    st.markdown("</div>", unsafe_allow_html=True)
