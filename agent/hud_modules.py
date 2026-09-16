"""HUD modular estilo Homem de Ferro — módulos flutuantes, mídia e intenções."""

from __future__ import annotations

import re
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

MUSIC_STREAMS = [
    "https://ice4.somafm.com/defcon-128-mp3",
    "https://ice6.somafm.com/dronezone-128-mp3",
]

DEFAULT_VIDEO = "https://www.youtube.com/embed/8YQoa_RhGgU"

# Palco fixo: os módulos NUNCA saem do DOM — só ligam/desligam visibilidade.
STAGE_SLOTS: dict[str, dict[str, str]] = {
    "video": {"kind": "video", "side": "left", "title": "MÓDULO · VÍDEO", "id": "video"},
    "board": {"kind": "board", "side": "right", "title": "MÓDULO · PLACA", "id": "board"},
    "schematic": {"kind": "schematic", "side": "right", "title": "MÓDULO · ESQUEMA", "id": "schematic"},
}

from .intent_router import AMBIENT_OFF_RE as MUSIC_OFF_RE
from .intent_router import AMBIENT_ON_RE as MUSIC_ON_RE
from .intent_router import TECH_RE, classify_message

BOARD_RE = re.compile(
    r"\b("
    r"ver\s+a\s+placa|mostra(r)?\s+a\s+placa|foto\s+da\s+placa|"
    r"abre(r)?\s+a\s+(foto|imagem)|an[aá]lise\s+visual|"
    r"abre(r)?\s+o\s+m[oó]dulo\s+da\s+placa"
    r")\b",
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


def _esc(text: Any) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _blank_stage() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for kind, spec in STAGE_SLOTS.items():
        out[kind] = {**spec, "on": False, "payload": {}}
    return out


def _sync_visible_list() -> None:
    stage = st.session_state.get("stage") or {}
    st.session_state.hud_modules = [
        {
            "id": kind,
            "kind": kind,
            "title": slot.get("title") or STAGE_SLOTS[kind]["title"],
            "side": slot.get("side") or STAGE_SLOTS[kind]["side"],
            "payload": slot.get("payload") or {},
            "on": True,
        }
        for kind, slot in stage.items()
        if isinstance(slot, dict) and slot.get("on")
    ]


def ensure_hud_state() -> None:
    st.session_state.setdefault("music_on", False)
    st.session_state.setdefault("music_track", 0)
    stage = st.session_state.get("stage")
    if not isinstance(stage, dict) or not stage:
        st.session_state.stage = _blank_stage()
    else:
        merged = _blank_stage()
        for kind, spec in STAGE_SLOTS.items():
            prev = stage.get(kind) if isinstance(stage.get(kind), dict) else {}
            merged[kind] = {
                **spec,
                "on": bool(prev.get("on")),
                "payload": prev.get("payload") or {},
                "title": prev.get("title") or spec["title"],
                "side": spec["side"],
            }
        st.session_state.stage = merged
    _sync_visible_list()


def open_module(
    *,
    kind: str,
    title: str,
    side: str = "right",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Acende o slot no palco. Não cria nem destrói nós — só `on=True`."""
    ensure_hud_state()
    alias = {"image": "board", "pdf": "schematic"}.get(kind, kind)
    if alias not in STAGE_SLOTS:
        alias = "schematic"
    stage = dict(st.session_state.stage)
    slot = dict(stage[alias])
    slot["on"] = True
    slot["title"] = title or STAGE_SLOTS[alias]["title"]
    slot["side"] = STAGE_SLOTS[alias]["side"]
    slot["payload"] = payload or {}
    stage[alias] = slot
    st.session_state.stage = stage
    _sync_visible_list()
    return {
        "id": alias,
        "kind": alias,
        "title": slot["title"],
        "side": slot["side"],
        "payload": slot["payload"],
        "on": True,
    }


def close_modules(*, kind: str | None = None, side: str | None = None) -> None:
    """Apaga a luz do slot. O módulo continua no palco (`display:none`)."""
    ensure_hud_state()
    stage = dict(st.session_state.stage)
    close_all = kind in {None, "all", ""} and side is None
    kind_alias = {"image": "board", "pdf": "schematic", "all": None}.get(str(kind or ""), kind)
    for key, slot in stage.items():
        slot = dict(slot)
        if close_all:
            slot["on"] = False
        else:
            kind_ok = kind_alias is None or key == kind_alias
            side_ok = side is None or slot.get("side") == side
            if kind_ok and side_ok:
                slot["on"] = False
        stage[key] = slot
    st.session_state.stage = stage
    _sync_visible_list()


def detect_hud_intents(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    cls = classify_message(t)
    out: dict[str, Any] = {
        "music_on": cls.get("ambient_on"),
        "open": [],
        "close_all": False,
        "handled_ui_only": False,
        "reply": "",
        "spoken": "",
        "intent_class": cls.get("primary"),
        "is_technical": cls.get("is_technical"),
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
        low = t.lower()
        if re.search(r"\blo[\s\-]?fi\b|\blof[iy]\b", low):
            out["music_track"] = 1
        else:
            out["music_track"] = 0
        out["reply"] = "Música de foco no ar — waveform no rodapé."
        out["spoken"] = "Música iniciada, senhor."

    if BOARD_RE.search(t):
        out["open"].append("board")
    if SCHEMA_RE.search(t):
        out["open"].append("schematic")
    if VIDEO_RE.search(t):
        out["open"].append("video")

    # "abre o esquema da placa" → prioriza esquema (não abre slot de foto à toa)
    if "schematic" in out["open"] and "board" in out["open"]:
        if re.search(r"\besquema\b|\bschematic\b|\bdatasheet\b|\bmanual\b|\bdiagrama\b", t, re.I):
            if not re.search(
                r"\b(ver a placa|mostra a placa|foto da placa|abre a (foto|imagem)|an[aá]lise visual)\b",
                t,
                re.I,
            ):
                out["open"] = [k for k in out["open"] if k != "board"]

    technical = bool(cls.get("is_technical"))
    pure_ambient = out["music_on"] is not None and not out["open"] and not technical
    pure_ui = bool(out["open"]) and not technical

    if pure_ambient:
        out["handled_ui_only"] = True
    elif pure_ui:
        parts = []
        if "board" in out["open"]:
            parts.append("módulo da placa à direita")
        if "schematic" in out["open"]:
            parts.append("esquema técnico à direita")
        if "video" in out["open"]:
            parts.append("vídeo de referência à esquerda")
        base = (out["reply"] + " ").lstrip()
        out["reply"] = base + "Abrindo " + ", ".join(parts) + "."
        out["spoken"] = (out["spoken"] + " Módulos no ar.").strip() or "Módulos no ar."
        out["handled_ui_only"] = True

    return out


def apply_hud_intents(intents: dict[str, Any], case: dict[str, Any] | None = None) -> None:
    ensure_hud_state()
    if intents.get("close_all"):
        close_modules()
    if intents.get("music_on") is True:
        st.session_state.music_on = True
        if intents.get("music_track") is not None:
            st.session_state.music_track = int(intents["music_track"])
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
    from .event_bus import refresh_token

    ensure_hud_state()
    tok = refresh_token("music")
    active = bool(st.session_state.music_on)
    track = int(st.session_state.music_track) % len(MUSIC_STREAMS)
    src = MUSIC_STREAMS[track]
    status = "SYNTHWAVE · ON" if active else "STANDBY"
    dot = "#00f2ff" if active else "#445566"
    glow = "0 0 12px #00f2ff" if active else "none"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<meta name="jarvis-music-tok" content="{tok}"/>
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


def _photo_data_url() -> str:
    raw = st.session_state.get("last_image_bytes")
    if not raw:
        return ""
    import base64

    b64 = base64.b64encode(raw).decode("ascii")
    mime = "image/jpeg"
    name = str(st.session_state.get("last_image_name") or "").lower()
    if name.endswith(".png"):
        mime = "image/png"
    elif name.endswith(".webp"):
        mime = "image/webp"
    return f"data:{mime};base64,{b64}"


def _slot_class(on: bool) -> str:
    return "j-stage-slot is-on" if on else "j-stage-slot is-off"


def _stage_html(side: str) -> str:
    """Todos os slots do lado existem sempre. Visibilidade só via CSS."""
    ensure_hud_state()
    stage = st.session_state.stage
    kinds = [k for k, spec in STAGE_SLOTS.items() if spec["side"] == side]
    any_on = any(bool(stage[k].get("on")) for k in kinds)
    wait_cls = _slot_class(not any_on)
    blocks = [
        f'<div class="{wait_cls}" data-slot="wait">'
        "<p>Slot holográfico em espera.<br/>O palco não destrói módulos — só apaga a luz.</p>"
        "</div>"
    ]
    for kind in kinds:
        slot = stage[kind]
        on = bool(slot.get("on"))
        title = _esc(slot.get("title") or STAGE_SLOTS[kind]["title"])
        payload = slot.get("payload") or {}
        cls = _slot_class(on)
        inner = ""
        if kind == "video":
            url = str(payload.get("url") or DEFAULT_VIDEO)
            if not url.startswith("http"):
                url = DEFAULT_VIDEO
            url = _esc(url)
            label = _esc(payload.get("label") or "Referência")
            inner = (
                f'<div class="j-video"><iframe src="{url}" title="ref" '
                f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" '
                f'allowfullscreen loading="lazy"></iframe></div>'
                f'<p class="cap">{label}</p>'
            )
        elif kind == "board":
            src = _photo_data_url()
            name = _esc(payload.get("name") or "placa")
            img_disp = "block" if src else "none"
            empty_disp = "none" if src else "block"
            img = (
                f'<img class="j-stage-photo" src="{src}" alt="{name}" style="display:{img_disp}"/>'
                if src
                else '<img class="j-stage-photo" alt="placa" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==" style="display:none"/>'
            )
            inner = (
                f"{img}"
                f'<p class="j-module-empty" style="display:{empty_disp}">Sem foto ainda — envie a imagem no chat.</p>'
                f'<p class="cap">Análise visual — peça o próximo ponto no chat.</p>'
            )
        else:
            board = _esc(str(payload.get("board") or "equipamento")[:28])
            symptom = _esc(str(payload.get("symptom") or "—")[:40])
            inner = f"""
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
            """
        blocks.append(
            f'<div class="{cls}" data-slot="{kind}">'
            f'<div class="j-module-bar"><span>{title}</span><span class="j-module-id">{kind}</span></div>'
            f"{inner}</div>"
        )
    body = "".join(blocks)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>
html,body{{margin:0;background:transparent;color:#9ecfe0;font-family:Rajdhani,sans-serif;}}
.j-stage-slot{{display:none;padding:8px;}}
.j-stage-slot.is-on{{display:block;}}
.j-module-bar{{display:flex;justify-content:space-between;font-size:11px;letter-spacing:.12em;color:#00f2ff;margin-bottom:8px;text-transform:uppercase;}}
.j-module-id{{color:#ffaa00;opacity:.8;font-size:10px;}}
.j-module-empty{{border:1px dashed rgba(0,242,255,.35);padding:18px;text-align:center;color:#8fd;}}
.j-stage-photo{{width:100%;border-radius:10px;border:1px solid rgba(0,242,255,.3);}}
.j-video{{position:relative;width:100%;padding-top:56.25%;border-radius:10px;overflow:hidden;border:1px solid rgba(0,242,255,.3);}}
.j-video iframe{{position:absolute;inset:0;width:100%;height:100%;border:0;}}
.j-schematic svg{{width:100%;height:auto;display:block;}}
.cap{{font-size:12px;color:#8fb6d8;margin:.4rem 0 0;}}
</style></head><body>
<div class="j-stage" data-side="{_esc(side)}">{body}</div>
</body></html>"""


def render_zone_modules(side: str) -> None:
    """Palco sempre montado: mesmos iframes e mesmos botões a cada rerun."""
    ensure_hud_state()
    kinds = [k for k, spec in STAGE_SLOTS.items() if spec["side"] == side]
    label = "ZONA ANÁLISE · ESQ" if side == "left" else "ZONA ANÁLISE · DIR"
    st.markdown(
        f'<div class="j-zone"><div class="j-zone-title">{label} · PALCO</div></div>',
        unsafe_allow_html=True,
    )
    height = 320 if side == "left" else 460
    components.html(_stage_html(side), height=height, scrolling=False)
    labels = {"video": "Vídeo", "board": "Placa", "schematic": "Esquema"}
    cols = st.columns(max(1, len(kinds)))
    for col, kind in zip(cols, kinds):
        with col:
            if st.button(
                f"Recolher {labels.get(kind, kind)}",
                key=f"stage_hide_{kind}",
                use_container_width=True,
            ):
                close_modules(kind=kind)
                st.rerun()
