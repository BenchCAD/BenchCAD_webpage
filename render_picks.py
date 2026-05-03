"""Pick hard variants from N un-used families and compose 2 contact sheets.

Source: BenchCAD/cad_bench HF parquet (composite_png column = 4-view render).
Output: /tmp/benchcad_picks/sheet_a.png, sheet_b.png
"""

from __future__ import annotations

import io
import math
import random
import sys
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
PARQUET = Path.home() / ".cache/huggingface/hub/datasets--BenchCAD--cad_bench/snapshots/6bf222ee20d0e2e2a74d12cdaa52a3b994ca0175/data/test-00000-of-00001.parquet"
OUT_DIR = ROOT / "previews"
OUT_DIR.mkdir(parents=True, exist_ok=True)

USED = {
    "twisted_drill", "bevel_gear", "twisted_bracket", "coil_spring",
    "impeller", "bellows", "heat_sink", "eyebolt", "turnbuckle", "hinge",
    "ratchet_sector", "double_simplex_sprocket", "t_pipe_fitting",
    "lathe_turned_part", "spline_hub", "fan_shroud", "wing_nut",
    # Already chosen by the user from the previous pass (Take 2: 1,2,7,10,18,24,27)
    "helical_gear", "sprocket", "pipe_elbow", "handwheel",
    "wall_anchor", "pulley", "round_flange",
}

# Tiered op rarity. Tier-1 ops (sweep/loft/twistExtrude/torus) produce
# unmistakably non-trivial geometry; tier-2 ops (patterns / threaded holes /
# spline / shell) are common but still visual interest above plain extrude+cut.
TIER1_OPS = ("sweep", "loft", "twistextrude", "torus", "helix", "thread")
TIER2_OPS = ("polararray", "rarray", "mirrory", "spline", "shell",
             "threephointarc", "threepointarc", "cborehole", "cskhole",
             "polygon", "slot2d")

sys.path.insert(0, str(ROOT))
from make_distribution import STANDARDS  # noqa: E402

N_PICK = 30
TILE_W = 240    # final tile image width (composite is 268, will scale)


def op_bonus(row: dict) -> int:
    ops = (row.get("ops_used") or "").lower()
    b = 0
    if any(op in ops for op in TIER1_OPS):
        b += 120
    if any(op in ops for op in TIER2_OPS):
        b += 30
    return b


def complexity(row: dict) -> int:
    """Heuristic visual-complexity score for a CAD sample."""
    fc = int(row.get("feature_count") or 0)
    ops = row.get("ops_used") or "[]"
    n_ops = ops.count('"') // 2 if isinstance(ops, str) else len(ops)
    code_len = len(row.get("gt_code") or "")
    return fc * 6 + n_ops * 3 + code_len // 60 + op_bonus(row)


def load_hard_by_family() -> dict[str, list[dict]]:
    """{family: [row, ...]} for difficulty == 'hard', each list sorted
    by complexity descending."""
    t = pq.read_table(PARQUET, columns=[
        "stem", "family", "difficulty", "feature_count", "ops_used",
        "gt_code", "composite_png",
    ])
    rows = t.to_pylist()
    by_fam: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("difficulty") != "hard":
            continue
        by_fam.setdefault(r["family"], []).append(r)
    for fam, lst in by_fam.items():
        lst.sort(key=complexity, reverse=True)
    return by_fam


def caption_tile(composite_bytes: bytes, family: str, standard: str | None) -> Image.Image:
    img = Image.open(io.BytesIO(composite_bytes)).convert("RGB")
    img = img.resize((TILE_W, TILE_W), Image.LANCZOS)

    pad = 8
    cap_h = 56
    canvas = Image.new("RGB", (TILE_W, TILE_W + cap_h), "white")
    canvas.paste(img, (0, 0))

    draw = ImageDraw.Draw(canvas)
    try:
        f1 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 15)
        f2 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 11)
    except OSError:
        f1 = ImageFont.load_default()
        f2 = ImageFont.load_default()

    draw.text((TILE_W // 2, TILE_W + 6), family,
              fill="#111827", font=f1, anchor="mt")
    draw.text((TILE_W // 2, TILE_W + 28), standard or "—",
              fill="#6b7280", font=f2, anchor="mt")
    draw.rectangle([(0, 0), (TILE_W - 1, TILE_W + cap_h - 1)],
                   outline="#e5e7eb", width=1)
    return canvas


def make_sheet(tiles: list[Image.Image], cols: int, title: str) -> Image.Image:
    if not tiles:
        return Image.new("RGB", (100, 100), "white")
    rows = math.ceil(len(tiles) / cols)
    tw, th = tiles[0].size
    gap = 12
    title_h = 50
    W = cols * tw + (cols + 1) * gap
    H = title_h + rows * th + (rows + 1) * gap
    sheet = Image.new("RGB", (W, H), "#fafafa")

    draw = ImageDraw.Draw(sheet)
    try:
        ft = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
    except OSError:
        ft = ImageFont.load_default()
    draw.text((W // 2, 14), title, fill="#111827", font=ft, anchor="mt")

    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        x = gap + c * (tw + gap)
        y = title_h + gap + r * (th + gap)
        sheet.paste(tile, (x, y))
    return sheet


def main() -> None:
    by_fam = load_hard_by_family()
    print(f"families with hard variants in HF parquet: {len(by_fam)}")

    # Rank families by their most-complex hard sample (descending). The
    # complexity score boosts samples with rare ops (sweep/loft/twistExtrude
    # tier-1, patterns/threaded-holes tier-2).
    ranked = sorted(
        ((fam, lst) for fam, lst in by_fam.items() if fam not in USED),
        key=lambda p: -complexity(p[1][0]),
    )
    picks = ranked[:N_PICK]

    tiles: list[Image.Image] = []
    for fam, rows in picks:
        row = rows[0]                     # most-complex hard sample
        cb = row["composite_png"]["bytes"]
        tile = caption_tile(cb, fam, STANDARDS.get(fam))
        tiles.append(tile)
        ops_short = (row.get("ops_used") or "")[:60].replace('"', '')
        print(f"  {fam:<26} score={complexity(row):>4}  ← {row['stem']}  ops={ops_short}")

    half = math.ceil(len(tiles) / 2)
    sheet_a = make_sheet(tiles[:half], cols=5,
                         title=f"BenchCAD hero candidates — sheet A (1–{half})")
    sheet_b = make_sheet(tiles[half:], cols=5,
                         title=f"BenchCAD hero candidates — sheet B ({half+1}–{len(tiles)})")

    a_path = OUT_DIR / "sheet_a.png"
    b_path = OUT_DIR / "sheet_b.png"
    sheet_a.save(a_path, optimize=True)
    sheet_b.save(b_path, optimize=True)
    print(f"\nwrote {a_path} ({a_path.stat().st_size // 1024} KB)")
    print(f"wrote {b_path} ({b_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
