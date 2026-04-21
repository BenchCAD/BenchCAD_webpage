"""Generate family-category distribution wheel for the BenchCAD site.

Output: website/static/images/family_distribution.svg
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUT = Path(__file__).resolve().parent / "static/images/family_distribution.svg"

# Primary ISO / DIN / EN standard per family (blank if no direct standard).
STANDARDS = {
    # Fasteners
    "bolt": "ISO 4014", "pan_head_screw": "ISO 14583", "hex_nut": "ISO 4032",
    "wing_nut": "DIN 315", "tee_nut": "DIN 1624", "washer": "ISO 7089",
    "rivet": "DIN 660", "eyebolt": "DIN 580", "u_bolt": "DIN 3570",
    "hex_standoff": "DIN 6334", "wall_anchor": "DIN 7990",
    "grommet": "DIN 71412", "clevis_pin": "ISO 2341", "dowel_pin": "ISO 2338",
    "cotter_pin": "ISO 1234", "taper_pin": "ISO 2339", "circlip": "DIN 471",
    "parallel_key": "DIN 6885", "knob": "DIN 6336", "ball_knob": "DIN 319",
    "lobed_knob": "DIN 6336", "pull_handle": "DIN 3124",
    # Gears & Transmission
    "spur_gear": "ISO 1328", "helical_gear": "ISO 1328",
    "bevel_gear": "ISO 23509", "worm_screw": "ISO 1122",
    "sprocket": "ISO 606", "double_simplex_sprocket": "ISO 606",
    "pulley": "ISO 4183", "handwheel": "DIN 950", "spline_hub": "ISO 14",
    # Shafts & Revolved
    "hollow_tube": "ISO 4200", "dog_bone": "ISO 527",
    "twisted_drill": "DIN 338", "spacer_ring": "DIN 988",
    "turnbuckle": "DIN 1480", "clevis": "DIN 71752", "j_hook": "DIN 1480",
    # Springs
    "coil_spring": "DIN 2088", "torsion_spring": "DIN 2088",
    "bellows": "DIN 4820",
    # Brackets & Mounts
    "shaft_collar": "DIN 705", "flat_link": "DIN 763", "hinge": "DIN 3601",
    # Housings
    "enclosure": "IEC 60529", "bearing_retainer_cap": "DIN 625",
    "dome_cap": "DIN 1587", "chair": "EN 1729", "table": "EN 527",
    # Piping
    "pipe_flange": "DIN 2501", "round_flange": "DIN 2501",
    "t_pipe_fitting": "DIN 2605", "pipe_elbow": "DIN 2605",
    "duct_elbow": "DIN 24147", "venturi_tube": "ISO 5167",
    "nozzle": "DIN 24154", "grease_nipple": "DIN 71412",
    "threaded_adapter": "ISO 228",
    # Panels & Structural
    "i_beam": "EN 10034", "u_channel": "EN 10279", "t_slot_rail": "DIN 1013",
    "connector_faceplate": "IEC 60603",
}


CATEGORIES = {
    "Fasteners": [
        "bolt", "pan_head_screw", "hex_nut", "wing_nut", "tee_nut",
        "washer", "rivet", "eyebolt", "u_bolt", "hex_standoff",
        "standoff", "pcb_standoff_plate", "wall_anchor", "grommet",
        "snap_clip", "clevis_pin", "dowel_pin", "cotter_pin", "taper_pin",
        "circlip", "parallel_key", "knob", "ball_knob", "lobed_knob",
        "pull_handle",
    ],
    "Gears & Transmission": [
        "spur_gear", "helical_gear", "bevel_gear", "worm_screw",
        "sprocket", "double_simplex_sprocket", "pulley", "handwheel",
        "cam", "ratchet_sector", "impeller", "propeller", "spline_hub",
    ],
    "Shafts & Revolved": [
        "stepped_shaft", "hollow_tube", "dog_bone", "lathe_turned_part",
        "twisted_drill", "tapered_boss", "connecting_rod", "piston",
        "spacer_ring", "torus_link", "turnbuckle", "clevis", "j_hook",
    ],
    "Springs": ["coil_spring", "torsion_spring", "bellows"],
    "Brackets & Mounts": [
        "l_bracket", "z_bracket", "gusseted_bracket", "twisted_bracket",
        "mounting_angle", "mounting_plate", "slotted_plate",
        "keyhole_plate", "locator_block", "pillow_block", "rib_plate",
        "shaft_collar", "flat_link", "hinge", "dovetail_slide",
    ],
    "Housings & Containers": [
        "enclosure", "fan_shroud", "heat_sink", "motor_end_cap",
        "bearing_retainer_cap", "dome_cap", "battery_holder", "phone_stand",
        "chair", "table", "bucket", "gridfinity_bin",
        "hex_key_organizer", "capsule",
    ],
    "Piping & Flanges": [
        "pipe_flange", "round_flange", "t_pipe_fitting", "pipe_elbow",
        "duct_elbow", "venturi_tube", "nozzle", "grease_nipple",
        "threaded_adapter", "manifold_block",
    ],
    "Panels & Structural": [
        "i_beam", "u_channel", "t_slot_rail", "rect_frame", "waffle_plate",
        "vented_panel", "mesh_panel", "wire_grid", "cable_routing_panel",
        "connector_faceplate", "sheet_metal_tray", "cruciform", "star_blank",
    ],
}

# Category colours (muted, distinct)
COLORS = {
    "Fasteners":             "#1f4ed8",
    "Gears & Transmission":  "#9333ea",
    "Shafts & Revolved":     "#db2777",
    "Springs":               "#f59e0b",
    "Brackets & Mounts":     "#10b981",
    "Housings & Containers": "#0ea5e9",
    "Piping & Flanges":      "#ef4444",
    "Panels & Structural":   "#64748b",
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

    fig, ax = plt.subplots(figsize=(11, 11), subplot_kw=dict(polar=True))
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_axis_off()

    R_INNER = 0.45
    R_CAT = 0.72
    R_FAM_INNER = 0.72
    R_FAM_OUTER = 1.08

    angle = 0.0
    for cat, members in CATEGORIES.items():
        n = len(members)
        span = 2 * math.pi * n / total
        # category arc
        ax.bar(angle + span / 2, R_CAT - R_INNER, width=span,
               bottom=R_INNER, color=COLORS[cat],
               edgecolor="white", linewidth=2, align="center")

        # category label — curved along mid-radius of the category ring
        mid = angle + span / 2
        label_r = (R_INNER + R_CAT) / 2
        rot = math.degrees(-mid) if math.pi / 2 < mid < 3 * math.pi / 2 else math.degrees(-mid)
        # Simpler: just put text at mid angle, upright
        lx = label_r * math.sin(mid)
        ly = label_r * math.cos(mid)
        ang_deg = math.degrees(mid)
        text_rot = -ang_deg if ang_deg < 180 else 180 - ang_deg
        ax.text(mid, label_r, f"{cat}\n({n})",
                ha="center", va="center", fontsize=11,
                fontweight="bold", color="white",
                rotation=text_rot, rotation_mode="anchor")

        # family sub-wedges
        fam_span = span / n
        fam_color = lighten(COLORS[cat], 0.15)
        for i, fam in enumerate(members):
            fa = angle + fam_span * i
            ax.bar(fa + fam_span / 2, R_FAM_OUTER - R_FAM_INNER,
                   width=fam_span, bottom=R_FAM_INNER,
                   color=fam_color, edgecolor="white", linewidth=0.8,
                   align="center")
            # family label — radial text outside
            mid_fa = fa + fam_span / 2
            txt_r = R_FAM_OUTER + 0.015
            ang = math.degrees(mid_fa)
            # make text readable: rotate along radius, flip if on bottom half
            if ang <= 180:
                rot = 90 - ang
                ha = "left"
            else:
                rot = 270 - ang
                ha = "right"
            label = fam.replace("_", " ")
            std = STANDARDS.get(fam, "")
            if std:
                label = f"{label} · {std}"
            ax.text(mid_fa, txt_r, label,
                    ha=ha, va="center", fontsize=7.2, color="#1f2937",
                    rotation=rot, rotation_mode="anchor")

        angle += span

    # central title
    std_count = len({v for v in STANDARDS.values() if v})
    ax.text(0, 0, f"BenchCAD\n106 families\n· 8 categories ·\n{std_count} ISO/DIN/EN refs",
            ha="center", va="center", fontsize=14, fontweight="bold",
            color="#1f2937",
            transform=ax.transData._b if False else ax.transData)
    # simpler: place text in data coords at origin with radius 0
    # (matplotlib polar accepts (theta=0, r=0) as center)

    ax.set_ylim(0, 1.35)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, format="svg", bbox_inches="tight",
                pad_inches=0.1, transparent=True)
    print(f"wrote {OUT}  ({OUT.stat().st_size//1024} KB)")


if __name__ == "__main__":
    main()
