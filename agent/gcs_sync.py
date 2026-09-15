"""Sincroniza a pasta de dados com um bucket Google Cloud Storage.

No Cloud Run o disco do container some a cada deploy/restart.
Com GCS_BUCKET definido:
  - no boot: baixa o bucket → JARVIS_DATA_DIR
  - a cada gravação: sobe o arquivo alterado

Sem GCS_BUCKET (local / Railway volume): não faz nada.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from .paths import DATA_ROOT, ensure_data_dirs

log = logging.getLogger("jarvis.gcs")
_lock = threading.Lock()
_pulled = False


def gcs_enabled() -> bool:
    return bool((os.getenv("GCS_BUCKET") or "").strip())


def _bucket_name() -> str:
    return (os.getenv("GCS_BUCKET") or "").strip()


def _prefix() -> str:
    # Prefixo opcional dentro do bucket, ex.: jarvis/
    p = (os.getenv("GCS_PREFIX") or "jarvis").strip().strip("/")
    return f"{p}/" if p else ""


def _client():
    from google.cloud import storage

    return storage.Client()


def _rel(path: Path) -> str | None:
    try:
        rel = path.resolve().relative_to(DATA_ROOT.resolve())
    except ValueError:
        return None
    return rel.as_posix()


def pull_from_gcs(*, force: bool = False) -> str:
    """Baixa objetos do bucket para DATA_ROOT (uma vez por processo)."""
    global _pulled
    if not gcs_enabled():
        return "GCS desligado"
    with _lock:
        if _pulled and not force:
            return "GCS já sincronizado neste boot"
        ensure_data_dirs()
        bucket_name = _bucket_name()
        prefix = _prefix()
        try:
            client = _client()
            bucket = client.bucket(bucket_name)
            count = 0
            for blob in client.list_blobs(bucket_name, prefix=prefix):
                name = blob.name
                if not name or name.endswith("/"):
                    continue
                rel = name[len(prefix) :] if name.startswith(prefix) else name
                if not rel:
                    continue
                dest = DATA_ROOT / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                blob.download_to_filename(str(dest))
                count += 1
            _pulled = True
            msg = f"GCS pull OK: {count} arquivo(s) de gs://{bucket_name}/{prefix}"
            log.info(msg)
            return msg
        except Exception as exc:  # noqa: BLE001
            msg = f"GCS pull falhou (seguindo com disco local): {exc}"
            log.warning(msg)
            _pulled = True  # não martela a API a cada rerun do Streamlit
            return msg


def push_path(path: Path | str) -> None:
    """Envia um arquivo (ou pasta) para o bucket."""
    if not gcs_enabled():
        return
    path = Path(path)
    try:
        if path.is_dir():
            for f in path.rglob("*"):
                if f.is_file():
                    _upload_file(f)
            return
        if path.is_file():
            _upload_file(path)
    except Exception as exc:  # noqa: BLE001
        log.warning("GCS push falhou (%s): %s", path, exc)


def _upload_file(path: Path) -> None:
    rel = _rel(path)
    if not rel:
        return
    bucket_name = _bucket_name()
    blob_name = f"{_prefix()}{rel}"
    client = _client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(str(path))
    log.debug("GCS upload %s", blob_name)


def push_all() -> str:
    """Sobe a árvore inteira de DATA_ROOT (backup manual / migração)."""
    if not gcs_enabled():
        return "GCS desligado"
    ensure_data_dirs()
    n = 0
    for f in DATA_ROOT.rglob("*"):
        if f.is_file():
            try:
                _upload_file(f)
                n += 1
            except Exception as exc:  # noqa: BLE001
                log.warning("skip %s: %s", f, exc)
    return f"GCS push ALL: {n} arquivo(s)"


def status_line() -> str:
    if not gcs_enabled():
        return "Memória: disco local (sem GCS)"
    return f"Memória: gs://{_bucket_name()}/{_prefix()} → {DATA_ROOT}"
