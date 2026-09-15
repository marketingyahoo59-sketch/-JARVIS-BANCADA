"""Voz: Whisper STT + TTS OpenAI, com fallback offline/browser."""

from __future__ import annotations

import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _openai_client():
    from openai import OpenAI

    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY não configurada.")
    return OpenAI(api_key=key)


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """Converte áudio em texto (pt-BR) via Whisper; se falhar, lança erro claro."""
    try:
        client = _openai_client()
        model = os.getenv("WHISPER_MODEL", "whisper-1")
        result = client.audio.transcriptions.create(
            model=model,
            file=(filename, audio_bytes),
            language="pt",
            prompt=(
                "Diagnóstico eletrônico. Pode conter valores como 5 vírgula 2 volts, "
                "pino 3, CI de standby, capacitor C905, continuidade, ohms."
            ),
        )
        return (result.text or "").strip()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Whisper indisponível. Use a escuta contínua do navegador (Chrome/Edge) "
            f"ou tente de novo. Detalhe: {exc}"
        ) from exc


def speak_text(text: str, voice: str | None = None) -> bytes:
    """Gera MP3. JARVIS_TTS=edge|openai|off (padrão edge = mais rápido)."""
    clean = _for_speech(text)
    prefer = (os.getenv("JARVIS_TTS") or "edge").strip().lower()
    if prefer in {"off", "0", "false", "no"}:
        return b""
    if prefer == "openai":
        try:
            return _speak_openai(clean, voice=voice)
        except Exception:
            return _speak_edge(clean)
    try:
        return _speak_edge(clean)
    except Exception:
        try:
            return _speak_openai(clean, voice=voice)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "TTS indisponível (edge e OpenAI). "
                f"Detalhe: {exc}"
            ) from exc



def _speak_openai(clean: str, voice: str | None = None) -> bytes:
    client = _openai_client()
    voice_name = voice or os.getenv("TTS_VOICE", "nova")
    model = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
    try:
        response = client.audio.speech.create(
            model=model,
            voice=voice_name,
            input=clean,
            response_format="mp3",
            instructions=(
                "Fale em português do Brasil, claro, calmo e objetivo, "
                "como um técnico guia parceiro de bancada."
            ),
        )
    except Exception:
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice_name
            if voice_name in {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
            else "nova",
            input=clean,
            response_format="mp3",
        )
    return response.content


def _speak_edge(clean: str) -> bytes:
    """Fallback TTS sem chave OpenAI (edge-tts)."""
    import asyncio
    import tempfile
    from pathlib import Path

    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("Pacote edge-tts não instalado") from exc

    voice = os.getenv("EDGE_TTS_VOICE", "pt-BR-AntonioNeural")

    async def _run() -> bytes:
        communicate = edge_tts.Communicate(clean, voice)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            out = Path(tmp.name)
        await communicate.save(str(out))
        data = out.read_bytes()
        out.unlink(missing_ok=True)
        return data

    try:
        return asyncio.run(asyncio.wait_for(_run(), timeout=8.0))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"edge-tts timeout/falha: {exc}") from exc


def _for_speech(text: str) -> str:
    t = text or ""
    t = re.sub(r"\*\*|__|`+", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"#+\s*", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 900:
        t = t[:900].rsplit(".", 1)[0] + "."
    return t


def extract_intake_from_speech(transcript: str) -> dict[str, str]:
    """Extrai modelo da placa e sintoma de uma fala livre."""
    client = _openai_client()
    model = os.getenv("OPENAI_MODEL", "gpt-5.5")
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Extraia do texto falado o modelo da placa/aparelho e o sintoma. "
                    'Responda só JSON: {"board_model": "...", "symptom": "..."}. '
                    "Se faltar algo, use o melhor palpite curto em português."
                ),
            },
            {"role": "user", "content": transcript},
        ],
    )
    import json

    raw = response.choices[0].message.content or "{}"
    data: dict[str, Any] = json.loads(raw)
    return {
        "board_model": str(data.get("board_model") or transcript[:80]).strip(),
        "symptom": str(data.get("symptom") or transcript).strip(),
    }


# aliases
speak_text = speak_text
transcribe_audio = transcribe_audio
