"""Compose a main-figure candidate strip for the BenchCAD paper.

Takes a fixed list of families, finds the most-complex hard variant per
family in the BenchCAD HF parquet, and assembles them into one composite
image for review.
"""

from __future__ import annotations

import io
import math
import sys
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
PARQUET = Path.home() / ".cache/huggingface/hub/datasets--BenchCAD--cad_bench/snapshots/6bf222ee20d0e2e2a74d12cdaa52a3b994ca0175/data/test-00000-of-00001.parquet"
OUT = ROOT / "previews/main_figure.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT))
from make_distribution import STANDARDS  # noqa: E402

# User's wishlist for the paper's main figure (hard variants)
FAMILIES = [
    "twisted_drill", "wing_nut", "torsion_spring", "duct_elbow",
    "spur_gear", "helical_gear", "bevel_gear", "pipe_elbow",
    "double_simplex_sprocket", "handwheel", "t_pipe_fitting",
    "pcb_standoff_plate", "round_flange", "cam", "spline_hub",
    "eyebolt", "impeller",
]

TILE = 240
GAP = 12
COLS = 6


def complexity(row: dict) -> int:
    fc = int(row.get("feature_count") or 0)
    ops = row.get("ops_used") or "[]"
    n_ops = ops.count('"') // 2 if isinstance(ops, str) else len(ops)
    code_len = len(row.get("gt_code") or "")
    return fc * 6 + n_ops * 3 + code_len // 60


def best_hard_per_family() -> dict[str, dict]:
    t = pq.read_table(PARQUET, columns=[
        "stem", "family", "difficulty", "feature_count", "ops_used",
        "gt_code", "composite_png",
    ])
    best: dict[str, dict] = {}
    for r in t.to_pylist():
        if r.get("difficulty") != "hard":
            continue
        if r["family"] not in FAMILIES:
            continue
        if r["family"] not in best or complexity(r) > complexity(best[r["family"]]):
            best[r["family"]] = r
    return best


def caption_tile(composite_bytes: bytes, family: str, standard: str | None) -> Image.Image:
    img = Image.open(io.BytesIO(composite_bytes)).convert("RGB").resize((TILE, TILE), Image.LANCZOS)
    cap_h = 56
    canvas = Image.new("RGB", (TILE, TILE + cap_h), "white")
    canvas.paste(img, (0, 0))

    draw = ImageDraw.Draw(canvas)
    try:
        f1 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 16)
        f2 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 12)
    except OSError:
        f1 = ImageFont.load_default()
        f2 = ImageFont.load_default()

    draw.text((TILE // 2, TILE + 6), family, fill="#111827", font=f1, anchor="mt")
    draw.text((TILE // 2, TILE + 30), standard or "—", fill="#6b7280", font=f2, anchor="mt")
    draw.rectangle([(0, 0), (TILE - 1, TILE + cap_h - 1)], outline="#e5e7eb", width=1)
    return canvas


def main() -> None:
    best = best_hard_per_family()
    missing = [f for f in FAMILIES if f not in best]
    print(f"resolved {len(best)} / {len(FAMILIES)} families")
    if missing:
        print(f"  missing: {missing}")

    tiles = []
    for fam in FAMILIES:
        row = best.get(fam)
        if not row:
            continue
        cb = row["composite_png"]["bytes"]
        tile = caption_tile(cb, fam, STANDARDS.get(fam))
        tiles.append(tile)
        print(f"  {fam:<28} ← {row['stem']}  score={complexity(row)}")

    rows = math.ceil(len(tiles) / COLS)
    tw, th = tiles[0].size
    title_h = 50
    W = COLS * tw + (COLS + 1) * GAP
    H = title_h + rows * th + (rows + 1) * GAP
    sheet = Image.new("RGB", (W, H), "#fafafa")

    draw = ImageDraw.Draw(sheet)
    try:
        ft = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
    except OSError:
        ft = ImageFont.load_default()
    draw.text((W // 2, 14),
              f"BenchCAD main-figure candidates ({len(tiles)} hard variants)",
              fill="#111827", font=ft, anchor="mt")

    for i, tile in enumerate(tiles):
        r, c = divmod(i, COLS)
        x = GAP + c * (tw + GAP)
        y = title_h + GAP + r * (th + GAP)
        sheet.paste(tile, (x, y))

    sheet.save(OUT, optimize=True)
    print(f"\nwrote {OUT} ({OUT.stat().st_size // 1024} KB, {W}×{H})")


if __name__ == "__main__":
    main()
