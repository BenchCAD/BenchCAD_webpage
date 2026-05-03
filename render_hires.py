"""Render 512×512 iso stills of the main-figure picks.

Pipeline: HF parquet gt_code → exec via CadQuery → temp STL → VTK iso
render with the same camera/material as render_cases.py (just at higher
resolution and as a single still).

Output:
  /tmp/benchcad_picks/hires/<family>.png   (one per pick)
  /tmp/benchcad_picks/hires_composite.png  (combined 4×N grid)
"""

from __future__ import annotations

import io
import math
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import trimesh
import vtk
from PIL import Image, ImageDraw, ImageFont
from vtk.util.numpy_support import numpy_to_vtk

ROOT = Path(__file__).resolve().parent
PARQUET = Path.home() / ".cache/huggingface/hub/datasets--BenchCAD--cad_bench/snapshots/6bf222ee20d0e2e2a74d12cdaa52a3b994ca0175/data/test-00000-of-00001.parquet"
HIRES_DIR = Path("/tmp/benchcad_picks/hires")
HIRES_DIR.mkdir(parents=True, exist_ok=True)
COMP_PATH = Path("/tmp/benchcad_picks/hires_composite.png")

sys.path.insert(0, str(ROOT))
from make_distribution import STANDARDS  # noqa: E402

# (family, stem_or_None) — None means pick the most-complex hard sample.
# 18 picks for the paper main figure, laid out 6×3.
SELECTED: list[tuple[str, str | None]] = [
    ("twisted_drill",            None),
    ("wing_nut",                 None),
    ("torsion_spring",           None),
    ("bolt",                     None),
    ("u_bolt",                   None),
    ("helical_gear",             None),
    ("pipe_elbow",               None),
    ("double_simplex_sprocket",  None),
    ("handwheel",                None),
    ("t_pipe_fitting",           "synth_t_pipe_fitting_000377_s4420"),  # #3
    ("pcb_standoff_plate",       None),
    ("round_flange",             None),
    ("cam",                      None),
    ("spline_hub",               None),
    ("eyebolt",                  None),
    ("impeller",                 None),
    ("heat_sink",                "synth_heat_sink_000574_s4420"),       # #3
    ("battery_holder",           None),
]

# Render config — true ISO from [1,1,1] octant (elev=arctan(1/√2), az=45°)
IMG_SIZE = 512
SS = 2                      # supersample
ELEV_DEG = math.degrees(math.atan(1.0 / math.sqrt(2.0)))   # 35.264°
AZ_DEG = 45.0
CAM_DIST = 1.9
LOOKAT = np.array([0.5, 0.5, 0.5])
MESH_COLOR = np.array([129, 216, 208]) / 255.0   # Tiffany blue (lightened for shading)
EDGE_COLOR = (0.0, 0.0, 0.0)


def cam_eye_for(elev_deg: float, az_deg: float, dist: float = CAM_DIST) -> np.ndarray:
    e, a = math.radians(elev_deg), math.radians(az_deg)
    return LOOKAT + dist * np.array([
        math.cos(a) * math.cos(e),
        math.sin(a) * math.cos(e),
        math.sin(e),
    ])


CAM_EYE = cam_eye_for(ELEV_DEG, AZ_DEG)


def complexity(row: dict) -> int:
    fc = int(row.get("feature_count") or 0)
    ops = row.get("ops_used") or "[]"
    n_ops = ops.count('"') // 2 if isinstance(ops, str) else len(ops)
    code_len = len(row.get("gt_code") or "")
    return fc * 6 + n_ops * 3 + code_len // 60


def pick_row(rows: list[dict], family: str, stem: str | None) -> dict | None:
    if stem:
        for r in rows:
            if r["stem"] == stem:
                return r
        return None
    cands = [r for r in rows if r["family"] == family and r.get("difficulty") == "hard"]
    cands.sort(key=complexity, reverse=True)
    return cands[0] if cands else None


def _patch_ocp_hashcode() -> None:
    """OCP removed `HashCode` from TopoDS_* in newer wheels but CadQuery
    2.3 still calls it. Monkey-patch a fallback so STL export works."""
    try:
        import OCP.TopoDS as _t
    except ImportError:
        return

    def _hash_code(self, *args):
        return hash(self)

    for cls_name in (
        "TopoDS_Shape", "TopoDS_Solid", "TopoDS_Face", "TopoDS_Edge",
        "TopoDS_Vertex", "TopoDS_Wire", "TopoDS_Shell",
        "TopoDS_Compound", "TopoDS_CompSolid",
    ):
        cls = getattr(_t, cls_name, None)
        if cls and not hasattr(cls, "HashCode"):
            try:
                cls.HashCode = _hash_code
            except (TypeError, AttributeError):
                pass


_patch_ocp_hashcode()


def code_to_stl(gt_code: str, dst: Path) -> None:
    """Execute CadQuery code, find a Workplane in locals, export STL."""
    import cadquery as cq

    ns: dict = {"show_object": lambda *a, **k: None}
    exec(gt_code, ns, ns)

    candidate = (
        ns.get("result") or ns.get("r") or ns.get("part") or ns.get("model")
    )
    if candidate is None:
        # Fallback: scan for any Workplane / Solid / Compound
        for v in ns.values():
            if isinstance(v, cq.Workplane):
                candidate = v
                break
    if candidate is None:
        raise RuntimeError("no Workplane in gt_code")
    cq.exporters.export(candidate, str(dst))


def load_mesh_norm(stl_path: Path):
    m = trimesh.load_mesh(str(stl_path))
    v = np.asarray(m.vertices, dtype=np.float64)
    f = np.asarray(m.faces, dtype=np.int64)
    mn, mx = v.min(axis=0), v.max(axis=0)
    scale = 1.0 / max((mx - mn).max(), 1e-9)
    v = (v - (mn + mx) / 2.0) * scale + 0.5
    return v, f


def render_iso(verts: np.ndarray, tris: np.ndarray,
               cam_eye: np.ndarray | None = None) -> Image.Image:
    if cam_eye is None:
        cam_eye = CAM_EYE
    pts = vtk.vtkPoints()
    pts.SetData(numpy_to_vtk(verts, deep=True))

    cells = vtk.vtkCellArray()
    for tri in tris:
        cells.InsertNextCell(3)
        for idx in tri:
            cells.InsertCellPoint(int(idx))

    pd = vtk.vtkPolyData()
    pd.SetPoints(pts)
    pd.SetPolys(cells)

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(pd)
    normals.ComputePointNormalsOn()
    normals.Update()

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())
    mapper.ScalarVisibilityOff()      # use actor color, not mesh scalars
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    p = actor.GetProperty()
    p.SetColor(*MESH_COLOR)
    p.SetAmbient(0.3)
    p.SetDiffuse(0.7)

    edges = vtk.vtkFeatureEdges()
    edges.SetInputConnection(normals.GetOutputPort())
    edges.BoundaryEdgesOn()
    edges.FeatureEdgesOn()
    edges.ManifoldEdgesOff()
    edges.NonManifoldEdgesOn()
    edges.SetFeatureAngle(35.0)
    em = vtk.vtkPolyDataMapper()
    em.SetInputConnection(edges.GetOutputPort())
    ea = vtk.vtkActor()
    ea.SetMapper(em)
    ep = ea.GetProperty()
    ep.SetColor(*EDGE_COLOR)
    ep.SetLineWidth(2.0)
    ep.SetRepresentationToWireframe()
    ep.LightingOff()

    ren = vtk.vtkRenderer()
    ren.AddActor(actor)
    ren.AddActor(ea)
    ren.SetBackground(1.0, 1.0, 1.0)

    cam = ren.GetActiveCamera()
    cam.SetPosition(*cam_eye.tolist())
    cam.SetFocalPoint(*LOOKAT.tolist())
    cam.SetViewUp(0.0, 0.0, 1.0)
    # Parallel (orthographic) projection — eliminates perspective cropping
    # of elongated objects (drills, U-bolts, tubes) at ISO angles. A scale
    # of ~0.9 leaves a small margin around the unit cube's hex projection.
    cam.SetParallelProjection(1)
    cam.SetParallelScale(0.9)

    rw = vtk.vtkRenderWindow()
    rw.SetOffScreenRendering(1)
    rw.AddRenderer(ren)
    rw.SetSize(IMG_SIZE * SS, IMG_SIZE * SS)
    rw.Render()

    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(rw)
    w2i.Update()

    import vtk.util.numpy_support as nps
    img = w2i.GetOutput()
    dims = img.GetDimensions()
    arr = nps.vtk_to_numpy(img.GetPointData().GetScalars())
    arr = arr.reshape(dims[1], dims[0], -1)[::-1][:, :, :3].astype(np.uint8)
    return Image.fromarray(arr).resize((IMG_SIZE, IMG_SIZE), Image.LANCZOS)


def render_one(gt_code: str, cam_eye: np.ndarray | None = None) -> Image.Image:
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as fp:
        stl = Path(fp.name)
    try:
        code_to_stl(gt_code, stl)
        v, f = load_mesh_norm(stl)
        return render_iso(v, f, cam_eye=cam_eye)
    finally:
        stl.unlink(missing_ok=True)


def label_tile(img: Image.Image, family: str) -> Image.Image:
    cap_h = 64
    canvas = Image.new("RGB", (img.width, img.height + cap_h), "white")
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    try:
        f1 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
        f2 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
    except OSError:
        f1 = ImageFont.load_default()
        f2 = ImageFont.load_default()
    draw.text((img.width // 2, img.height + 10), family, fill="#111827", font=f1, anchor="mt")
    draw.text((img.width // 2, img.height + 38),
              STANDARDS.get(family) or "—", fill="#6b7280", font=f2, anchor="mt")
    draw.rectangle([(0, 0), (img.width - 1, img.height + cap_h - 1)],
                   outline="#e5e7eb", width=2)
    return canvas


def main() -> None:
    rows = pq.read_table(PARQUET, columns=[
        "stem", "family", "difficulty", "feature_count",
        "ops_used", "gt_code",
    ]).to_pylist()

    tiles: list[tuple[str, Image.Image]] = []
    for fam, stem in SELECTED:
        row = pick_row(rows, fam, stem)
        if not row:
            print(f"  MISS {fam}")
            continue
        t0 = time.time()
        try:
            im = render_one(row["gt_code"])
        except Exception as e:
            print(f"  FAIL {fam}: {e}")
            continue
        out = HIRES_DIR / f"{fam}.png"
        im.save(out, optimize=True)
        tiles.append((fam, im))
        print(f"  {fam:<28} {time.time()-t0:5.1f}s ← {row['stem']}")

    # Composite grid (6 columns × 3 rows for 18 tiles)
    if tiles:
        cols = 6
        rows_n = math.ceil(len(tiles) / cols)
        labeled = [label_tile(im, fam) for fam, im in tiles]
        tw, th = labeled[0].size
        gap = 18
        title_h = 0           # no title — clean for paper insertion
        W = cols * tw + (cols + 1) * gap
        H = title_h + rows_n * th + (rows_n + 1) * gap
        sheet = Image.new("RGB", (W, H), "white")
        for i, t in enumerate(labeled):
            r, c = divmod(i, cols)
            x = gap + c * (tw + gap)
            y = title_h + gap + r * (th + gap)
            sheet.paste(t, (x, y))
        sheet.save(COMP_PATH, optimize=True)
        print(f"\nwrote {COMP_PATH} ({COMP_PATH.stat().st_size // 1024} KB, {W}×{H})")


if __name__ == "__main__":
    main()
