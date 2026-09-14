"""Voz: escuta (Whisper) e fala (TTS OpenAI)."""

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
        raise RuntimeError("OPENAI_API_KEY não configurada — voz precisa da chave OpenAI.")
    return OpenAI(api_key=key)


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """Converte áudio em texto (pt-BR) via Whisper."""
    client = _openai_client()
    model = os.getenv("WHISPER_MODEL", "whisper-1")
    file_tuple = (filename, audio_bytes)
    result = client.audio.transcriptions.create(
        model=model,
        file=file_tuple,
        language="pt",
        prompt=(
            "Diagnóstico eletrônico. Pode conter valores como 5 vírgula 2 volts, "
            "pino 3, CI de standby, capacitor C905, continuidade, ohms."
        ),
    )
    text = (result.text or "").strip()
    return text


def speak_text(text: str, voice: str | None = None) -> bytes:
    """Gera áudio MP3 da fala do agente (pt-BR)."""
    client = _openai_client()
    voice_name = voice or os.getenv("TTS_VOICE", "nova")
    model = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
    clean = _for_speech(text)
    try:
        response = client.audio.speech.create(
            model=model,
            voice=voice_name,
            input=clean,
            response_format="mp3",
            instructions="Fale em português do Brasil, claro, calmo e objetivo, como um técnico guia.",
        )
    except Exception:
        # fallback para tts-1 se o modelo novo não estiver disponível na conta
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice_name if voice_name in {"alloy", "echo", "fable", "onyx", "nova", "shimmer"} else "nova",
            input=clean,
            response_format="mp3",
        )
    return response.content


def _for_speech(text: str) -> str:
    """Remove markdown e deixa o texto natural para falar."""
    t = text or ""
    t = re.sub(r"\*\*|__|`+", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"#+\s*", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Limita tamanho para TTS (evita áudio longo demais)
    if len(t) > 900:
        t = t[:900].rsplit(".", 1)[0] + "."
    return t


def extract_intake_from_speech(transcript: str) -> dict[str, str]:
    """Extrai modelo da placa e sintoma de uma fala livre."""
    client = _openai_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Extraia do texto falado o modelo da placa/aparelho e o sintoma. "
                    "Responda só JSON: {\"board_model\": \"...\", \"symptom\": \"...\"}. "
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
