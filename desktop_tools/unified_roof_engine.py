#!/usr/bin/env python3
"""
Unified RoofPro & Calebra Math Engine
------------------------------------
Unifies Steve's Desktop Calebra Canvas math (Shoelace area, pixel calibration, rise/run pitch)
with RoofPro SaaS Geodesic satellite trigonometry and Best Buy Metals fabrication standards.

Features:
1. Mathematical equivalence between rise/run (sqrt(1 + (p/12)^2)) and secant (1/cos(theta)).
2. Automated Web Mercator Ground Resolution (eliminates manual pixel guessing):
   Resolution (ft/px) = 513592.6 * cos(lat) / 2^zoom
3. Best Buy Metals Fabrication BOM:
   - Cut length: True Rake + 2" eave overhang - 1" ridge clearance (+1/12 ft)
   - 24" on-center purlin rows for over-shingle recovery
4. Recovery cost advantage: Highlights dumpster fee zeroing (-$1,950 savings).
5. Cyclomatic complexity <= 10 per function to meet deterministic VDD standards.
"""

import math
from typing import Any, Dict, List, Optional, Tuple


def calculate_ground_resolution(latitude_deg: float, zoom_level: int) -> float:
    """
    Computes ground resolution in feet per pixel for Web Mercator satellite tiles.
    Resolution (ft/px) = (513592.6 * cos(latitude)) / (2^zoom)
    """
    lat_rad = math.radians(latitude_deg)
    return (513592.6 * math.cos(lat_rad)) / (2.0 ** zoom_level)


def calculate_scale_factor(latitude_deg: float, zoom_level: int) -> float:
    """
    Computes Steve's Calebra scale factor C (pixels per foot) from geographic coordinates.
    Scale C (px/ft) = 1 / Resolution
    """
    res = calculate_ground_resolution(latitude_deg, zoom_level)
    return 1.0 / res if res > 0 else 5.0


def calculate_pitch_multiplier(pitch: float, is_degrees: bool = False) -> float:
    """
    Calculates 3D geometric expansion multiplier M.
    Equivalent forms: M = 1 / cos(theta) = sqrt(1 + (pitch/12)^2).
    """
    if is_degrees:
        rad = math.radians(pitch)
        cos_val = math.cos(rad)
        return 1.0 / cos_val if cos_val > 0 else 1.0
    return math.sqrt(1.0 + (pitch / 12.0) ** 2)


def calculate_shoelace_area_and_perimeter(
    points: List[Tuple[float, float]],
    px_per_ft: float,
) -> Tuple[float, float]:
    """
    Calculates flat 2D area (sq ft) and perimeter (ft) from screen polygon coordinates.
    """
    n = len(points)
    if n < 3 or px_per_ft <= 0:
        return 0.0, 0.0

    area_px = 0.5 * abs(sum(
        points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
        for i in range(n)
    ))

    perimeter_px = sum(
        math.dist(points[i], points[(i + 1) % n])
        for i in range(n)
    )

    flat_area_sqft = area_px / (px_per_ft ** 2)
    perimeter_ft = perimeter_px / px_per_ft
    return flat_area_sqft, perimeter_ft


def calculate_procurement_materials(
    eave_ft: float,
    true_rake_ft: float,
    squares: float,
    panel_profile: str,
    is_recover: bool,
) -> Dict[str, Any]:
    """Computes panel counts, cut lengths, purlin framing, and trim sticks."""
    coverage_width = 3.0 if panel_profile == "ribbed_36" else 1.333
    panel_qty = math.ceil(eave_ft / coverage_width)
    panel_cut_ft = true_rake_ft + (1.0 / 12.0)  # +2" eave overhang, -1" ridge clearance

    purlin_rows = math.ceil(true_rake_ft / 2.0) + 1 if is_recover else 0
    purlin_lf = purlin_rows * eave_ft

    drip_edge_sticks = math.ceil(eave_ft / 10.0)
    ridge_cap_sticks = math.ceil(eave_ft / 10.0)
    fastener_boxes = max(1, math.ceil(squares / 5.0))

    return {
        "panel_profile": "29ga Tuff-Rib (36in)" if panel_profile == "ribbed_36" else "26ga Standing Seam (16in)",
        "panel_quantity": panel_qty,
        "panel_cut_length_ft": round(panel_cut_ft, 2),
        "purlin_rows": purlin_rows,
        "total_purlin_linear_ft": round(purlin_lf, 2),
        "purlin_spacing_inches": 24 if is_recover else 0,
        "drip_edge_10ft_sticks": drip_edge_sticks,
        "ridge_cap_10ft_sticks": ridge_cap_sticks,
        "fastener_boxes": fastener_boxes,
    }


def calculate_recovery_savings(is_recover: bool) -> Dict[str, float]:
    """Calculates Steve's competitive cost advantage over tear-off reroofing."""
    if not is_recover:
        return {"dumpster_fee": 650.0, "demo_labor": 1300.0, "net_savings": 0.0}

    return {
        "dumpster_fee": 0.0,
        "demo_labor": 0.0,
        "net_savings": 1950.0,  # $650 dumpster + $1,300 demo labor saved
    }


def calculate_unified_bom(
    eave_length_ft: float,
    rake_length_2d_ft: float,
    flat_area_sqft: float,
    pitch: float = 6.0,
    is_degrees: bool = False,
    panel_profile: str = "ribbed_36",
    is_recover: bool = True,
    waste_pct: float = 10.0,
) -> Dict[str, Any]:
    """
    Unified BOM engine reconciling Steve's Calebra and RoofPro SaaS models.
    """
    multiplier = calculate_pitch_multiplier(pitch, is_degrees)
    true_rake = rake_length_2d_ft * multiplier
    true_area = flat_area_sqft * multiplier
    order_area = true_area * (1.0 + (waste_pct / 100.0))
    squares = order_area / 100.0

    procurement = calculate_procurement_materials(
        eave_ft=eave_length_ft,
        true_rake_ft=true_rake,
        squares=squares,
        panel_profile=panel_profile,
        is_recover=is_recover,
    )

    savings = calculate_recovery_savings(is_recover)

    return {
        "geometry": {
            "pitch_multiplier": round(multiplier, 4),
            "true_rake_ft": round(true_rake, 2),
            "true_pitched_area_sqft": round(true_area, 2),
            "order_area_sqft": round(order_area, 2),
            "roof_squares": round(squares, 2),
        },
        "procurement": procurement,
        "recovery_advantage": savings,
    }
