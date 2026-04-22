"""Generate CS-Bench-style family-category distribution figure for BenchCAD.

Output: static/images/family_distribution.svg
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Wedge, Circle

OUT = Path(__file__).resolve().parent / "static/images/family_distribution.svg"

STANDARDS = {
    "bolt": "ISO 4014", "pan_head_screw": "ISO 14583", "hex_nut": "ISO 4032",
    "wing_nut": "DIN 315", "tee_nut": "DIN 1624", "washer": "ISO 7089",
    "rivet": "DIN 660", "eyebolt": "DIN 580", "u_bolt": "DIN 3570",
    "hex_standoff": "DIN 6334", "wall_anchor": "DIN 7990",
    "grommet": "DIN 71412", "clevis_pin": "ISO 2341", "dowel_pin": "ISO 2338",
    "cotter_pin": "ISO 1234", "taper_pin": "ISO 2339", "circlip": "DIN 471",
    "parallel_key": "DIN 6885", "knob": "DIN 6336", "ball_knob": "DIN 319",
    "lobed_knob": "DIN 6336", "pull_handle": "DIN 3124",
    "spur_gear": "ISO 1328", "helical_gear": "ISO 1328",
    "bevel_gear": "ISO 23509", "worm_screw": "ISO 1122",
    "sprocket": "ISO 606", "double_simplex_sprocket": "ISO 606",
    "pulley": "ISO 4183", "handwheel": "DIN 950", "spline_hub": "ISO 14",
    "hollow_tube": "ISO 4200", "dog_bone": "ISO 527",
    "twisted_drill": "DIN 338", "spacer_ring": "DIN 988",
    "turnbuckle": "DIN 1480", "clevis": "DIN 71752", "j_hook": "DIN 1480",
    "coil_spring": "DIN 2088", "torsion_spring": "DIN 2088",
    "bellows": "DIN 4820",
    "shaft_collar": "DIN 705", "flat_link": "DIN 763", "hinge": "DIN 3601",
    "enclosure": "IEC 60529", "bearing_retainer_cap": "DIN 625",
    "dome_cap": "DIN 1587", "chair": "EN 1729", "table": "EN 527",
    "pipe_flange": "DIN 2501", "round_flange": "DIN 2501",
    "t_pipe_fitting": "DIN 2605", "pipe_elbow": "DIN 2605",
    "duct_elbow": "DIN 24147", "venturi_tube": "ISO 5167",
    "nozzle": "DIN 24154", "grease_nipple": "DIN 71412",
    "threaded_adapter": "ISO 228",
    "i_beam": "EN 10034", "u_channel": "EN 10279", "t_slot_rail": "DIN 1013",
    "connector_faceplate": "IEC 60603",
}

CATEGORIES = {
    "Fasteners & Hardware": [
        "bolt", "pan_head_screw", "hex_nut", "wing_nut", "tee_nut",
        "washer", "rivet", "eyebolt", "u_bolt", "hex_standoff",
        "standoff", "pcb_standoff_plate", "wall_anchor", "grommet",
        "snap_clip", "clevis_pin", "dowel_pin", "cotter_pin", "taper_pin",
        "circlip", "parallel_key", "knob", "ball_knob", "lobed_knob",
        "pull_handle", "turnbuckle", "clevis", "j_hook",
    ],
    "Motion & Transmission": [
        "spur_gear", "helical_gear", "bevel_gear", "worm_screw",
        "sprocket", "double_simplex_sprocket", "pulley", "handwheel",
        "cam", "ratchet_sector", "impeller", "propeller", "spline_hub",
        "shaft_collar", "stepped_shaft", "hollow_tube", "tapered_boss",
        "lathe_turned_part", "dog_bone", "twisted_drill", "spacer_ring",
        "connecting_rod", "piston", "torus_link",
        "coil_spring", "torsion_spring",
    ],
    "Structural & Mounting": [
        "l_bracket", "z_bracket", "gusseted_bracket", "twisted_bracket",
        "mounting_angle", "mounting_plate", "slotted_plate",
        "keyhole_plate", "locator_block", "pillow_block", "rib_plate",
        "flat_link", "hinge", "dovetail_slide",
        "i_beam", "u_channel", "t_slot_rail", "rect_frame", "cruciform",
    ],
    "Fluid & Process": [
        "pipe_flange", "round_flange", "t_pipe_fitting", "pipe_elbow",
        "duct_elbow", "venturi_tube", "nozzle", "grease_nipple",
        "threaded_adapter", "manifold_block", "bellows",
    ],
    "Panels & Sheet Metal": [
        "waffle_plate", "vented_panel", "mesh_panel", "wire_grid",
        "cable_routing_panel", "connector_faceplate", "sheet_metal_tray",
        "star_blank",
    ],
    "Enclosures & Product Parts": [
        "enclosure", "fan_shroud", "heat_sink", "motor_end_cap",
        "bearing_retainer_cap", "dome_cap", "battery_holder", "phone_stand",
        "chair", "table", "bucket", "gridfinity_bin",
        "hex_key_organizer", "capsule",
    ],
}

# 6 distinct hues
COLORS = {
    "Fasteners & Hardware":       "#7c3aed",
    "Motion & Transmission":      "#059669",
    "Structural & Mounting":      "#2563eb",
    "Fluid & Process":            "#0891b2",
    "Panels & Sheet Metal":       "#d97706",
    "Enclosures & Product Parts": "#db2777",
}

# Two-line breaks for upright readability inside sectors
CAT_LABELS = {
    "Fasteners & Hardware":       "Fasteners &\nHardware",
    "Motion & Transmission":      "Motion &\nTransmission",
    "Structural & Mounting":      "Structural &\nMounting",
    "Fluid & Process":            "Fluid &\nProcess",
    "Panels & Sheet Metal":       "Panels &\nSheet Metal",
    "Enclosures & Product Parts": "Enclosures &\nProduct Parts",
}


def lighten(hex_color: str, amount: float = 0.35) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def main() -> None:
    total = sum(len(v) for v in CATEGORIES.values())
    assert total == 106, f"expected 106, got {total}"

    # Wide canvas for word-cloud margins on both sides
    fig, ax = plt.subplots(figsize=(22, 14))
    XL, YL = 11.0, 7.0
    ax.set_xlim(-XL, XL)
    ax.set_ylim(-YL, YL)
    ax.set_aspect("equal")
    ax.set_axis_off()

    R_HUB = 1.45
    R_CAT_IN = R_HUB
    R_CAT_OUT = 3.3
    R_FAM_OUT = 3.8  # thin outer family color band

    # Assign each category a sector; start at 90° (top), go clockwise
    cat_angles: dict[str, tuple[float, float]] = {}
    angle_deg = 90.0
    for cat, members in CATEGORIES.items():
        n = len(members)
        span_deg = 360.0 * n / total
        start = angle_deg - span_deg
        end = angle_deg
        cat_angles[cat] = (start, end)

        # Category wedge
        ax.add_patch(Wedge((0, 0), R_CAT_OUT, start, end,
                           width=R_CAT_OUT - R_CAT_IN,
                           facecolor=COLORS[cat],
                           edgecolor="white", linewidth=2, zorder=3))

        # Thin outer family colour band (one slice per family, no label)
        fam_color = lighten(COLORS[cat], 0.28)
        sub_span = span_deg / n
        for i in range(n):
            sub_start = start + i * sub_span
            sub_end = sub_start + sub_span
            ax.add_patch(Wedge((0, 0), R_FAM_OUT, sub_start, sub_end,
                               width=R_FAM_OUT - R_CAT_OUT,
                               facecolor=fam_color,
                               edgecolor="white", linewidth=0.6, zorder=3))

        # Category label — rotated to follow the arc tangent (CS-Bench style)
        mid_deg = (start + end) / 2
        mid_rad = math.radians(mid_deg)
        label_r = (R_CAT_IN + R_CAT_OUT) / 2
        lx = label_r * math.cos(mid_rad)
        ly = label_r * math.sin(mid_rad)
        # Tangent to circle: rotation = angle − 90°; flip when upside-down
        rot = mid_deg - 90.0
        if rot > 90.0:
            rot -= 180.0
        elif rot < -90.0:
            rot += 180.0
        # Font size by sector span — big sectors get big labels
        fs = 13.0 + min(4.5, span_deg / 14)
        ax.text(lx, ly, CAT_LABELS[cat],
                ha="center", va="center",
                rotation=rot, rotation_mode="anchor",
                fontsize=fs, fontweight="bold",
                color="white", zorder=5)

        angle_deg -= span_deg

    # Central hub
    ax.add_patch(Circle((0, 0), R_HUB, facecolor="white",
                        edgecolor="#1f2937", linewidth=1.8, zorder=4))
    std_count = len({v for v in STANDARDS.values() if v})
    ax.text(0, 0.58, "BenchCAD", ha="center", va="center",
            fontsize=27, fontweight="bold", color="#111827", zorder=6)
    ax.text(0, 0.15, "106 families", ha="center", va="center",
            fontsize=15, color="#1f2937", zorder=6)
    ax.text(0, -0.22, "6 categories", ha="center", va="center",
            fontsize=14, color="#4b5563", zorder=6)
    ax.text(0, -0.62, f"{std_count} ISO / DIN / EN", ha="center", va="center",
            fontsize=14, color="#4b5563", zorder=6)

    # ---- Word cloud of family names around the wheel ----
    rng = random.Random(7)
    placed: list[tuple[float, float, float, float]] = []

    def overlaps(x: float, y: float, w: float, h: float) -> bool:
        # keep clear of the wheel
        if math.hypot(x, y) - max(w, h) * 0.5 < R_FAM_OUT + 0.25:
            return True
        for ex, ey, ew, eh in placed:
            if abs(x - ex) * 2 < (w + ew + 0.12) and abs(y - ey) * 2 < (h + eh + 0.08):
                return True
        return False

    all_fams: list[tuple[str, str]] = [
        (fam, cat) for cat, mems in CATEGORIES.items() for fam in mems
    ]

    # Non-uniform 3-tier font sizes — dramatic variation like a word cloud
    fs_for_fam: dict[str, float] = {}
    for fam, _cat in all_fams:
        tier = rng.random()
        if tier < 0.15:                 # ~16 big words
            fs_for_fam[fam] = rng.uniform(20.0, 25.0)
        elif tier < 0.55:               # ~42 medium
            fs_for_fam[fam] = rng.uniform(14.0, 18.0)
        else:                           # ~48 small
            fs_for_fam[fam] = rng.uniform(10.0, 13.0)

    # Biggest first → hardest to place; longer strings next
    all_fams.sort(key=lambda p: (-fs_for_fam[p[0]], -len(p[0])))

    unplaced: list[tuple[str, str]] = []
    for fam, cat in all_fams:
        label = fam.replace("_", " ")
        fs = fs_for_fam[fam]
        # approximate text bbox (data units ≈ inches here with equal aspect)
        w = len(label) * fs * 0.0085
        h = fs * 0.018

        start, end = cat_angles[cat]
        mid_rad = math.radians((start + end) / 2)
        half_span = math.radians(max((end - start) / 2, 12))

        done = False
        for _ in range(500):
            r = rng.uniform(R_FAM_OUT + 0.55, min(XL, YL) * 1.1)
            ang = mid_rad + rng.uniform(-half_span * 1.5, half_span * 1.5)
            x = r * math.cos(ang)
            y = r * math.sin(ang)
            if abs(x) + w / 2 > XL - 0.1 or abs(y) + h / 2 > YL - 0.1:
                continue
            if overlaps(x, y, w, h):
                continue
            placed.append((x, y, w, h))
            ax.text(x, y, label, ha="center", va="center",
                    fontsize=fs, color=COLORS[cat],
                    fontweight="medium", zorder=2)
            done = True
            break
        if not done:
            unplaced.append((fam, cat))

    # Fallback pass: try anywhere in frame (outside wheel) for leftovers
    for fam, cat in unplaced:
        label = fam.replace("_", " ")
        # smaller fallback size so packing is easier
        fs = min(fs_for_fam[fam], 12.5)
        w = len(label) * fs * 0.0085
        h = fs * 0.018
        done = False
        for _ in range(1500):
            x = rng.uniform(-XL + w / 2 + 0.1, XL - w / 2 - 0.1)
            y = rng.uniform(-YL + h / 2 + 0.1, YL - h / 2 - 0.1)
            if overlaps(x, y, w, h):
                continue
            placed.append((x, y, w, h))
            ax.text(x, y, label, ha="center", va="center",
                    fontsize=fs, color=COLORS[cat],
                    fontweight="medium", zorder=2)
            done = True
            break
        if not done:
            print(f"warn: could not place '{fam}'")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, format="svg", bbox_inches="tight",
                pad_inches=0.15, transparent=True)
    print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
