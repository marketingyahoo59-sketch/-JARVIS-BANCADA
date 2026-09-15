"""
JARVIS de Bancada — HUD estilo Homem de Ferro.
Diagnóstico eletrônico com voz, visão, pesquisa e memória.
"""

from __future__ import annotations

import base64
import hashlib
import random
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

from agent.diagnostic import DiagnosticAgent
from agent.docs import extract_text_from_bytes
from agent.failures import find_similar, list_failures
from agent.memory import CaseMemory
from agent.profile import address_user, list_presets, load_profile, save_profile
from agent.safety import safety_brief, safety_checklist
from agent.system_hud import host_metrics, load_remote_pc_sensor
from agent.vision import annotate_board, zoom_around_probes
from agent.hud_modules import (
    apply_hud_intents,
    detect_hud_intents,
    ensure_hud_state,
    render_music_dock,
    render_zone_modules,
)
from agent.voice import extract_intake_from_speech, speak_text, transcribe_audio

st.set_page_config(
    page_title="JARVIS de Bancada",
    page_icon="🦾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from agent.paths import CASES_DIR as DATA_DIR, UPLOADS_DIR as UPLOAD_DIR, ensure_data_dirs
from agent.gcs_sync import gcs_enabled, pull_from_gcs, push_path, status_line

ensure_data_dirs()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
# Cloud Run: restaura SQLite/fotos do bucket GCS no boot do processo
_GCS_BOOT = pull_from_gcs() if gcs_enabled() else ""

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

# WAV silencioso — slot de áudio SEMPRE montado (evita removeChild ao criar/destruir st.audio).
_SILENT_WAV = base64.b64decode("UklGRkQDAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YSADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==")


HUD_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;800&family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&display=swap');

:root {
  --cyan: #00f2ff;
  --cyan-dim: rgba(0,242,255,.35);
  --orange: #ffaa00;
  --orange-dim: rgba(255,170,0,.35);
  --glass: rgba(0, 242, 255, 0.05);
  --ink: #000000;
  --text: #c8f7ff;
}

html, body, [class*="css"] {
  font-family: 'Rajdhani', sans-serif !important;
}

.stApp {
  background:
    radial-gradient(ellipse 80% 50% at 50% -10%, rgba(0,242,255,.12), transparent 55%),
    radial-gradient(ellipse 40% 40% at 100% 100%, rgba(255,170,0,.08), transparent 50%),
    radial-gradient(circle at 20% 80%, rgba(0,80,100,.25), transparent 40%),
    linear-gradient(180deg, #000 0%, #001014 40%, #000 100%) !important;
  color: var(--text);
  overflow-x: hidden;
}

header[data-testid="stHeader"] {
  background: transparent !important;
  pointer-events: none !important;
}
#MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; height: 0; }

/* ===== OVERLAY HUD (não captura cliques) ===== */
.hud-overlay {
  position: fixed; inset: 0; z-index: 0;
  pointer-events: none !important;
  overflow: hidden;
}
.hud-overlay * { pointer-events: none !important; }

.hud-vignette {
  position: absolute; inset: 0;
  background:
    linear-gradient(90deg, rgba(0,0,0,.55), transparent 12%, transparent 88%, rgba(0,0,0,.55)),
    linear-gradient(0deg, rgba(0,0,0,.45), transparent 18%, transparent 85%, rgba(0,0,0,.35));
}

.hud-grid {
  position: absolute; inset: 0; opacity: .22;
  background-image:
    linear-gradient(rgba(0,242,255,.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,242,255,.07) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 75%);
  animation: gridDrift 28s linear infinite;
}
@keyframes gridDrift {
  from { background-position: 0 0, 0 0; }
  to { background-position: 48px 48px, 48px 48px; }
}

.hud-scanline {
  position: absolute; left: 0; width: 100%; height: 2px;
  background: linear-gradient(90deg, transparent, var(--cyan), var(--orange), var(--cyan), transparent);
  box-shadow: 0 0 18px var(--cyan), 0 0 40px rgba(0,242,255,.35);
  animation: boardScan 4.2s linear infinite;
  opacity: .75;
}
@keyframes boardScan {
  0% { top: -2%; opacity: 0; }
  8% { opacity: .85; }
  92% { opacity: .85; }
  100% { top: 102%; opacity: 0; }
}

.hud-ring-stack {
  position: absolute; width: 160px; height: 160px;
}
.hud-ring-stack.tl { top: 70px; left: 12px; }
.hud-ring-stack.br { bottom: 40px; right: 16px; }
.hud-ring {
  position: absolute; inset: 0; border-radius: 50%;
  border: 1px dashed rgba(0,242,255,.45);
  box-shadow: 0 0 12px rgba(0,242,255,.2), inset 0 0 18px rgba(0,242,255,.08);
}
.hud-ring.r2 { inset: 14px; border-style: solid; border-color: rgba(255,170,0,.35);
  animation: spinRev 14s linear infinite; }
.hud-ring.r3 { inset: 28px; border: 2px dotted rgba(0,242,255,.55);
  animation: spin 7s linear infinite; }
.hud-ring.r1 { animation: spin 18s linear infinite; }
.hud-ring-core {
  position: absolute; inset: 48px; border-radius: 50%;
  background: radial-gradient(circle at 40% 35%, #fff 0 6%, #00f2ff 12% 40%, transparent 70%);
  box-shadow: 0 0 30px rgba(0,242,255,.7);
  animation: corePulse 2.4s ease-in-out infinite;
}
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes spinRev { from { transform: rotate(360deg); } to { transform: rotate(0deg); } }
@keyframes corePulse {
  0%,100% { filter: brightness(1); transform: scale(1); }
  50% { filter: brightness(1.35); transform: scale(1.06); }
}

.hud-corner {
  position: absolute; width: 28px; height: 28px;
  border: 2px solid var(--cyan); opacity: .7;
  box-shadow: 0 0 10px rgba(0,242,255,.4);
}
.hud-corner.tl { top: 10px; left: 10px; border-right:0; border-bottom:0; }
.hud-corner.tr { top: 10px; right: 10px; border-left:0; border-bottom:0; }
.hud-corner.bl { bottom: 10px; left: 10px; border-right:0; border-top:0; }
.hud-corner.br { bottom: 10px; right: 10px; border-left:0; border-top:0; }

.hud-side-rail {
  position: absolute; top: 22%; width: 118px;
  display: flex; flex-direction: column; gap: 8px;
}
.hud-side-rail.left { left: 8px; }
.hud-side-rail.right { right: 8px; }
.hud-telem {
  background: var(--glass);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(0,242,255,.3);
  box-shadow: 0 0 15px rgba(0,242,255,.18), inset 0 0 20px rgba(0,242,255,.04);
  border-radius: 10px;
  padding: 8px 10px;
  transition: box-shadow .25s, border-color .25s, transform .25s;
}
.hud-telem:hover, .hud-telem.glow {
  border-color: var(--cyan);
  box-shadow: 0 0 22px rgba(0,242,255,.45), inset 0 0 24px rgba(0,242,255,.08);
  transform: translateY(-1px);
}
.hud-telem b {
  display:block; font-family:'Orbitron',sans-serif; font-size:9px;
  letter-spacing:.14em; color: var(--orange); margin-bottom: 2px;
}
.hud-telem span {
  font-family:'Share Tech Mono', monospace; font-size: 13px; color: var(--cyan);
  text-shadow: 0 0 8px rgba(0,242,255,.45);
}
.hud-telem.warn span { color: var(--orange); text-shadow: 0 0 8px rgba(255,170,0,.5); }

/* Decorativo não rouba cliques do menu Streamlit */
.j-shell, .j-shell * { pointer-events: none !important; }
div[data-testid="stMarkdownContainer"]:has(.j-shell),
div[data-testid="element-container"]:has(.j-shell),
div[data-testid="stMarkdownContainer"]:has(.hud-overlay),
div[data-testid="element-container"]:has(.hud-overlay) {
  pointer-events: none !important;
}

.block-container {
  padding-top: .85rem !important;
  padding-bottom: 2.2rem !important;
  max-width: 1180px !important;
  position: relative; z-index: 1;
}

.j-shell {
  position: relative; z-index: 1;
  margin-bottom: .75rem;
  padding: .95rem 1.05rem;
  border-radius: 16px;
  border: 1px solid rgba(0,242,255,.35);
  background: rgba(0, 242, 255, 0.05);
  backdrop-filter: blur(12px);
  box-shadow: 0 0 0 1px rgba(255,170,0,.12), 0 0 28px rgba(0,242,255,.15),
              inset 0 0 40px rgba(0,242,255,.04);
  animation: jpulse 4.8s ease-in-out infinite;
  pointer-events: none;
  overflow: hidden;
}
.j-shell::before {
  content:""; position:absolute; inset:0; pointer-events:none;
  background:
    linear-gradient(rgba(0,242,255,.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,242,255,.04) 1px, transparent 1px);
  background-size: 28px 28px;
  opacity:.5;
  mask-image: linear-gradient(180deg, rgba(0,0,0,.55), transparent 90%);
}
@keyframes jpulse {
  0%,100% { box-shadow: 0 0 0 1px rgba(255,170,0,.12), 0 0 28px rgba(0,242,255,.15), inset 0 0 40px rgba(0,242,255,.04); }
  50% { box-shadow: 0 0 0 1px rgba(0,242,255,.45), 0 0 40px rgba(0,242,255,.28), inset 0 0 48px rgba(255,170,0,.06); }
}
.j-row { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
.j-brand { display:flex; align-items:center; gap:12px; }
.j-arc {
  width: 48px; height: 48px; border-radius: 50%; position: relative;
  background: radial-gradient(circle at 35% 35%, #fff 0 8%, #7DF9FF 10% 28%, #00f2ff 32% 58%, #0077A8 62% 100%);
  box-shadow: 0 0 22px rgba(0,242,255,.95), inset 0 0 12px rgba(255,255,255,.55);
  animation: arc 2.1s ease-in-out infinite;
}
.j-arc::after {
  content:""; position:absolute; inset:-6px; border-radius:50%;
  border:1px dashed rgba(0,242,255,.5); animation: spin 10s linear infinite;
}
@keyframes arc {
  0%,100% { transform: scale(1); filter: brightness(1); }
  50% { transform: scale(1.08); filter: brightness(1.25); }
}
.j-brand h1 {
  margin:0; font-family:'Orbitron',sans-serif; font-size:1.12rem; letter-spacing:.18em;
  color: var(--cyan); text-shadow: 0 0 18px rgba(0,242,255,.65), 0 0 40px rgba(255,170,0,.2);
}
.j-brand p {
  margin:0; color: var(--orange); font-size:.72rem; letter-spacing:.2em; text-transform:uppercase;
  text-shadow: 0 0 10px rgba(255,170,0,.35);
  font-family:'Orbitron',sans-serif;
}
.j-greet {
  margin-top:.15rem; color: var(--cyan); font-family:'Orbitron',sans-serif;
  font-size:.72rem; letter-spacing:.1em; text-align:right;
  text-shadow: 0 0 10px rgba(0,242,255,.35);
  animation: softGlitch 5.5s steps(2, end) infinite;
}
@keyframes softGlitch {
  0%,90%,100% { transform: none; opacity: 1; text-shadow: 0 0 10px rgba(0,242,255,.35); }
  92% { transform: translate(1px,0); opacity:.85; text-shadow: -1px 0 #ffaa00, 1px 0 #00f2ff; }
  94% { transform: translate(-1px,0); }
}

.j-scan {
  height:2px; margin-top:10px;
  background: linear-gradient(90deg, transparent, #00f2ff, #ffaa00, #00f2ff, transparent);
  background-size: 200% 100%; animation: scanBar 2.6s linear infinite;
  opacity:.9; box-shadow: 0 0 10px rgba(0,242,255,.5);
}
@keyframes scanBar { from { background-position: 200% 0; } to { background-position: -200% 0; } }

.j-statusstrip {
  display:grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap:8px; margin-top:12px;
}
.j-stat {
  border:1px solid rgba(0,242,255,.28); border-radius:8px; padding:.5rem .55rem;
  background: rgba(0, 242, 255, 0.05);
  backdrop-filter: blur(8px);
  clip-path: polygon(10px 0, 100% 0, 100% calc(100% - 10px), calc(100% - 10px) 100%, 0 100%, 0 10px);
  box-shadow: 0 8px 20px rgba(0,0,0,.35), inset 0 0 16px rgba(0,242,255,.06), 0 0 12px rgba(0,242,255,.1);
  transition: border-color .2s, box-shadow .2s, transform .2s;
}
.j-stat:hover {
  border-color: var(--cyan);
  box-shadow: 0 0 20px rgba(0,242,255,.35), inset 0 0 18px rgba(0,242,255,.1);
  transform: translateY(-2px);
}
.j-stat b { display:block; font-family:'Orbitron',sans-serif; font-size:.55rem; color: var(--orange); letter-spacing:.12em; }
.j-stat span { color: var(--cyan); font-size:.92rem; font-weight:600; font-family:'Share Tech Mono', monospace;
  text-shadow: 0 0 8px rgba(0,242,255,.35); }
.j-stat.hot span, .j-stat.warn span { color: var(--orange); text-shadow:0 0 10px rgba(255,170,0,.5); }
.j-stat.ok span { color:#86efac; }

.j-hero {
  position:relative; overflow:hidden; border-radius:18px; margin-bottom:1rem;
  padding:1.45rem 1.25rem; border:1px solid rgba(0,242,255,.3);
  background: rgba(0, 242, 255, 0.05);
  backdrop-filter: blur(12px);
  box-shadow: 0 0 24px rgba(0,242,255,.12), inset 0 0 40px rgba(0,242,255,.04);
  transition: box-shadow .25s, border-color .25s;
}
.j-hero:hover {
  border-color: rgba(0,242,255,.55);
  box-shadow: 0 0 36px rgba(0,242,255,.28);
}
.j-hero::before {
  content:""; position:absolute; inset:0; pointer-events:none;
  background-image:
    linear-gradient(rgba(0,242,255,.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,242,255,.06) 1px, transparent 1px);
  background-size: 34px 34px;
  mask-image: linear-gradient(180deg, rgba(0,0,0,.45), transparent 88%);
  animation: drift 16s linear infinite;
}
@keyframes drift { from { background-position:0 0,0 0; } to { background-position:34px 34px,34px 34px; } }
.j-hero h2 {
  position:relative; margin:0 0 .35rem; font-family:'Orbitron',sans-serif;
  font-size:clamp(1.2rem, 3.2vw, 1.75rem); color:#e8fbff; letter-spacing:.06em;
  text-shadow: 0 0 16px rgba(0,242,255,.4);
}
.j-hero p { position:relative; margin:0; color:#9ecfe0; font-size:1.05rem; line-height:1.4; max-width:42rem; }

.j-chip {
  display:inline-flex; align-items:center; gap:8px; padding:.35rem .8rem; border-radius:999px;
  border:1px solid rgba(0,242,255,.4); background:rgba(0,30,40,.55); color: var(--cyan);
  font-family:'Orbitron',sans-serif; font-size:.7rem; letter-spacing:.1em;
  box-shadow: 0 0 12px rgba(0,242,255,.15);
}
.j-chip.on { border-color:#22c55e; color:#86efac; box-shadow:0 0 14px rgba(34,197,94,.3); }
.j-chip.busy { border-color: var(--orange); color:#ffd27a; }
.j-chip.talk { border-color:#38bdf8; color:#7DD3FC; }

.j-panel {
  border:1px solid rgba(0,242,255,.28); border-radius:14px; padding:1rem 1.05rem;
  background: rgba(0, 242, 255, 0.05);
  backdrop-filter: blur(10px);
  box-shadow: 0 0 18px rgba(0,242,255,.1), inset 0 0 28px rgba(0,242,255,.04);
  margin-bottom:.85rem;
  transition: border-color .2s, box-shadow .2s, transform .2s;
}
.j-panel:hover {
  border-color: rgba(0,242,255,.55);
  box-shadow: 0 0 28px rgba(0,242,255,.28);
  transform: translateY(-1px);
}
.j-panel h3 {
  margin:0 0 .5rem; font-family:'Orbitron',sans-serif; font-size:.78rem;
  letter-spacing:.14em; color: var(--orange); text-transform:uppercase;
}

.j-rings { display:flex; flex-wrap:wrap; gap:12px; margin: .6rem 0 1rem; }
.j-ring {
  width:92px; height:92px; border-radius:50%;
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  border:2px solid rgba(0,242,255,.45);
  box-shadow: 0 0 18px rgba(0,242,255,.3), inset 0 0 18px rgba(0,242,255,.12);
  background: radial-gradient(circle at 40% 35%, rgba(0,242,255,.2), rgba(0,0,0,.75));
  position: relative;
}
.j-ring::before {
  content:""; position:absolute; inset:-4px; border-radius:50%;
  border:1px dashed rgba(255,170,0,.4); animation: spin 12s linear infinite;
}
.j-ring b { font-family:'Orbitron',sans-serif; font-size:.9rem; color: var(--cyan); z-index:1; }
.j-ring span { font-size:.55rem; letter-spacing:.12em; color:#8FB6D8; text-transform:uppercase; z-index:1; }

.j-risk {
  border:1px solid rgba(255,170,0,.4); padding:.85rem 1rem; margin-top:.75rem;
  background: rgba(40,24,0,.4); color:#FFE08A; border-radius:12px;
  box-shadow: inset 0 0 20px rgba(255,170,0,.08), 0 0 16px rgba(255,170,0,.12);
}

.stButton > button {
  border-radius:12px !important;
  border:1px solid rgba(255,170,0,.6) !important;
  background: linear-gradient(180deg, #ffd56a 0%, #ffaa00 45%, #d97706 100%) !important;
  color:#0a0f18 !important; font-family:'Orbitron',sans-serif !important;
  font-weight:800 !important; letter-spacing:.06em !important;
  box-shadow: 0 0 22px rgba(255,170,0,.35), inset 0 1px 0 rgba(255,255,255,.35) !important;
  position: relative; z-index: 2;
  pointer-events: auto !important;
  text-transform: uppercase !important;
}
.stButton > button:hover {
  box-shadow: 0 0 32px rgba(0,242,255,.45), 0 0 18px rgba(255,170,0,.45) !important;
  filter: brightness(1.08);
}

div[data-testid="stSegmentedControl"] {
  position: relative; z-index: 90;
  pointer-events: auto !important;
  margin-bottom: .85rem;
  padding: .4rem;
  border: 1px solid rgba(0,242,255,.35);
  border-radius: 14px;
  background: rgba(0, 242, 255, 0.05);
  backdrop-filter: blur(10px);
  box-shadow: inset 0 0 24px rgba(0,242,255,.08), 0 0 20px rgba(0,242,255,.12);
}
div[data-testid="stSegmentedControl"] button,
div[data-testid="stSegmentedControl"] label,
div[data-testid="stSegmentedControl"] * {
  pointer-events: auto !important;
  font-family:'Orbitron',sans-serif !important;
  font-size:.68rem !important;
  letter-spacing:.06em !important;
  text-transform: uppercase !important;
}
div[data-testid="stSegmentedControl"] [data-baseweb="button"],
div[data-testid="stSegmentedControl"] button {
  background: linear-gradient(180deg, #ffe08a 0%, #ffaa00 42%, #c97800 100%) !important;
  color: #0a0f18 !important;
  border: 1px solid rgba(255, 200, 80, .65) !important;
  box-shadow: 0 0 16px rgba(255,170,0,.28), inset 0 1px 0 rgba(255,255,255,.28) !important;
  border-radius: 10px !important;
  font-weight: 800 !important;
}
div[data-testid="stSegmentedControl"] button[aria-checked="true"],
div[data-testid="stSegmentedControl"] [aria-checked="true"] {
  box-shadow: 0 0 28px rgba(0,242,255,.5), 0 0 18px rgba(255,170,0,.4), inset 0 0 12px rgba(255,255,255,.2) !important;
  border-color: #00f2ff !important;
  filter: brightness(1.08);
}

/* Chat holográfico */
div[data-testid="stChatMessage"] {
  background: rgba(0, 242, 255, 0.05) !important;
  backdrop-filter: blur(10px) !important;
  border: 1px solid rgba(0,242,255,.28) !important;
  border-radius: 14px !important;
  box-shadow: 0 0 20px rgba(0,242,255,.12), inset 0 0 24px rgba(0,242,255,.04) !important;
  animation: msgIn .45s ease-out both;
  transition: border-color .2s, box-shadow .2s;
}
div[data-testid="stChatMessage"]:hover {
  border-color: rgba(0,242,255,.55) !important;
  box-shadow: 0 0 28px rgba(0,242,255,.3) !important;
}
@keyframes msgIn {
  from { opacity: 0; transform: translateY(8px) skewX(-1deg); filter: blur(2px); }
  to { opacity: 1; transform: none; filter: none; }
}
div[data-testid="stChatMessage"] p,
div[data-testid="stChatMessage"] span,
div[data-testid="stChatMessage"] .stMarkdown {
  color: #d5f8ff !important;
  text-shadow: 0 0 6px rgba(0,242,255,.15);
}
div[data-testid="stChatInput"] textarea,
div[data-testid="stChatInput"] {
  border-color: rgba(0,242,255,.4) !important;
  background: rgba(0,10,14,.85) !important;
  color: #c8f7ff !important;
  box-shadow: 0 0 16px rgba(0,242,255,.12) !important;
}

.j-tech-tip {
  font-family:'Share Tech Mono', monospace; font-size:.72rem; color: rgba(0,242,255,.7);
  letter-spacing:.04em;
}

@media (max-width: 1100px) {
  .hud-side-rail { display: none; }
  .hud-ring-stack { opacity: .35; transform: scale(.7); }
}
@media (max-width: 900px) {
  .j-statusstrip { grid-template-columns: repeat(2, minmax(0,1fr)); }
  .j-greet { text-align:left; }
}
@media (max-width: 768px) {
  .block-container { padding-left:.65rem !important; padding-right:.65rem !important; }
  .j-shell { border-radius:12px; padding:.7rem; }
  .j-brand h1 { font-size:.92rem; }
  .j-hero { padding:1.1rem 1rem; border-radius:14px; }
  .j-hero h2 { font-size:1.1rem; }
  .hud-ring-stack { display:none; }
}

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
</style>
"""


def pt(mapa: dict[str, str], valor: str | None, padrao: str = "—") -> str:
    if not valor:
        return padrao
    return mapa.get(valor, valor)


def inject_hud() -> None:
    st.markdown(HUD_CSS, unsafe_allow_html=True)
    # Manifest/SW via link estático — NÃO usar components.html mexendo no
    # parent.document (isso causava NotFoundError: removeChild no React).
    st.markdown(
        '<link rel="manifest" href="/app/static/manifest.json" />',
        unsafe_allow_html=True,
    )
    # Overlay estável: valores cacheados ~3s (HTML com mesma estrutura a cada rerun).
    now = time.time()
    telem = st.session_state.get("_hud_telem")
    if not telem or now - float(st.session_state.get("_hud_telem_at") or 0) > 3.0:
        telem = {
            "v": round(random.uniform(11.7, 12.4), 2),
            "hz": random.randint(48, 62),
            "ma": round(random.uniform(0.12, 0.48), 2),
            "tmp": round(random.uniform(28.0, 41.0), 1),
            "scan": random.choice(["SYNC", "PROBE", "MAP", "IDLE"]),
        }
        st.session_state._hud_telem = telem
        st.session_state._hud_telem_at = now
    st.markdown(
        f"""
        <div class="hud-overlay" aria-hidden="true">
          <div class="hud-vignette"></div>
          <div class="hud-grid"></div>
          <div class="hud-scanline"></div>
          <div class="hud-corner tl"></div>
          <div class="hud-corner tr"></div>
          <div class="hud-corner bl"></div>
          <div class="hud-corner br"></div>
          <div class="hud-ring-stack tl">
            <div class="hud-ring r1"></div>
            <div class="hud-ring r2"></div>
            <div class="hud-ring r3"></div>
            <div class="hud-ring-core"></div>
          </div>
          <div class="hud-ring-stack br">
            <div class="hud-ring r1"></div>
            <div class="hud-ring r2"></div>
            <div class="hud-ring r3"></div>
            <div class="hud-ring-core"></div>
          </div>
          <div class="hud-side-rail left">
            <div class="hud-telem glow"><b>RAIL 12V</b><span>{telem['v']:.2f} V</span></div>
            <div class="hud-telem"><b>FREQ</b><span>{telem['hz']} kHz</span></div>
            <div class="hud-telem"><b>I-SENSE</b><span>{telem['ma']:.2f} A</span></div>
          </div>
          <div class="hud-side-rail right">
            <div class="hud-telem"><b>BOARD ΔT</b><span>{telem['tmp']:.1f} °C</span></div>
            <div class="hud-telem warn"><b>SCAN</b><span>{telem['scan']}</span></div>
            <div class="hud-telem"><b>PESQUISA</b><span>LIVE</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
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
        "listen_on": False,
        "last_voice_hash": "",
        "agent_speaking": False,
        "voice_status": "idle",
        "safety_ack": False,
        "last_manual_audio_hash": "",
        "nav": "bancada",
        "greeted_once": False,
        "tts_autoplay": False,
        "_pending_voice": None,
        "hud_modules": [],
        "music_on": False,
        "music_track": 0,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def top_menu() -> str:
    info = get_agent().provider_info()
    model = info.get("model") or ("demo" if info.get("mock") else "IA")
    profile = load_profile()
    who = address_user(profile)
    host = host_metrics()
    remote = load_remote_pc_sensor()
    cpu = host.get("cpu_percent")
    ram = host.get("ram_percent")
    cpu_s = f"{cpu:.0f}%" if isinstance(cpu, (int, float)) else "—"
    ram_s = f"{ram:.0f}%" if isinstance(ram, (int, float)) else "—"
    temp_cls = ""
    if remote and not remote.get("stale"):
        temps = remote.get("temperatures") or []
        if temps:
            pc_temp = f"{temps[0]['celsius']}°C"
            try:
                tc = float(temps[0]["celsius"])
                temp_cls = "hot" if tc >= 80 else ("ok" if tc < 70 else "")
            except Exception:
                pass
        else:
            pc_temp = f"CPU {remote.get('cpu_percent', '—')}%"
            temp_cls = "ok"
        pc_label = "PC LOCAL"
    else:
        temps = host.get("temperatures") or []
        if temps:
            pc_temp = f"{temps[0]['celsius']}°C"
            temp_cls = "ok"
        else:
            pc_temp = "sensor off"
        pc_label = host.get("label") or "HOST"
    hour = datetime.now().hour
    greet = "BOM DIA" if hour < 12 else ("BOA TARDE" if hour < 18 else "BOA NOITE")
    v_bus = random.uniform(4.85, 5.15)
    scan_pct = random.randint(18, 97)
    arc_cls = "busy" if st.session_state.get("voice_status") == "processing" else ""
    st.markdown(
        f"""
        <div class="j-shell">
          <div class="j-row">
            <div class="j-brand">
              <div class="j-arc {arc_cls}"></div>
              <div>
                <h1>JARVIS</h1>
                <p>HUD ENGENHARIA · {model}</p>
              </div>
            </div>
            <div class="j-greet">{greet}, {who.upper()} · CENTRO DE COMANDO ONLINE</div>
          </div>
          <div class="j-scan"></div>
          <div class="j-statusstrip">
            <div class="j-stat" title="Operador autenticado"><b>OPERADOR</b><span>{who}</span></div>
            <div class="j-stat" title="Oficina ativa"><b>OFICINA</b><span>{profile.get('workshop','—')}</span></div>
            <div class="j-stat" title="Carga do host"><b>CPU HOST</b><span>{cpu_s}</span></div>
            <div class="j-stat" title="Memória do host"><b>RAM HOST</b><span>{ram_s}</span></div>
            <div class="j-stat {temp_cls}" title="Telemetria térmica"><b>{pc_label}</b><span>{pc_temp}</span></div>
            <div class="j-stat" title="Enlace IA"><b>ENLACE</b><span>{(info.get('active') or '—').upper()}</span></div>
          </div>
          <div class="j-rings">
            <div class="j-ring"><b>{cpu_s}</b><span>CPU</span></div>
            <div class="j-ring"><b>{ram_s}</b><span>RAM</span></div>
            <div class="j-ring"><b>{v_bus:.1f}V</b><span>BUS</span></div>
            <div class="j-ring"><b>{scan_pct}%</b><span>SCAN</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    labels = {
        "bancada": "🦾 Bancada",
        "casos": "📁 Casos",
        "falhas": "🧰 Falhas",
        "seguranca": "🛡️ Segurança",
        "sistemas": "🛰️ Sistemas",
        "config": "⚙️ Config",
    }
    keys = list(labels.keys())
    if st.session_state.get("nav") not in keys:
        st.session_state.nav = "bancada"
    # Inicializa o widget uma vez — NÃO sobrescrever nav_segment em todo rerun
    # (isso anulava o clique do utilizador).
    if "nav_segment" not in st.session_state:
        st.session_state.nav_segment = st.session_state.nav
    chosen = st.segmented_control(
        "Navegação",
        options=keys,
        format_func=lambda k: labels[k],
        key="nav_segment",
        label_visibility="collapsed",
        width="stretch",
    )
    if chosen in keys:
        st.session_state.nav = chosen
    cascade = {
        "bancada": ["CHAT", "MÓDULOS", "MIC", "MÍDIA"],
        "casos": ["ABERTOS", "RESOLVIDOS", "RETOMAR"],
        "falhas": ["BANCO", "PARECIDOS", "APRENDER"],
        "seguranca": ["CHECKLIST", "ALERTAS"],
        "sistemas": ["CPU", "RAM", "ENLACE", "GCS"],
        "config": ["PERFIL", "VOZ", "MODELO"],
    }.get(st.session_state.nav, [])
    if cascade:
        chips = "".join(f"<span>{c}</span>" for c in cascade)
        st.markdown(f'<div class="j-cascade">{chips}</div>', unsafe_allow_html=True)
    return st.session_state.nav


def play_agent_voice(text: str) -> None:
    """Gera TTS e agenda autoplay no slot fixo de áudio (não monta st.audio aqui)."""
    if not st.session_state.voice_out or not (text or "").strip():
        st.session_state.agent_speaking = False
        st.session_state.voice_status = "listening" if st.session_state.listen_on else "idle"
        return
    st.session_state.voice_status = "speaking"
    st.session_state.agent_speaking = True
    try:
        audio = speak_text(text)
        if audio:
            st.session_state.last_tts_bytes = audio
            st.session_state.tts_autoplay = True
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
                meta={"phase": "chat", "mode": "chat", "spoken_reply": spoken, "hud": True},
            )
        except Exception:
            pass
        play_agent_voice(spoken)
        st.session_state.voice_status = "listening" if st.session_state.listen_on else "idle"
        st.session_state.agent_speaking = False
        st.rerun()
        return

    # Pausa o microfone ANTES do spinner — evita erro React removeChild
    # e impede nova fala enquanto a IA pensa.
    st.session_state.voice_status = "processing"
    st.session_state.agent_speaking = True
    with st.spinner("JARVIS sincronizando…"):
        try:
            result = ag.handle_user(
                case,
                text,
                image_bytes=image_bytes,
                image_name=image_name,
                image_mime=image_mime,
            )
        except Exception as exc:  # noqa: BLE001
            st.session_state.agent_speaking = False
            st.session_state.voice_status = "listening" if st.session_state.listen_on else "idle"
            st.error(f"Falha de enlace com a IA: {exc}")
            st.stop()
    # Retomada pode trocar o case_id
    if result.get("switched_case_id"):
        st.session_state.case_id = result["switched_case_id"]
    elif result.get("case", {}).get("case_id"):
        st.session_state.case_id = result["case"]["case_id"]
    if result.get("awaiting_confirm"):
        st.info("Aguardando confirmação da medição.")
    if result.get("safety_brief"):
        st.caption(f"🛡️ {result['safety_brief']}")
    play_agent_voice(result.get("spoken_reply") or result.get("message") or "")
    st.rerun()


def ensure_open_chat(ag: DiagnosticAgent) -> dict:
    """Garante uma sessão de chat aberto (sem formulário)."""
    if st.session_state.case_id:
        case = ag.load_case(st.session_state.case_id)
        if case:
            return case
    who = address_user()
    out = ag.open_session(who)
    st.session_state.case_id = out["case"]["case_id"]
    if out.get("spoken_reply") and not st.session_state.get("greeted_once"):
        st.session_state.greeted_once = True
        # TTS da saudação inicial (opcional)
        if st.session_state.get("voice_out", True):
            play_agent_voice(out.get("spoken_reply") or "")
    return out["case"]


def open_chat_view(ag: DiagnosticAgent) -> None:
    """Chat fluido estilo WhatsApp/ChatGPT — fotos e medições na conversa."""
    case = ensure_open_chat(ag)
    who = address_user()
    mode = case.get("chat_mode") or "open"
    mode_label = "MODO ESPECIALISTA" if mode == "electronics" else "CHAT ABERTO"
    board = case.get("board_model") or "—"
    symptom = case.get("symptom") or "—"

    st.markdown(
        f"""
        <div class="j-hero">
          <h2>Centro de comando, {who}</h2>
          <p>Dashboard modular estilo Homem de Ferro — módulos flutuam, chat fica. Mande foto quando quiser.
          Diga <b>consertar</b>, <b>defeito</b> ou <b>medir</b> e eu assumo o multímetro.
          Atalhos: <b>música de foco</b> · <b>abre o esquema</b> · <b>ver a placa</b> · <b>abre o vídeo</b> · <b>anota:</b> …</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        f"**{mode_label}** · caso `{case['case_id']}` · "
        f"placa: **{board}** · sintoma: **{symptom}** · "
        f"{pt(STATUS_PT, case.get('status'))}"
    )
    render_status_chip()
    compact_controls()

    cols = st.columns([1, 1, 1])
    with cols[0]:
        if st.button("Nova conversa", use_container_width=True):
            st.session_state.case_id = None
            st.session_state.greeted_once = False
            st.session_state.last_image_bytes = None
            st.session_state.last_voice_hash = ""
            st.rerun()
    with cols[1]:
        if mode != "electronics" and st.button("Ativar especialista", use_container_width=True):
            st.session_state.voice_status = "processing"
            st.session_state.agent_speaking = True
            submit_user_turn(
                ag,
                case,
                "Quero ativar o modo especialista para consertar um equipamento",
            )
    with cols[2]:
        if st.button("Casos salvos", use_container_width=True):
            st.session_state.nav = "casos"
            if "nav_segment" in st.session_state:
                st.session_state.nav_segment = "casos"
            st.rerun()

    st.markdown(
        '<div class="j-cmd-title">ZONA DE COMANDO · ANÁLISE · TELEMETRIA</div>',
        unsafe_allow_html=True,
    )
    left, center, right = st.columns([1.05, 1.45, 1.05], gap="medium")
    with left:
        render_zone_modules("left")
    with center:
        st.markdown(
            '<div class="j-cmd-title">ZONA DE COMANDO · CHAT</div>',
            unsafe_allow_html=True,
        )
        # Histórico do chat
        for msg in case.get("messages", []):
            papel = "assistant" if msg["role"] == "assistant" else "user"
            with st.chat_message(papel):
                st.caption("JARVIS" if msg["role"] == "assistant" else who)
                st.markdown(msg["content"])
                meta = msg.get("meta") or {}
                if meta.get("image"):
                    st.caption(f"📎 foto: {meta['image']}")
                if meta.get("probe") and msg["role"] == "assistant":
                    render_probe_card(meta["probe"])
                if meta.get("solution") and meta.get("verdict") == "fail":
                    render_solution(meta["solution"])

        last_meta: dict = {}
        for msg in reversed(case.get("messages", [])):
            if msg.get("role") == "assistant" and msg.get("meta"):
                last_meta = msg["meta"]
                break

        # Voz contínua
        # Escuta global montada em main() — evita segundo iframe (crash removeChild).

        # Composer: foto + texto na mesma conversa
        with st.container():
            photo = st.file_uploader(
                "Anexar foto na conversa",
                type=["jpg", "jpeg", "png", "webp"],
                key=f"chat_photo_{case['case_id']}",
            )
            prompt = st.chat_input("Mensagem, medição ou 'bom dia'…")
            if prompt is not None:
                image_bytes = image_name = None
                image_mime = "image/jpeg"
                text = prompt.strip()
                if photo is not None:
                    image_bytes = photo.getvalue()
                    image_name = photo.name
                    image_mime = photo.type or "image/jpeg"
                    st.session_state.last_image_bytes = image_bytes
                    st.session_state.last_image_name = image_name
                    (UPLOAD_DIR / f"{case['case_id']}_{image_name}").write_bytes(image_bytes)
                    try:
                        push_path(UPLOAD_DIR / f"{case['case_id']}_{image_name}")
                    except Exception:
                        pass
                    if not text:
                        text = "Analise a foto e diga o próximo passo."
                if text:
                    submit_user_turn(
                        ag,
                        case,
                        text,
                        image_bytes=image_bytes,
                        image_name=image_name,
                        image_mime=image_mime,
                    )

        with st.expander("Áudio manual ou documento"):
            manual = st.audio_input("Gravação manual")
            if manual is not None:
                digest = hashlib.sha1(manual.getvalue()).hexdigest()
                if digest != st.session_state.last_manual_audio_hash:
                    st.session_state.last_manual_audio_hash = digest
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
                        (UPLOAD_DIR / f"{case['case_id']}_{image_name}").write_bytes(image_bytes)
                        try:
                            push_path(UPLOAD_DIR / f"{case['case_id']}_{image_name}")
                        except Exception:
                            pass
                    submit_user_turn(
                        ag,
                        case,
                        transcript,
                        image_bytes=image_bytes,
                        image_name=image_name,
                        image_mime=image_mime,
                    )
            doc = st.file_uploader(
                "Esquema / PDF",
                type=["pdf", "txt", "md"],
                key=f"chat_doc_{case['case_id']}",
            )
            if doc is not None and st.button("Anexar documento", use_container_width=True):
                with st.spinner("Lendo documento…"):
                    try:
                        result = ag.attach_document(case, doc.name, doc.getvalue())
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Documento: {exc}")
                        st.stop()
                play_agent_voice(result.get("spoken_reply") or result.get("message") or "")
                st.rerun()

        with st.expander("Marcar resolvido (aprendizado + banco de falhas)"):
            part = st.text_input("Peça que resolveu", placeholder="Ex: C905")
            notes = st.text_input("Nota (opcional)")
            if st.button("Salvar no arquivo de falhas", type="primary"):
                if not part.strip():
                    st.error("Informe a peça.")
                else:
                    ag.resolve_case(case, part.strip(), notes.strip())
                    st.success("Salvo no SQLite e no banco JSON.")
                    play_agent_voice(f"Caso resolvido. Salvei a troca de {part.strip()}.")
                    st.rerun()

    with right:
        render_zone_modules("right")
        # Painel holográfico de telemetria da placa (valores oscilam a cada rerun)
        board_lbl = board if board and board != "—" else "AGUARDANDO MODELO"
        st.markdown(
            f"""
            <div class="j-panel">
              <h3>Telemetria da placa</h3>
              <div class="j-rings">
                <div class="j-ring"><b>{random.uniform(11.6,12.5):.1f}</b><span>VBUS</span></div>
                <div class="j-ring"><b>{random.uniform(3.25,3.38):.2f}</b><span>3V3</span></div>
                <div class="j-ring"><b>{random.randint(32,48)}</b><span>°C</span></div>
                <div class="j-ring"><b>{random.randint(1,9)}</b><span>NET</span></div>
              </div>
              <p class="j-tech-tip">MODELO · {board_lbl}<br/>SINTOMA · {symptom}<br/>SCANNER · ANALISANDO BANCADA</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        dm = case.get("diagnostic_map")
        if dm and mode == "electronics":
            st.markdown('<div class="j-panel"><h3>Mapa de diagnóstico</h3>', unsafe_allow_html=True)
            cur = int(dm.get("current_step") or 1)
            for step in dm.get("steps") or []:
                sid = int(step.get("id") or 0)
                mark = "▶" if sid == cur else ("✓" if sid < cur else "○")
                st.markdown(
                    f"**{mark} Passo {sid} — {step.get('name')}**  \n"
                    f"{step.get('goal')}  \n"
                    f"_{step.get('ask')}_"
                )
            if dm.get("research_hint"):
                st.caption(f"Pista web: {dm['research_hint'][:180]}")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="j-panel"><h3>Memória</h3>', unsafe_allow_html=True)
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
            st.caption("Nenhuma medição ainda — mande valores no chat.")
        st.markdown("</div>", unsafe_allow_html=True)

        render_audio_slot()

        if st.session_state.last_image_bytes:
            st.markdown('<div class="j-panel"><h3>Visão</h3>', unsafe_allow_html=True)
            coords = []
            if last_meta.get("probe"):
                coords = last_meta["probe"].get("coordinates") or []
            if coords:
                annotated = annotate_board(st.session_state.last_image_bytes, coords)
                st.image(annotated, caption="Pontas", use_container_width=True)
                zoom = zoom_around_probes(st.session_state.last_image_bytes, coords)
                if zoom is not None:
                    st.image(zoom, caption="Zoom", use_container_width=True)
            else:
                st.image(
                    st.session_state.last_image_bytes,
                    caption=st.session_state.last_image_name or "foto",
                    use_container_width=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

        st.caption(f"🛡️ {safety_brief(case.get('phase') if mode == 'electronics' else 'intake')}")


    st.markdown('<div class="j-music-wrap">', unsafe_allow_html=True)
    render_music_dock()
    st.markdown("</div>", unsafe_allow_html=True)

def mount_listen_slot() -> str | None:
    """Iframe de escuta contínua REMOVIDO (anti-removeChild). Sempre None."""
    return None


def render_audio_slot() -> None:
    """Player SEMPRE montado com o mesmo widget — nunca troca st.audio ↔ caption."""
    audio = st.session_state.get("last_tts_bytes") or _SILENT_WAV
    fmt = "audio/mp3" if st.session_state.get("last_tts_bytes") else "audio/wav"
    autoplay = bool(st.session_state.pop("tts_autoplay", False))
    try:
        st.audio(audio, format=fmt, autoplay=autoplay)
    except TypeError:
        st.audio(audio, format=fmt)


def consume_continuous_voice(key: str | None = None) -> str | None:
    pending = st.session_state.pop("_pending_voice", None)
    return pending


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
        # Toggle só controla se processamos o áudio — o widget FICA sempre montado.
        st.session_state.listen_on = st.toggle(
            "Mic rápido",
            value=st.session_state.listen_on,
            help="Gravação nativa do Streamlit (widget sempre no DOM — evita removeChild).",
        )
    with c3:
        st.session_state.safety_ack = st.toggle("Segurança OK", value=st.session_state.safety_ack)

    # CRÍTICO: st.audio_input SEMPRE no mesmo lugar do DOM (ligado ou não).
    # Montar/desmontar conforme o toggle causava NotFoundError: removeChild no React.
    st.caption(
        "Mic pronto — grave e envie." if st.session_state.listen_on
        else "Mic em espera (ligue Mic rápido para enviar a gravação)."
    )
    mic = st.audio_input("Falar com o JARVIS", key="jarvis_mic_fast")
    if st.session_state.listen_on and mic is not None:
        digest = hashlib.sha1(mic.getvalue()).hexdigest()
        if digest != st.session_state.last_manual_audio_hash:
            st.session_state.last_manual_audio_hash = digest
            st.session_state.voice_status = "processing"
            st.session_state.agent_speaking = True
            with st.spinner("Transcrevendo…"):
                try:
                    transcript = transcribe_audio(
                        mic.getvalue(), filename=mic.name or "fala.wav"
                    )
                except Exception as exc:  # noqa: BLE001
                    st.session_state.agent_speaking = False
                    st.session_state.voice_status = "idle"
                    st.error(f"Áudio: {exc}")
                    st.stop()
            if transcript and transcript.strip():
                st.session_state._pending_voice = transcript.strip()
                st.rerun()
    elif st.session_state.listen_on:
        st.session_state.voice_status = "listening"
    elif st.session_state.voice_status == "listening":
        st.session_state.voice_status = "idle"



def page_config() -> None:
    profile = load_profile()
    who = address_user(profile)
    st.markdown(
        f"""
        <div class="j-hero">
          <h2>CONFIGURAÇÃO · PERFIL</h2>
          <p>Operador ativo: <b>{who}</b>. O JARVIS usa este nome nas saudações e no HUD.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    presets = list_presets()
    names = [p["display_name"] for p in presets]
    cur = profile.get("display_name", "Sr. Igor")
    idx = names.index(cur) if cur in names else 0
    escolha = st.selectbox("Perfil rápido", names, index=idx)
    if st.button("Ativar perfil selecionado", type="primary", use_container_width=True):
        chosen = next(p for p in presets if p["display_name"] == escolha)
        save_profile(chosen)
        st.success(f"Perfil ativo: {chosen['display_name']}")
        st.rerun()

    st.markdown('<div class="j-panel"><h3>Editar dados do técnico</h3>', unsafe_allow_html=True)
    with st.form("form_perfil"):
        dn = st.text_input("Como o JARVIS chama (ex: Sr. Igor)", value=profile.get("display_name", ""))
        full = st.text_input("Nome completo", value=profile.get("full_name", ""))
        title = st.text_input("Função", value=profile.get("title", ""))
        workshop = st.text_input("Oficina / bancada", value=profile.get("workshop", ""))
        specialty = st.text_input("Especialidade", value=profile.get("specialty", ""))
        shifts = ["Integral", "Manhã", "Tarde", "Noite"]
        shift_cur = profile.get("shift", "Integral")
        shift = st.selectbox(
            "Turno",
            shifts,
            index=shifts.index(shift_cur) if shift_cur in shifts else 0,
        )
        notes = st.text_area("Notas", value=profile.get("notes", ""), height=80)
        call_by = st.checkbox("Chamar pelo nome", value=bool(profile.get("call_by_name", True)))
        if st.form_submit_button("Salvar perfil", type="primary", use_container_width=True):
            save_profile(
                {
                    **profile,
                    "display_name": dn.strip() or "Sr. Igor",
                    "full_name": full.strip(),
                    "title": title.strip(),
                    "workshop": workshop.strip(),
                    "specialty": specialty.strip(),
                    "shift": shift,
                    "notes": notes.strip(),
                    "call_by_name": call_by,
                }
            )
            st.success(f"Salvo. JARVIS vai chamar: {dn.strip() or 'Sr. Igor'}")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="j-panel"><h3>Temperatura real do PC</h3>
        <p>1) No Windows, na pasta do projeto: <code>pip install -r requirements.txt</code><br>
        2) Terminal A: <code>python scripts/sensor_local.py</code> (deixe aberto)<br>
        3) Terminal B: <code>streamlit run app.py --server.port 3847</code><br>
        4) Abra <b>Sistemas</b> — CPU/RAM/temp vêm do seu PC.<br>
        No site Cloud Run, CPU/RAM são do <b>servidor</b>, não da bancada.</p></div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="j-risk"><b>RISCOS</b> · Cloud Run com mín=0 pode ter cold start ·
        OpenAI consome créditos · não compartilhe a API key ·
        temperatura no cloud ≠ PC da bancada · confirmação antes de SOLUÇÃO é obrigatória ·
        não mexa em alta tensão sem EPI.</div>
        """,
        unsafe_allow_html=True,
    )


def page_sistemas(ag: DiagnosticAgent) -> None:
    st.caption(status_line())
    info = ag.provider_info()
    profile = load_profile()
    who = address_user(profile)
    host = host_metrics()
    remote = load_remote_pc_sensor()
    live = remote if (remote and not remote.get("stale")) else host
    src = "PC LOCAL (sensor)" if (remote and not remote.get("stale")) else (host.get("label") or "HOST")

    st.markdown(
        f"""
        <div class="j-hero">
          <h2>SISTEMAS À SUA DISPOSIÇÃO · {who.upper()}</h2>
          <p>Telemetria do núcleo: CPU, RAM, temperatura e estado da armadura. Fonte: {src}.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_status_chip()
    compact_controls()

    cpu = live.get("cpu_percent")
    ram = live.get("ram_percent")
    temps = live.get("temperatures") or []
    temp_s = f"{temps[0]['celsius']:.0f}°C" if temps else "N/D"
    disk = live.get("disk_percent")
    disk_s = f"{disk:.0f}%" if isinstance(disk, (int, float)) else "—"
    cpu_s = f"{cpu:.0f}%" if isinstance(cpu, (int, float)) else "—"
    ram_s = f"{ram:.0f}%" if isinstance(ram, (int, float)) else "—"

    st.markdown(
        f"""
        <div class="j-rings">
          <div class="j-ring"><b>{cpu_s}</b><span>CPU</span></div>
          <div class="j-ring"><b>{ram_s}</b><span>RAM</span></div>
          <div class="j-ring"><b>{temp_s}</b><span>TEMP</span></div>
          <div class="j-ring"><b>{disk_s}</b><span>DISK</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("CPU", cpu_s)
    if live.get("ram_used_gb") is not None:
        m2.metric("RAM", f"{live.get('ram_used_gb')} / {live.get('ram_total_gb')} GB")
    else:
        m2.metric("RAM", ram_s)
    m3.metric("Temperatura", temp_s if temps else "Não disponível")
    m4.metric("Host", live.get("hostname") or host.get("hostname") or "—")

    if temps:
        for t in temps[:6]:
            st.caption(f"Sensor `{t.get('sensor')}` → **{t.get('celsius')} °C**")
    else:
        st.info(
            "Temperatura não disponível neste host. No Windows rode "
            "`python scripts/sensor_local.py` na pasta do projeto."
        )

    if remote:
        age = remote.get("age_sec")
        if remote.get("stale"):
            st.warning(f"Sensor local desatualizado ({age}s). Reinicie `scripts/sensor_local.py`.")
        else:
            st.success(f"Sensor local ativo · idade {age}s · {remote.get('hostname', '')}")

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Provedor", (info.get("active") or "—").upper())
    c2.metric("Modelo", info.get("model") or "—")
    c3.metric("Modo", "DEMO" if info.get("mock") else "COMBATE")
    st.caption(
        "Deploy: Google Cloud Run + GCS — ver deploy/CLOUDRUN.md"
    )
    st.markdown(
        """
        <div class="j-risk"><b>RISCOS OPERACIONAIS</b> · Free Cloud Run dorme sem ping ·
        cold start ~30–60s · API paga por uso · métricas do site ≠ PC da bancada ·
        confirme medição antes de SOLUÇÃO · EPI em alta tensão.</div>
        """,
        unsafe_allow_html=True,
    )
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
        st.session_state.nav_segment = "bancada"
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
            st.session_state.nav_segment = "bancada"
            st.rerun()


def intake_form(ag: DiagnosticAgent) -> None:
    who = address_user()
    hour = datetime.now().hour
    greet = "Bom dia" if hour < 12 else ("Boa tarde" if hour < 18 else "Boa noite")
    st.markdown(
        f"""
        <div class="j-hero">
          <h2>{greet.upper()}, {who.upper()}</h2>
          <p>Sistemas à sua disposição. Diga o modelo da placa e o sintoma. Eu vejo, pesquiso,
          guio o multímetro e falo o próximo passo — J.A.R.V.I.S. na bancada.</p>
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
    heard = None  # microfone global em main()
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
        render_audio_slot()

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
        # Escuta global montada em main() — evita segundo iframe.
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
                        try:
                            push_path(UPLOAD_DIR / f"{case['case_id']}_{image_name}")
                        except Exception:
                            pass
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
                        try:
                            push_path(UPLOAD_DIR / f"{case['case_id']}_{image_name}")
                        except Exception:
                            pass
                    submit_user_turn(
                        ag,
                        case,
                        text,
                        image_bytes=image_bytes,
                        image_name=image_name,
                        image_mime=image_mime,
                    )

        with st.expander("Marcar resolvido (aprendizado + banco de falhas)"):
            part = st.text_input("Peça que resolveu", placeholder="Ex: C905")
            notes = st.text_input("Nota (opcional)")
            if st.button("Salvar no arquivo de falhas", type="primary"):
                if not part.strip():
                    st.error("Informe a peça.")
                else:
                    ag.resolve_case(case, part.strip(), notes.strip())
                    st.success("Salvo no SQLite e no banco JSON.")
                    play_agent_voice(f"Caso resolvido. Salvei a troca de {part.strip()}.")
                    st.rerun()

    with right:
        dm = case.get("diagnostic_map")
        if dm:
            st.markdown('<div class="j-panel"><h3>Mapa de diagnóstico</h3>', unsafe_allow_html=True)
            cur = int(dm.get("current_step") or 1)
            for step in dm.get("steps") or []:
                sid = int(step.get("id") or 0)
                mark = "▶" if sid == cur else ("✓" if sid < cur else "○")
                st.markdown(
                    f"**{mark} Passo {sid} — {step.get('name')}**  \n"
                    f"{step.get('goal')}  \n"
                    f"_{step.get('ask')}_"
                )
            if dm.get("research_hint"):
                st.caption(f"Pista web: {dm['research_hint'][:180]}")
            st.markdown("</div>", unsafe_allow_html=True)

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

    # Sem iframe de microfone (removeChild). Voz via st.audio_input em compact_controls.
    if False:
        heard = mount_listen_slot()
        if heard:
            st.session_state._pending_voice = heard

    if nav == "seguranca":
        page_seguranca()
    elif nav == "falhas":
        page_falhas()
    elif nav == "casos":
        page_casos(ag)
    elif nav == "sistemas":
        page_sistemas(ag)
    elif nav == "config":
        page_config()
    else:
        # Se a voz capturou frase, processa no chat aberto
        pending = st.session_state.pop("_pending_voice", None)
        if pending:
            case = ensure_open_chat(ag)
            st.success(f"Ouvi: “{pending}”")
            submit_user_turn(ag, case, pending)
            return
        open_chat_view(ag)


if __name__ == "__main__":
    main()
