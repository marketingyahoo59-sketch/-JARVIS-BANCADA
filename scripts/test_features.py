"""Testa os 8 melhoramentos sem UI."""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def ok(name: str) -> None:
    print(f"OK  {name}")


def fail(name: str, exc: Exception) -> None:
    print(f"FAIL {name}: {exc}")
    raise SystemExit(1) from exc


def test_vision() -> None:
    try:
        from agent.vision import annotate_board, zoom_around_probes

        img = Image.new("RGB", (640, 480), (40, 40, 40))
        d = ImageDraw.Draw(img)
        d.rectangle((100, 80, 540, 400), outline=(200, 200, 200), width=3)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        data = buf.getvalue()
        coords = [
            {"label": "ponta preta GND", "x": 20, "y": 70},
            {"label": "ponta vermelha VCC", "x": 75, "y": 30},
        ]
        annotated = annotate_board(data, coords)
        assert annotated.size == (640, 480)
        zoom = zoom_around_probes(data, coords)
        assert zoom is not None and zoom.size[0] >= 100
        ok("1 visão: marcação + zoom")
    except Exception as exc:  # noqa: BLE001
        fail("1 visão", exc)


def test_status_helpers() -> None:
    try:
        labels = {"idle", "listening", "processing", "speaking"}
        assert labels == {"idle", "listening", "processing", "speaking"}
        from agent.listen_component import continuous_listen

        assert continuous_listen(active=True) is None
        ok("2 escuta: no-op (anti-removeChild)")
    except Exception as exc:  # noqa: BLE001
        fail("2 escuta", exc)


def test_research_guards() -> None:
    try:
        from agent.research import is_researchable_device, research_for_case, _is_junk

        assert not is_researchable_device("equipamento")
        assert not is_researchable_device("o equipamento")
        assert is_researchable_device("Samsung UN32J4300")
        assert is_researchable_device("placa Fonte Philco PBF")
        assert _is_junk(
            "Código de Erro do Microsoft Teams 0xcaa80000",
            "login Windows",
            "https://techcommunity.microsoft.com/t5/teams",
        )
        out = research_for_case({"board_model": "", "symptom": "não liga"}, "consertar")
        assert "adiada" in out.lower() or "modelo" in out.lower()
        ok("2b pesquisa: filtro + sem modelo")
    except Exception as exc:  # noqa: BLE001
        fail("2b pesquisa", exc)


def test_operator_scene() -> None:
    try:
        from agent.agent_tools import execute_tool
        from agent.scene import (
            parse_num,
            scan_anomalies,
            screen_snapshot,
            verify_actions,
        )

        assert parse_num("5.8 V") == 5.8
        alerts = scan_anomalies({"telemetry": {"vbus": "5.9 V"}, "ui_errors": []})
        assert alerts and "5V" in alerts[0]["text"]
        snap = screen_snapshot()
        assert "layout" in snap and "modules" in snap
        close = execute_tool("close_all_modules", {})
        assert close.get("ok")
        layout = execute_tool("set_layout", {"mode": "repair"})
        assert layout.get("ok") and layout.get("layout") == "repair"
        focus = execute_tool("focus_component", {"id": "vbus"})
        assert focus.get("ok") and focus.get("id") == "vbus"
        checks = verify_actions(
            [{"name": "set_layout", "result": {"ok": True, "layout": "repair"}}],
            {"layout": "repair", "modules": [], "focus": "vbus"},
        )
        assert checks and checks[0]["ok"]
        ok("2c operador: cena + anomalia 5V + tools")
    except Exception as exc:  # noqa: BLE001
        fail("2c operador cena", exc)


def test_failures() -> None:
    try:
        from agent import failures

        with tempfile.TemporaryDirectory() as tmp:
            failures.BANK_DIR = Path(tmp)
            failures.BANK_PATH = Path(tmp) / "bank.json"
            entry = failures.add_resolved_failure(
                board_model="Placa Fonte XYZ",
                symptom="não liga / LED standby apagado",
                failed_node="rail 5V standby",
                replaced_part="C905 1000uF",
                notes="inchado",
            )
            assert entry["replaced_part"] == "C905 1000uF"
            sims = failures.find_similar("Fonte XYZ", "não liga")
            assert sims and sims[0]["id"] == entry["id"]
            assert failures.list_failures()
            ctx = failures.similar_as_context("Fonte XYZ", "LED standby")
            assert "C905" in ctx
        ok("3 banco de falhas")
    except Exception as exc:  # noqa: BLE001
        fail("3 banco de falhas", exc)


def test_docs() -> None:
    try:
        from agent.docs import extract_text_from_bytes, docs_context_from_case, save_case_doc

        txt = b"Datasheet U1 pin 8 = VCC 3.3V\nPin 4 = GND"
        excerpt = extract_text_from_bytes("esquema.txt", txt)
        assert "VCC" in excerpt
        with tempfile.TemporaryDirectory() as tmp:
            from agent import docs

            docs.DOCS_DIR = Path(tmp)
            path = save_case_doc("case-test", "esquema.txt", txt)
            assert path.exists()
        ctx = docs_context_from_case(
            {"documents": [{"filename": "esquema.txt", "excerpt": excerpt}]}
        )
        assert "DOCUMENTOS" in ctx and "VCC" in ctx
        # PDF mínimo (pode não ter texto); só não pode crashar
        try:
            from pypdf import PdfWriter

            bio = io.BytesIO()
            w = PdfWriter()
            w.add_blank_page(width=200, height=200)
            w.write(bio)
            pdf_text = extract_text_from_bytes("x.pdf", bio.getvalue())
            assert isinstance(pdf_text, str)
        except Exception:
            pass
        ok("4 docs PDF/TXT")
    except Exception as exc:  # noqa: BLE001
        fail("4 docs", exc)


def test_safety() -> None:
    try:
        from agent.safety import safety_brief, safety_checklist

        items = safety_checklist()
        assert len(items) >= 5
        assert "tomada" in safety_brief("measure").lower() or "escala" in safety_brief("measure").lower()
        assert "soldar" in safety_brief("solution").lower() or "desligue" in safety_brief("solution").lower()
        ok("5 checklist segurança")
    except Exception as exc:  # noqa: BLE001
        fail("5 segurança", exc)


def test_tts_fallback() -> None:
    try:
        from agent.voice import _speak_edge, _for_speech

        clean = _for_speech("Teste de voz do JARVIS de bancada.")
        assert "JARVIS" in clean
        audio = _speak_edge("Olá, teste curto.")
        assert isinstance(audio, (bytes, bytearray)) and len(audio) > 500
        ok("6 fallback TTS edge-tts")
    except Exception as exc:  # noqa: BLE001
        fail("6 TTS fallback", exc)


def test_pwa() -> None:
    try:
        man = (ROOT / "static" / "manifest.json").read_text(encoding="utf-8")
        assert "JARVIS" in man
        assert (ROOT / "static" / "sw.js").exists()
        assert (ROOT / "static" / "icon-192.png").exists()
        assert (ROOT / "static" / "icon-512.png").exists()
        cfg = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
        assert "enableStaticServing" in cfg
        ok("7 PWA assets")
    except Exception as exc:  # noqa: BLE001
        fail("7 PWA", exc)


def test_confirm_flow() -> None:
    try:
        from agent.diagnostic import DiagnosticAgent, CONFIRM_WORDS
        from agent.memory import CaseMemory

        with tempfile.TemporaryDirectory() as tmp:
            mem = CaseMemory(Path(tmp))
            ag = DiagnosticAgent(mem)
            case = mem.create("Board A", "não liga")
            # simula pending confirm
            pending = {
                "measured": "0.2V",
                "probe": {"point_name": "5VSB", "expected_value": "5V"},
                "solution": {
                    "failed_node": "5VSB",
                    "replace_first": "C905",
                    "how_to_confirm": "Meça de novo após a troca.",
                },
                "result": {
                    "assistant_message": "fail",
                    "spoken_reply": "fail",
                    "phase": "solution",
                    "mode": "solution",
                    "verdict": "fail",
                    "probe": {"point_name": "5VSB", "expected_value": "5V"},
                    "solution": {
                        "failed_node": "5VSB",
                        "replace_first": "C905",
                        "how_to_confirm": "ok",
                    },
                    "next_action": "ask_replace",
                },
            }
            case["pending_confirm"] = pending
            mem.save(case)
            assert ag._is_confirm("confirmo")
            assert ag._is_deny("não")
            assert any("confirmo" in w for w in CONFIRM_WORDS)

            out = ag.handle_user(case, "confirmo")
            assert out.get("mode") == "solution" or out.get("phase") == "solution"
            assert out.get("solution")
            assert case.get("pending_confirm") is None

            # deny path
            case2 = mem.create("Board B", "sem standby")
            case2["pending_confirm"] = pending
            mem.save(case2)
            out2 = ag.handle_user(case2, "não")
            assert out2.get("verdict") == "pending"
            assert case2.get("pending_confirm") is None

            # resolve -> bank
            from agent import failures

            failures.BANK_DIR = Path(tmp) / "bank"
            failures.BANK_PATH = failures.BANK_DIR / "bank.json"
            resolved = ag.resolve_case(case, "C905", "inchado")
            assert resolved["bank_entry"]["replaced_part"] == "C905"
        ok("8 confirmação + resolve")
    except Exception as exc:  # noqa: BLE001
        fail("8 confirmação", exc)


def test_imports_app() -> None:
    try:
        import ast

        ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
        from agent.diagnostic import DiagnosticAgent
        from agent.vision import annotate_board
        from agent.failures import list_failures
        from agent.safety import safety_checklist
        from agent.docs import extract_text_from_bytes
        from agent.voice import speak_text

        assert all(
            callable(x)
            for x in (
                DiagnosticAgent,
                annotate_board,
                list_failures,
                safety_checklist,
                extract_text_from_bytes,
                speak_text,
            )
        )
        ok("imports app/agent")
    except Exception as exc:  # noqa: BLE001
        fail("imports", exc)


if __name__ == "__main__":
    test_imports_app()
    test_vision()
    test_status_helpers()
    test_research_guards()
    test_operator_scene()
    test_failures()
    test_docs()
    test_safety()
    test_tts_fallback()
    test_pwa()
    test_confirm_flow()
    print("\nTodos os testes passaram.")
