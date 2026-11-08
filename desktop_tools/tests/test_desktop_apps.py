"""Unit tests for Steve's Roofing desktop workflow modules.

Covers headless state transitions, BOM calculations, canvas geometry,
serialization/deserialization, and API worker handling across:
- desktop_tools.steve_roofing_unified (UnifiedRoofingOS)
- desktop_tools.steve_roofing_qac (SteveRoofingApp)
- desktop_tools.quote_generatr_ai (AIQuoteApp)
"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock, patch

from desktop_tools import quote_generatr_ai
from desktop_tools import steve_roofing_qac
from desktop_tools import steve_roofing_unified


class DummyWidget:
    """Lightweight headless mock for CTkEntry, CTkTextbox, CTkLabel, CTkButton, and CTkComboBox."""

    def __init__(self, initial_text: str = "") -> None:
        self.value = initial_text
        self.config_state: Dict[str, Any] = {}

    def get(self, *args: Any) -> str:
        return self.value

    def set(self, val: str) -> None:
        self.value = str(val)

    def insert(self, index: Any, text: str) -> None:
        self.value = text

    def delete(self, start: Any, end: Any = None) -> None:
        self.value = ""

    def configure(self, **kwargs: Any) -> None:
        self.config_state.update(kwargs)


class DummyCanvas:
    """Headless mock for tkinter.Canvas."""

    def __init__(self) -> None:
        self.items: List[Tuple[str, Tuple[Any, ...], Dict[str, Any]]] = []
        self._next_id = 1

    def _add(self, kind: str, *args: Any, **kwargs: Any) -> int:
        item_id = self._next_id
        self._next_id += 1
        self.items.append((kind, args, kwargs))
        return item_id

    def create_oval(self, *args: Any, **kwargs: Any) -> int:
        return self._add("oval", *args, **kwargs)

    def create_line(self, *args: Any, **kwargs: Any) -> int:
        return self._add("line", *args, **kwargs)

    def create_polygon(self, *args: Any, **kwargs: Any) -> int:
        return self._add("polygon", *args, **kwargs)

    def create_image(self, *args: Any, **kwargs: Any) -> int:
        return self._add("image", *args, **kwargs)

    def delete(self, tag: str) -> None:
        if tag == "all":
            self.items.clear()

    def winfo_width(self) -> int:
        return 700

    def winfo_height(self) -> int:
        return 520


def _build_headless_unified_app() -> steve_roofing_unified.UnifiedRoofingOS:
    """Constructs a UnifiedRoofingOS instance with headless widget doubles."""
    app = object.__new__(steve_roofing_unified.UnifiedRoofingOS)
    app.quote_ready = False
    app.accepted = False
    app.contract_signed = False
    app.quote_drafted_at = None
    app.accepted_at = None
    app.contract_signed_at = None
    app.audit_log = []

    app.points = []
    app.point_markers = []
    app.polygon_id = None
    app.closed = False
    app.bg_photo = None
    app.current_zoom = 19

    app.pitch_multipliers = {
        "Flat (0/12)": 1.000,
        "Moderate (6/12)": 1.118,
    }
    app.pricing_table = {
        "26ga Standing Seam (16in panel)": {"unit_cost_sqft": 3.45, "nominal_width_in": 16.0},
        "29ga Tuff-Rib / Agricultural (36in)": {"unit_cost_sqft": 2.15, "nominal_width_in": 36.0},
    }

    app.entry_address = DummyWidget("690 Dogwood Lane, Buncombe County, NC")
    app.gemini_key_entry = DummyWidget("test-key")
    app.maps_key_entry = DummyWidget("")
    app.txt_notes = DummyWidget("Sample customer notes")
    app.txt_quote_preview = DummyWidget("Initial quote preview")
    app.customer_signature_entry = DummyWidget("")
    app.contractor_signature_entry = DummyWidget("")
    app.scale_var = DummyWidget("5.0")
    app.pitch_combo = DummyWidget("Moderate (6/12)")
    app.profile_combo = DummyWidget("26ga Standing Seam (16in panel)")
    app.overlap_var = DummyWidget("4.0")
    app.waste_combo = DummyWidget("10%")

    app.lbl_quote = DummyWidget()
    app.lbl_accept = DummyWidget()
    app.lbl_contract = DummyWidget()
    app.btn_gen_quote = DummyWidget()
    app.btn_accept = DummyWidget()
    app.btn_sign = DummyWidget()
    app.btn_fetch_map = DummyWidget()
    app.status_card = DummyWidget()
    app.status_text = DummyWidget()
    app.txt_bom = DummyWidget()
    app.lbl_grand_total = DummyWidget()
    app.txt_codes = DummyWidget("=== LOCKED ===")
    app.txt_phases = DummyWidget("=== LOCKED ===")
    app.canvas = DummyCanvas()
    app.after = lambda delay, fn, *args: fn(*args)
    return app


def test_unified_canvas_and_bom_calculation() -> None:
    """Verify canvas pin placement, polygon closing, and real-time BOM calculation."""
    app = _build_headless_unified_app()
    app.recalculate_bom()
    assert app.lbl_grand_total.config_state["text"] == "ESTIMATED TOTAL: $0.00"

    # Click 4 corners of a 100x150 px rectangle (20x30 ft at 5 px/ft = 600 sq ft flat)
    for x, y in [(0, 0), (100, 0), (100, 150), (0, 150)]:
        app.on_canvas_click(SimpleNamespace(x=x, y=y))

    assert len(app.points) == 4
    app.close_polygon()
    assert app.closed is True
    assert app.polygon_id is not None
    assert "MEASUREMENT SPECIFICATIONS:" in app.txt_bom.get()
    assert app.lbl_grand_total.config_state["text"] != "ESTIMATED TOTAL: $0.00"

    # Clicks ignored once closed
    app.on_canvas_click(SimpleNamespace(x=50, y=50))
    assert len(app.points) == 4

    # Clear canvas resets state
    app.clear_canvas()
    assert len(app.points) == 0
    assert app.closed is False
    assert app.lbl_grand_total.config_state["text"] == "ESTIMATED TOTAL: $0.00"


def test_unified_bom_invalid_inputs_and_overlap_bounds() -> None:
    """Verify BOM calculation gracefully handles invalid scale or overlap values."""
    app = _build_headless_unified_app()
    app.points = [(0, 0), (100, 0), (100, 100)]

    app.scale_var.set("invalid")
    app.recalculate_bom()

    app.scale_var.set("-1.0")
    app.recalculate_bom()

    app.scale_var.set("5.0")
    app.overlap_var.set("20.0")  # >= 16.0 nominal width
    app.recalculate_bom()


def test_unified_qac_workflow_transitions_and_reset() -> None:
    """Verify full Stage 1 QAC gate progression, signature validation, and workflow reset."""
    app = _build_headless_unified_app()

    with patch.object(steve_roofing_unified.messagebox, "showwarning") as mock_warn, \
         patch.object(steve_roofing_unified.messagebox, "showinfo") as mock_info:
        # Cannot accept before quote ready
        app.action_mark_accepted()
        assert mock_warn.called

        # Render successful quote result
        app._render_quote_result("Generated Proposal Content", True)
        assert app.quote_ready is True
        assert app.btn_accept.config_state["state"] == "normal"

        # Missing customer signature blocks acceptance
        app.action_mark_accepted()
        assert app.accepted is False

        # Provide customer signature and accept
        app.customer_signature_entry.set("David Galloway")
        app.action_mark_accepted()
        assert app.accepted is True
        assert app.btn_sign.config_state["state"] == "normal"

        # Missing contractor signature blocks contract signing
        app.action_sign_contract()
        assert app.contract_signed is False

        # Provide contractor signature and sign
        app.contractor_signature_entry.set("Steve")
        app.action_sign_contract()
        assert app.contract_signed is True
        assert "GREEN LIGHT" in app.status_text.config_state["text"]
        assert "NORTH CAROLINA RESIDENTIAL CODE" in app.txt_codes.get()
        assert "PHASE 1: TEAR-OFF" in app.txt_phases.get()
        assert mock_info.called

        # Reset returns gate to locked red state
        app.reset_workflow()
        assert app.quote_ready is False
        assert app.accepted is False
        assert app.contract_signed is False
        assert len(app.audit_log) == 0
        assert "LOCKED (RED)" in app.status_text.config_state["text"]


def test_unified_save_load_and_export_job(tmp_path: Path) -> None:
    """Verify job JSON persistence, restoration, and text record export."""
    app = _build_headless_unified_app()
    app._render_quote_result("Proposal body", True)
    app.customer_signature_entry.set("David Galloway")
    with patch.object(steve_roofing_unified.messagebox, "showinfo"):
        app.action_mark_accepted()
        app.contractor_signature_entry.set("Steve")
        app.action_sign_contract()

    app.points = [(10, 10), (110, 10), (110, 110)]
    app.closed = True

    json_file = tmp_path / "job.json"
    txt_file = tmp_path / "job.txt"

    with patch.object(steve_roofing_unified.filedialog, "asksaveasfilename", return_value=str(json_file)), \
         patch.object(steve_roofing_unified.messagebox, "showinfo"):
        app.save_job()

    assert json_file.exists()
    saved_payload = json.loads(json_file.read_text(encoding="utf-8"))
    assert saved_payload["contract_signed"] is True

    # Reset and reload from disk
    app.reset_workflow()
    app.clear_canvas()
    with patch.object(steve_roofing_unified.filedialog, "askopenfilename", return_value=str(json_file)), \
         patch.object(steve_roofing_unified.messagebox, "showinfo"):
        app.load_job()

    assert app.contract_signed is True
    assert len(app.points) == 3
    assert app.closed is True

    # Export text record
    with patch.object(steve_roofing_unified.filedialog, "asksaveasfilename", return_value=str(txt_file)), \
         patch.object(steve_roofing_unified.messagebox, "showinfo"):
        app.export_job_record()

    assert txt_file.exists()
    assert "STEVE'S ROOFING - JOB RECORD" in txt_file.read_text(encoding="utf-8")


def test_unified_read_job_file_errors(tmp_path: Path) -> None:
    """Verify invalid JSON or non-dict job files show error and return None."""
    app = _build_headless_unified_app()
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("[1, 2, 3]", encoding="utf-8")

    with patch.object(steve_roofing_unified.messagebox, "showerror") as mock_err:
        assert app._read_job_file(str(bad_file)) is None
        assert mock_err.called


def test_unified_zoom_and_failed_quote() -> None:
    """Verify zoom clamping and failed AI quote handling."""
    app = _build_headless_unified_app()
    with patch.object(app, "start_satellite_fetch") as mock_fetch:
        app.adjust_zoom(5)
        assert app.current_zoom == 21
        app.adjust_zoom(-10)
        assert app.current_zoom == 16
        assert mock_fetch.call_count == 2

    app._render_quote_result("[QUOTE FAILED]", False)
    assert app.quote_ready is False
    assert app.btn_accept.config_state["state"] == "disabled"


def test_steve_roofing_qac_app_workflow() -> None:
    """Verify SteveRoofingApp (steve_roofing_qac.py) state machine and reset."""
    app = object.__new__(steve_roofing_qac.SteveRoofingApp)
    app.quote_ready = False
    app.accepted = False
    app.contract_signed = False
    app.txt_notes = DummyWidget("Customer: Marcus Vance")
    app.lbl_quote = DummyWidget()
    app.lbl_accept = DummyWidget()
    app.lbl_contract = DummyWidget()
    app.btn_generate_quote = DummyWidget()
    app.btn_customer_accept = DummyWidget()
    app.btn_sign_contract = DummyWidget()
    app.status_card = DummyWidget()
    app.status_text = DummyWidget()
    app.txt_codes = DummyWidget()
    app.txt_materials = DummyWidget()

    with patch.object(steve_roofing_qac.messagebox, "showinfo") as mock_info, \
         patch.object(steve_roofing_qac.messagebox, "showwarning") as mock_warn:
        app.txt_notes.set("")
        app.action_draft_quote()
        assert mock_warn.called
        assert app.quote_ready is False

        app.txt_notes.set("Field log notes")
        app.action_draft_quote()
        assert app.quote_ready is True

        app.action_mark_accepted()
        assert app.accepted is True

        app.action_sign_contract()
        assert app.contract_signed is True
        assert "GREEN LIGHT" in app.status_text.config_state["text"]
        assert "NORTH CAROLINA RESIDENTIAL CODE" in app.txt_codes.get()
        assert "PHASE 1: TEAR-OFF" in app.txt_materials.get()
        assert mock_info.called

        app.reset_workflow()
        assert app.quote_ready is False
        assert app.accepted is False
        assert app.contract_signed is False
        assert "LOCKED (RED)" in app.status_text.config_state["text"]


def test_quote_generatr_ai_validation_and_render() -> None:
    """Verify AIQuoteApp input validation and result rendering."""
    app = object.__new__(quote_generatr_ai.AIQuoteApp)
    app.txt_input = DummyWidget("David Galloway field notes")
    app.entry_key = DummyWidget("")
    app.txt_output = DummyWidget("")
    app.btn_generate = DummyWidget()
    app.after = lambda delay, fn, *args: fn(*args)

    with patch.object(quote_generatr_ai.messagebox, "showwarning") as mock_warn:
        # Missing API key
        app.start_ai_generation()
        assert mock_warn.call_count == 1

        # Missing notes
        app.entry_key.set("fake-key")
        app.txt_input.set("")
        app.start_ai_generation()
        assert mock_warn.call_count == 2

    # Render result restores button state and populates output
    app._render_result("Final AI Quote Text")
    assert app.txt_output.get() == "Final AI Quote Text"
    assert app.btn_generate.config_state["state"] == "normal"

    # Verify fallback when GENAI_SDK is None
    app.txt_input.set("Valid notes")
    with patch.object(quote_generatr_ai, "GENAI_SDK", None):
        app.start_ai_generation()
        assert "[ERROR] SDK Not Found" in app.txt_output.get()
        app._run_generation("fake-key", "Valid notes")
        assert "[ERROR] SDK Not Available" in app.txt_output.get()
