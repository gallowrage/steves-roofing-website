"""Unit tests for Steve's Roofing desktop tools and calculation engine.

Tests:
1. Trigonometric secant pitch multiplier M = sqrt(1 + (p/12)^2) = 1/cos(theta).
2. Web Mercator ground resolution and scale calibration.
3. Shoelace area and perimeter polygon calculations.
4. Best Buy Metals procurement cut-lists (Tuff-Rib 36" and Standing Seam 16").
5. Steve's 1x4 Over-Shingle Purlin Recover framing math and $1,950 savings.
"""

import math
from typing import List, Tuple
import pytest

from desktop_tools.unified_roof_engine import (
    calculate_ground_resolution,
    calculate_scale_factor,
    calculate_pitch_multiplier,
    calculate_shoelace_area_and_perimeter,
    calculate_procurement_materials,
    calculate_recovery_savings,
    calculate_unified_bom,
)


def test_pitch_multiplier_rises():
    """Verify standard rises match exact square root secant formulas."""
    assert math.isclose(calculate_pitch_multiplier(0.0), 1.0, rel_tol=1e-5)
    assert math.isclose(calculate_pitch_multiplier(4.0), math.sqrt(1.0 + (4.0 / 12.0) ** 2), rel_tol=1e-5)
    assert math.isclose(calculate_pitch_multiplier(6.0), 1.118034, rel_tol=1e-5)
    assert math.isclose(calculate_pitch_multiplier(12.0), math.sqrt(2.0), rel_tol=1e-5)


def test_pitch_multiplier_degrees():
    """Verify degree calculation matches secant 1/cos(theta)."""
    assert math.isclose(calculate_pitch_multiplier(0.0, is_degrees=True), 1.0, rel_tol=1e-5)
    expected_30 = 1.0 / math.cos(math.radians(30.0))
    assert math.isclose(calculate_pitch_multiplier(30.0, is_degrees=True), expected_30, rel_tol=1e-5)
    expected_45 = 1.0 / math.cos(math.radians(45.0))
    assert math.isclose(calculate_pitch_multiplier(45.0, is_degrees=True), expected_45, rel_tol=1e-5)


def test_ground_resolution_and_scale():
    """Verify Web Mercator resolution and scale calculation."""
    # Latitude 35.5 (Asheville, NC), Zoom 19
    res = calculate_ground_resolution(35.5, 19)
    assert res > 0.0
    scale = calculate_scale_factor(35.5, 19)
    assert math.isclose(scale, 1.0 / res, rel_tol=1e-5)


def test_shoelace_area_and_perimeter():
    """Verify 2D flat footprint area and perimeter calculation."""
    # 20 ft by 30 ft rectangle at 5.0 px/ft
    # In pixels: (0,0), (100,0), (100,150), (0,150)
    pts: List[Tuple[float, float]] = [(0.0, 0.0), (100.0, 0.0), (100.0, 150.0), (0.0, 150.0)]
    area, perim = calculate_shoelace_area_and_perimeter(pts, px_per_ft=5.0)
    assert math.isclose(area, 600.0, rel_tol=1e-4)
    assert math.isclose(perim, 100.0, rel_tol=1e-4)


def test_best_buy_tuff_rib_procurement():
    """Verify 29ga Tuff-Rib panel calculation with 36in coverage and 1in ridge clearance."""
    res = calculate_procurement_materials(
        eave_ft=30.0,
        true_rake_ft=16.0,
        squares=5.0,
        panel_profile="ribbed_36",
        is_recover=True,
    )
    assert res["panel_quantity"] == 10
    # True Rake 16.0 + 2" eave overhang - 1" ridge clearance = 16.0833 ft
    expected_cut = round(16.0 + (1.0 / 12.0), 2)
    assert math.isclose(res["panel_cut_length_ft"], expected_cut, rel_tol=1e-2)
    assert res["purlin_rows"] == 9
    assert res["total_purlin_linear_ft"] == 270.0
    assert res["purlin_spacing_inches"] == 24


def test_best_buy_standing_seam_procurement():
    """Verify 26ga Standing Seam panel calculation with 16in coverage."""
    res = calculate_procurement_materials(
        eave_ft=30.0,
        true_rake_ft=16.0,
        squares=5.0,
        panel_profile="standing_seam_16",
        is_recover=False,
    )
    expected_qty = math.ceil(30.0 / 1.333)
    assert res["panel_quantity"] == expected_qty
    assert res["purlin_rows"] == 0
    assert res["total_purlin_linear_ft"] == 0.0
    assert res["purlin_spacing_inches"] == 0


def test_steves_recovery_savings():
    """Verify Steve's $1,950 over-shingle purlin recover competitive advantage."""
    savings_on = calculate_recovery_savings(is_recover=True)
    assert savings_on["net_savings"] == 1950.0
    assert savings_on["dumpster_fee"] == 0.0
    assert savings_on["demo_labor"] == 0.0

    savings_off = calculate_recovery_savings(is_recover=False)
    assert savings_off["net_savings"] == 0.0
    assert savings_off["dumpster_fee"] == 650.0
    assert savings_off["demo_labor"] == 1300.0


def test_unified_bom_pipeline():
    """Verify end-to-end unified BOM pipeline reconciliation."""
    bom = calculate_unified_bom(
        eave_length_ft=40.0,
        rake_length_2d_ft=16.0,
        flat_area_sqft=1200.0,
        pitch=6.0,
        panel_profile="ribbed_36",
        is_recover=True,
    )
    geom = bom["geometry"]
    assert math.isclose(geom["pitch_multiplier"], 1.118, abs_tol=0.001)
    assert math.isclose(geom["true_rake_ft"], 17.89, abs_tol=0.01)
    assert bom["procurement"]["panel_quantity"] == 14
    assert bom["recovery_advantage"]["net_savings"] == 1950.0
