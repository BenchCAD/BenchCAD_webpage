"""Pull leaderboard data from the public Google Sheet and render the chart.

Output: static/images/leaderboard.svg

Sheet layout (gid → tab):
    0          → Img2cq   (Image → Code metrics)
    582819243  → QA       (currently empty; will hold Image→QA & Code→QA)
    1010348399 → Edit     (Edit Code metrics)

Chart: 4 tasks on x-axis, score on y-axis. Vendor → color, flagship →
filled marker, non-flagship → hollow marker.
"""

from __future__ import annotations

import csv
import io
import sys
import urllib.request
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

SHEET_ID = "1UPv4uzIfZOThTqAiJON6bE0c5eemfyTnvkeL_Nzp914"
TABS = {
    "img2code": 0,
    "qa":       582819243,
    "edit":     1010348399,
}

TASKS = ["Image → Code", "Image → QA", "Code → QA", "Edit Code"]

# (sheet_name_substring, display_name, vendor, flagship)
MODELS = [
    ("opus-4.7",         "Claude Opus 4.7",   "Anthropic", True),
    ("sonnet-4.6",       "Claude Sonnet 4.6", "Anthropic", False),
    ("gemini-3.1-pro",   "Gemini 3.1 Pro",    "Google",    True),
    ("gpt-5.3",          "GPT-5.3",           "OpenAI",    True),
    ("gpt-4o",           "GPT-4o",            "OpenAI",    False),
]

VENDOR_COLORS = {
    "Anthropic": "#cc785c",
    "Google":    "#4285f4",
    "OpenAI":    "#10a37f",
}

OUT = Path(__file__).resolve().parent / "static/images/leaderboard.svg"


def fetch_csv(gid: int) -> list[dict[str, str]]:
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8")
    if not text.strip():
        return []
    return list(csv.DictReader(io.StringIO(text)))


def parse_score(v: str | None) -> float | None:
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def matching_rows(rows: list[dict[str, str]], model_key: str, name_col: str):
    """Yield rows whose name column contains the model_key (case-insensitive)."""
    for row in rows:
        name = (row.get(name_col) or "").strip().lower()
        if model_key in name:
            yield row


def first_score(rows: list[dict[str, str]], model_key: str, name_col: str,
                score_col: str, *, require_blank: str | None = None) -> float | None:
    """Find the first matching row whose score_col parses to a float.
    If require_blank is set, the named column must be empty for the row to count."""
    for row in matching_rows(rows, model_key, name_col):
        if require_blank is not None and (row.get(require_blank) or "").strip():
            continue
        s = parse_score(row.get(score_col))
        if s is not None:
            return s
    return None


def collect_scores() -> dict[str, dict[str, float]]:
    """{task: {display_name: score}}"""
    scores: dict[str, dict[str, float]] = {t: {} for t in TASKS}

    img2code = fetch_csv(TABS["img2code"])
    qa = fetch_csv(TABS["qa"])
    edit = fetch_csv(TABS["edit"])

    for model_key, display, _vendor, _flag in MODELS:
        # Image → Code: Img2cq tab, "Score" column
        s = first_score(img2code, model_key, "Model", "Score")
        if s is not None:
            scores["Image → Code"][display] = s

        # Image → QA / Code → QA: QA tab (column names TBD; tolerate variants)
        if qa:
            for task, candidates in (
                ("Image → QA", ["Image → QA", "Image to QA", "image_qa", "img2qa", "Image QA"]),
                ("Code → QA",  ["Code → QA",  "Code to QA",  "code_qa",  "code2qa", "Code QA"]),
            ):
                for c in candidates:
                    s = first_score(qa, model_key, "Model", c)
                    if s is not None:
                        scores[task][display] = s
                        break

        # Edit Code: Edit tab "mean_IoU"; only summary rows (diff column blank)
        s = first_score(edit, model_key, "model", "mean_IoU", require_blank="diff")
        if s is not None:
            scores["Edit Code"][display] = s

    return scores


def render(scores: dict[str, dict[str, float]]) -> None:
    fig, ax = plt.subplots(figsize=(10, 6.0))

    n_models = len(MODELS)
    group_width = 0.78
    offsets = [-group_width / 2 + group_width * (i + 0.5) / n_models
               for i in range(n_models)]

    for i, (_key, display, vendor, flagship) in enumerate(MODELS):
        color = VENDOR_COLORS[vendor]
        face = color if flagship else "white"
        edge = color
        ew = 0.5 if flagship else 2.0

        xs, ys = [], []
        for j, task in enumerate(TASKS):
            s = scores[task].get(display)
            if s is None:
                continue
            xs.append(j + offsets[i])
            ys.append(s)
            ax.scatter(j + offsets[i], s, s=160, c=face, edgecolors=edge,
                       linewidths=ew, zorder=4)

        if len(xs) >= 2:
            ax.plot(xs, ys, color=color, linewidth=1.0, alpha=0.45,
                    linestyle="-" if flagship else "--", zorder=2)

    ax.set_xticks(range(len(TASKS)))
    ax.set_xticklabels(TASKS, fontsize=11)
    ax.set_ylabel("Score (higher is better)", fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_xlim(-0.5, len(TASKS) - 0.5)
    ax.grid(axis="y", alpha=0.25)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    handles = []
    for _key, display, vendor, flagship in MODELS:
        color = VENDOR_COLORS[vendor]
        if flagship:
            h = Line2D([0], [0], marker="o", color="w",
                       markerfacecolor=color, markeredgecolor=color,
                       markersize=10, label=display)
        else:
            h = Line2D([0], [0], marker="o", color="w",
                       markerfacecolor="white", markeredgecolor=color,
                       markersize=10, markeredgewidth=2, label=display)
        handles.append(h)
    ax.legend(handles=handles, loc="upper right",
              fontsize=10, frameon=True, framealpha=0.95)

    ax.set_title("BenchCAD Leaderboard — Commercial Frontier Models",
                 fontsize=12, pad=12)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, format="svg", bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)


def main() -> int:
    try:
        scores = collect_scores()
    except Exception as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        return 1
    n = sum(len(v) for v in scores.values())
    print(f"collected {n} (model, task, score) cells")
    for task, m in scores.items():
        print(f"  {task}: {len(m)} models")
    render(scores)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
