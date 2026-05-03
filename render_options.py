"""Render replacement-candidate composites for the BenchCAD main figure.

Outputs /tmp/benchcad_picks/options.png — labeled rows of:
  • Screw families (1 hard variant each)
  • t_pipe_fitting variants (multiple hard samples of same family)
  • heat_sink variants
  • battery_holder
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
PARQUET = Path.home() / ".cache/huggingface/hub/datasets--BenchCAD--cad_bench/snapshots/6bf222ee20d0e2e2a74d12cdaa52a3b994ca0175/data/test-00000-of-00001.parquet"
OUT = ROOT / "previews/options.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT))
from make_distribution import STANDARDS  # noqa: E402

TILE = 220
GAP = 10
COLS = 6


def complexity(row: dict) -> int:
    fc = int(row.get("feature_count") or 0)
    ops = row.get("ops_used") or "[]"
    n_ops = ops.count('"') // 2 if isinstance(ops, str) else len(ops)
    code_len = len(row.get("gt_code") or "")
    return fc * 6 + n_ops * 3 + code_len // 60


def load_table():
    return pq.read_table(PARQUET, columns=[
        "stem", "family", "difficulty", "feature_count",
        "ops_used", "gt_code", "composite_png",
    ]).to_pylist()


def hard_in(rows, family: str) -> list[dict]:
    return [r for r in rows if r["family"] == family and r.get("difficulty") == "hard"]


def best_per_family(rows, families: list[str]) -> list[tuple[str, dict]]:
    out = []
    for fam in families:
        cands = hard_in(rows, fam)
        if not cands:
            print(f"  no hard for {fam}")
            continue
        cands.sort(key=complexity, reverse=True)
        out.append((fam, cands[0]))
    return out


def top_n_in_family(rows, family: str, n: int) -> list[dict]:
    cands = hard_in(rows, family)
    cands.sort(key=complexity, reverse=True)
    return cands[:n]


def caption_tile(row: dict, label: str | None = None) -> Image.Image:
    cb = row["composite_png"]["bytes"]
    img = Image.open(io.BytesIO(cb)).convert("RGB").resize((TILE, TILE), Image.LANCZOS)
    cap_h = 56
    canvas = Image.new("RGB", (TILE, TILE + cap_h), "white")
    canvas.paste(img, (0, 0))

    draw = ImageDraw.Draw(canvas)
    try:
        f1 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 14)
        f2 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 11)
    except OSError:
        f1 = ImageFont.load_default()
        f2 = ImageFont.load_default()

    name = label if label else row["family"]
    sub = STANDARDS.get(row["family"]) or row["stem"].rsplit("_", 1)[0].replace("synth_", "")
    draw.text((TILE // 2, TILE + 6), name, fill="#111827", font=f1, anchor="mt")
    draw.text((TILE // 2, TILE + 28), sub, fill="#6b7280", font=f2, anchor="mt")
    draw.rectangle([(0, 0), (TILE - 1, TILE + cap_h - 1)], outline="#e5e7eb", width=1)
    return canvas


def main() -> None:
    rows = load_table()

    # Section 1: screw-type fastener families (1 hard sample each)
    screws = best_per_family(rows, ["bolt", "pan_head_screw", "u_bolt",
                                     "threaded_adapter", "rivet", "dowel_pin"])
    screw_tiles = [caption_tile(r, f"{fam}") for fam, r in screws]

    # Section 2: 4 different hard variants of t_pipe_fitting
    tpipes = top_n_in_family(rows, "t_pipe_fitting", 6)
    tpipe_tiles = [
        caption_tile(r, f"t_pipe #{i+1}")
        for i, r in enumerate(tpipes)
    ]

    # Section 3: 6 different hard variants of heat_sink
    heats = top_n_in_family(rows, "heat_sink", 6)
    heat_tiles = [
        caption_tile(r, f"heat_sink #{i+1}")
        for i, r in enumerate(heats)
    ]

    # Section 4: battery_holder
    bat = best_per_family(rows, ["battery_holder"])
    bat_tile = caption_tile(bat[0][1], "battery_holder") if bat else None

    sections = [
        ("Screws — replace duct_elbow with one of these", screw_tiles),
        ("t_pipe_fitting variants — pick a different one", tpipe_tiles),
        ("heat_sink variants — pick one to add", heat_tiles),
    ]
    if bat_tile:
        sections.append(("battery_holder", [bat_tile]))

    # Layout
    title_h = 50
    section_h = 32
    tw, th = TILE, TILE + 56
    total_h = title_h
    for _, tiles in sections:
        rows_in_section = (len(tiles) + COLS - 1) // COLS
        total_h += section_h + rows_in_section * (th + GAP) + GAP
    W = COLS * tw + (COLS + 1) * GAP

    sheet = Image.new("RGB", (W, total_h), "#fafafa")
    draw = ImageDraw.Draw(sheet)
    try:
        ft = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 20)
        fs = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 14)
    except OSError:
        ft = ImageFont.load_default()
        fs = ImageFont.load_default()
    draw.text((W // 2, 14),
              "BenchCAD main-figure replacement candidates",
              fill="#111827", font=ft, anchor="mt")

    y_cursor = title_h
    for section_title, tiles in sections:
        draw.text((GAP + 4, y_cursor + 6), section_title,
                  fill="#1f2937", font=fs, anchor="lt")
        y_cursor += section_h
        for i, tile in enumerate(tiles):
            r, c = divmod(i, COLS)
            x = GAP + c * (tw + GAP)
            y = y_cursor + r * (th + GAP)
            sheet.paste(tile, (x, y))
        rows_in_section = (len(tiles) + COLS - 1) // COLS
        y_cursor += rows_in_section * (th + GAP) + GAP

    sheet.save(OUT, optimize=True)
    print(f"\nwrote {OUT} ({OUT.stat().st_size // 1024} KB, {W}×{total_h})")
    for fam, r in screws:
        print(f"  screw  {fam:<24} ← {r['stem']}")
    for i, r in enumerate(tpipes):
        print(f"  tpipe  #{i+1:<2}                 ← {r['stem']}")
    for i, r in enumerate(heats):
        print(f"  heat   #{i+1:<2}                 ← {r['stem']}")
    if bat:
        print(f"  bat    {bat[0][0]:<24} ← {bat[0][1]['stem']}")


if __name__ == "__main__":
    main()
