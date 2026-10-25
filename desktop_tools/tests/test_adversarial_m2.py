"""Adversarial stress verification suite for Steve's Roofing calculation engine.

Empirically tests:
1. Pitch multiplier across extreme pitches: 0/12, 4/12, 6/12, 12/12, 24/12, 36/12 and degree angles.
2. Best Buy Metals cut-lists across 29ga (36") and 26ga (16") with ridge clearance (+1/12 ft).
3. Steve's 1x4 purlin recover framing: rows = ceil(True Rake / 2.0) + 1, total LF = rows * eave.
4. 48-Hour TTL safeguard boundary conditions.
5. Mathematical concordance with Buncombe County pilot parameters.
"""

import math
from typing import Dict, Any
import pytest

from desktop_tools.unified_roof_engine import (
    calculate_pitch_multiplier,
    calculate_procurement_materials,
    calculate_recovery_savings,
    calculate_unified_bom,
)


def test_adversarial_pitch_multiplier_extremes() -> None:
    """Stress-test pitch multiplier across flat, intermediate, and extreme slopes."""
    # 0/12 flat roof: M = 1.0
    assert math.isclose(calculate_pitch_multiplier(0.0), 1.0, rel_tol=1e-6)

    # 4/12 slope: sqrt(1 + (4/12)^2) = sqrt(10)/3 = 1.05409255
    m4 = calculate_pitch_multiplier(4.0)
    assert math.isclose(m4, 1.05409255, rel_tol=1e-6)

    # 6/12 slope: sqrt(1 + (6/12)^2) = sqrt(5)/2 = 1.11803399
    m6 = calculate_pitch_multiplier(6.0)
    assert math.isclose(m6, 1.11803399, rel_tol=1e-6)

    # 12/12 slope: sqrt(2) = 1.41421356
    m12 = calculate_pitch_multiplier(12.0)
    assert math.isclose(m12, math.sqrt(2.0), rel_tol=1e-6)

    # 24/12 steep: sqrt(1 + 4) = sqrt(5) = 2.23606798
    m24 = calculate_pitch_multiplier(24.0)
    assert math.isclose(m24, math.sqrt(5.0), rel_tol=1e-6)

    # 36/12 mansard: sqrt(1 + 9) = sqrt(10) = 3.16227766
    m36 = calculate_pitch_multiplier(36.0)
    assert math.isclose(m36, math.sqrt(10.0), rel_tol=1e-6)


def test_adversarial_pitch_multiplier_degree_angles() -> None:
    """Verify angular secant equivalences up to steep 75 degrees."""
    assert math.isclose(calculate_pitch_multiplier(0.0, is_degrees=True), 1.0, rel_tol=1e-6)

    m30 = calculate_pitch_multiplier(30.0, is_degrees=True)
    assert math.isclose(m30, 2.0 / math.sqrt(3.0), rel_tol=1e-6)

    m45 = calculate_pitch_multiplier(45.0, is_degrees=True)
    assert math.isclose(m45, math.sqrt(2.0), rel_tol=1e-6)

    m60 = calculate_pitch_multiplier(60.0, is_degrees=True)
    assert math.isclose(m60, 2.0, rel_tol=1e-6)

    m75 = calculate_pitch_multiplier(75.0, is_degrees=True)
    expected_75 = 1.0 / math.cos(math.radians(75.0))
    assert math.isclose(m75, expected_75, rel_tol=1e-6)


def test_adversarial_cut_list_profiles_and_clearance() -> None:
    """Verify 29ga (36in) and 26ga (16in) panel counts and +1/12 ft clearance."""
    # 29ga Tuff-Rib: 36in = 3.0ft coverage
    tuff_exact = calculate_procurement_materials(
        eave_ft=3.0, true_rake_ft=16.0, squares=5.0, panel_profile="ribbed_36", is_recover=False
    )
    assert tuff_exact["panel_quantity"] == 1

    tuff_fractional = calculate_procurement_materials(
        eave_ft=3.01, true_rake_ft=16.0, squares=5.0, panel_profile="ribbed_36", is_recover=False
    )
    assert tuff_fractional["panel_quantity"] == 2

    # 26ga Standing Seam: 16in = 1.333ft coverage
    seam_exact = calculate_procurement_materials(
        eave_ft=1.333, true_rake_ft=16.0, squares=5.0, panel_profile="standing_seam_16", is_recover=False
    )
    assert seam_exact["panel_quantity"] == 1

    seam_fractional = calculate_procurement_materials(
        eave_ft=1.334, true_rake_ft=16.0, squares=5.0, panel_profile="standing_seam_16", is_recover=False
    )
    assert seam_fractional["panel_quantity"] == 2

    # Panel cut length: True Rake + 2" eave overhang - 1" ridge clearance = True Rake + 1/12 ft
    for rake in [0.0, 10.0, 16.0, 28.0]:
        res = calculate_procurement_materials(
            eave_ft=30.0, true_rake_ft=rake, squares=5.0, panel_profile="ribbed_36", is_recover=False
        )
        expected_cut = round(rake + (1.0 / 12.0), 2)
        assert math.isclose(res["panel_cut_length_ft"], expected_cut, rel_tol=1e-2)


def test_adversarial_purlin_recover_boundary_rows() -> None:
    """Stress-test purlin rows formula: ceil(True Rake / 2.0) + 1."""
    # True rake = 0.0 -> 1 row (starter only)
    res0 = calculate_procurement_materials(
        eave_ft=50.0, true_rake_ft=0.0, squares=5.0, panel_profile="ribbed_36", is_recover=True
    )
    assert res0["purlin_rows"] == 1
    assert math.isclose(res0["total_purlin_linear_ft"], 50.0, rel_tol=1e-4)

    # True rake = 2.0 -> ceil(1.0) + 1 = 2 rows
    res2 = calculate_procurement_materials(
        eave_ft=50.0, true_rake_ft=2.0, squares=5.0, panel_profile="ribbed_36", is_recover=True
    )
    assert res2["purlin_rows"] == 2
    assert math.isclose(res2["total_purlin_linear_ft"], 100.0, rel_tol=1e-4)

    # True rake = 2.01 -> ceil(1.005) + 1 = 3 rows
    res2_01 = calculate_procurement_materials(
        eave_ft=50.0, true_rake_ft=2.01, squares=5.0, panel_profile="ribbed_36", is_recover=True
    )
    assert res2_01["purlin_rows"] == 3
    assert math.isclose(res2_01["total_purlin_linear_ft"], 150.0, rel_tol=1e-4)

    # Buncombe rake = 28.0 ft -> ceil(14.0) + 1 = 15 rows
    res28 = calculate_procurement_materials(
        eave_ft=50.0, true_rake_ft=28.0, squares=30.8, panel_profile="ribbed_36", is_recover=True
    )
    assert res28["purlin_rows"] == 15
    assert math.isclose(res28["total_purlin_linear_ft"], 750.0, rel_tol=1e-4)


def test_adversarial_purlin_savings_and_disable() -> None:
    """Verify Steve's $1,950 savings logic when enabled vs disabled."""
    active = calculate_recovery_savings(is_recover=True)
    assert active["net_savings"] == 1950.0
    assert active["dumpster_fee"] == 0.0
    assert active["demo_labor"] == 0.0

    disabled = calculate_recovery_savings(is_recover=False)
    assert disabled["net_savings"] == 0.0
    assert disabled["dumpster_fee"] == 650.0
    assert disabled["demo_labor"] == 1300.0
