"""Métricas do host (servidor/local) e sensor remoto do PC do técnico."""

from __future__ import annotations

import json
import os
import platform
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


from .paths import SENSORS_DIR as SENSOR_DIR, ensure_data_dirs

ensure_data_dirs()
SENSOR_DIR.mkdir(parents=True, exist_ok=True)
REMOTE_SENSOR = SENSOR_DIR / "pc_local.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def host_metrics() -> dict[str, Any]:
    """Métricas da máquina onde o JARVIS está rodando (Render ou PC local)."""
    out: dict[str, Any] = {
        "at": _now(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "source": "host",
        "label": "SERVIDOR RENDER" if os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID") else "HOST LOCAL",
    }
    try:
        import psutil

        out["cpu_percent"] = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        out["ram_percent"] = mem.percent
        out["ram_used_gb"] = round(mem.used / (1024**3), 2)
        out["ram_total_gb"] = round(mem.total / (1024**3), 2)
        disk = psutil.disk_usage("/")
        out["disk_percent"] = disk.percent
        temps = []
        try:
            tmap = psutil.sensors_temperatures() or {}
            for name, entries in tmap.items():
                for e in entries:
                    if e.current is not None:
                        temps.append(
                            {
                                "sensor": f"{name}:{e.label or 'temp'}",
                                "celsius": round(float(e.current), 1),
                            }
                        )
        except Exception:
            pass
        out["temperatures"] = temps
        out["temp_available"] = bool(temps)
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)
        out["cpu_percent"] = None
        out["ram_percent"] = None
        out["temperatures"] = []
        out["temp_available"] = False
    return out


def save_remote_pc_sensor(payload: dict[str, Any]) -> Path:
    """Salva telemetria enviada pelo PC do Sr. Igor (script local)."""
    data = {
        "at": _now(),
        "received_at": time.time(),
        **payload,
        "source": "pc_local",
    }
    REMOTE_SENSOR.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return REMOTE_SENSOR


def load_remote_pc_sensor(max_age_sec: int = 120) -> dict[str, Any] | None:
    if not REMOTE_SENSOR.exists():
        return None
    try:
        data = json.loads(REMOTE_SENSOR.read_text(encoding="utf-8"))
        age = time.time() - float(data.get("received_at") or 0)
        data["age_sec"] = round(age, 1)
        data["stale"] = age > max_age_sec
        return data
    except Exception:
        return None
