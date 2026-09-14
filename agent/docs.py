"""Upload e leitura de esquemas / datasheets (PDF ou texto)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "docs"


def save_case_doc(case_id: str, filename: str, data: bytes) -> Path:
    folder = DOCS_DIR / case_id
    folder.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in filename)[:120]
    path = folder / safe
    path.write_bytes(data)
    return path


def extract_text_from_bytes(filename: str, data: bytes, max_chars: int = 12000) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return _extract_pdf(data, max_chars=max_chars)
    if name.endswith((".txt", ".md", ".csv")):
        try:
            return data.decode("utf-8", errors="ignore")[:max_chars]
        except Exception:
            return data.decode("latin-1", errors="ignore")[:max_chars]
    # imagem de esquema: só nota — a visão do LLM analisa se anexada como foto
    if name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return "(documento de imagem — use também o upload de foto da placa/esquema)"
    return "(formato não suportado para texto; envie PDF ou TXT)"


def _extract_pdf(data: bytes, max_chars: int = 12000) -> str:
    try:
        from pypdf import PdfReader
        import io

        reader = PdfReader(io.BytesIO(data))
        parts: list[str] = []
        total = 0
        for page in reader.pages[:20]:
            text = page.extract_text() or ""
            if not text.strip():
                continue
            parts.append(text.strip())
            total += len(text)
            if total >= max_chars:
                break
        blob = "\n\n".join(parts).strip()
        return blob[:max_chars] if blob else "(PDF sem texto extraível — pode ser imagem escaneada)"
    except Exception as exc:  # noqa: BLE001
        return f"(falha ao ler PDF: {exc})"


def docs_context_from_case(case: dict[str, Any]) -> str:
    docs = case.get("documents") or []
    if not docs:
        return ""
    chunks = ["DOCUMENTOS DO CASO (esquema/datasheet):"]
    for d in docs[-3:]:
        name = d.get("filename") or "doc"
        excerpt = (d.get("excerpt") or "")[:4000]
        chunks.append(f"--- {name} ---\n{excerpt}")
    return "\n".join(chunks)
