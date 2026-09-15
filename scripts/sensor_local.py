"""
Sensor local do PC do técnico (Windows/Linux).
Roda NO SEU COMPUTADOR e grava telemetria para o JARVIS ler.

Uso (no PC):
  pip install psutil
  python scripts/sensor_local.py

Opcional — enviar para pasta data/sensors se o app rodar no mesmo PC.
Na nuvem (Render), copie o JSON gerado ou rode o JARVIS localmente para ver CPU/temp reais.
"""

from __future__ import annotations

import json
import platform
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import psutil
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Instale: pip install psutil") from exc


OUT = Path(__file__).resolve().parents[1] / "data" / "sensors" / "pc_local.json"


def read_temps() -> list[dict]:
    temps: list[dict] = []
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

    # Windows: tenta WMI se não houver sensors_temperatures
    if not temps and platform.system() == "Windows":
        try:
            import wmi  # type: ignore

            w = wmi.WMI(namespace="root\\wmi")
            for item in w.MSAcpi_ThermalZoneTemperature():
                c = round(float(item.CurrentTemperature) / 10.0 - 273.15, 1)
                temps.append({"sensor": "ACPI", "celsius": c})
        except Exception:
            pass
    return temps


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"JARVIS sensor local → {OUT}")
    print("Ctrl+C para parar. Atualiza a cada 5s.")
    while True:
        payload = {
            "at": datetime.now(timezone.utc).isoformat(),
            "received_at": time.time(),
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "technician_hint": "Sr. Igor",
            "cpu_percent": psutil.cpu_percent(interval=0.3),
            "ram_percent": psutil.virtual_memory().percent,
            "temperatures": read_temps(),
            "source": "pc_local",
        }
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        t = payload["temperatures"]
        tmsg = f"{t[0]['celsius']}°C" if t else "temp n/d (normal em muitos PCs Windows)"
        print(
            f"[{time.strftime('%H:%M:%S')}] CPU {payload['cpu_percent']}% | "
            f"RAM {payload['ram_percent']}% | {tmsg}"
        )
        time.sleep(5)


if __name__ == "__main__":
    main()
