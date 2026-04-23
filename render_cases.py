"""Render 16 rotating case animations for the BenchCAD project page.

For each family pick the most geometrically-complex sample (hard difficulty),
load mesh.stl, normalize to [0,1]^3 centered at (0.5,0.5,0.5), and render
N_FRAMES frames of the part rotating around an axis tilted TILT_DEG from Z.
Output animated WebP at website/static/cases/<family>.webp.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import trimesh
import vtk
from PIL import Image
from vtk.util.numpy_support import numpy_to_vtk

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "Cadance/data/data_generation/generated_data/fusion360"
OUT = ROOT / "static/cases"
OUT.mkdir(parents=True, exist_ok=True)

N_FRAMES = 24
TILT_DEG = 5.0            # rotation axis offset from Z (tumble)
ELEV_DEG = 22.0           # fixed camera elevation
AZ_DEG = 25.0             # fixed camera azimuth
CAM_DIST = 1.9
LOOKAT = np.array([0.5, 0.5, 0.5])
IMG_SIZE = 192
SS = 3
MESH_COLOR = np.array([255, 255, 136]) / 255.0
EDGE_COLOR = (0.12, 0.12, 0.12)
FRAME_MS = 93             # 0.75x of prior 70ms → slower spin

# (display_label, family_slug, stem) — all hard/complex samples
CASES = [
    ("twisted_drill",      "twisted_drill",      "synth_twisted_drill_006224_s4420"),
    ("bevel_gear",         "bevel_gear",         "synth_bevel_gear_000810_s4419"),
    ("twisted_bracket",    "twisted_bracket",    "synth_twisted_bracket_000001_s4418"),
    ("coil_spring",        "coil_spring",        "synth_coil_spring_001093_s4420"),
    ("impeller",           "impeller",           "synth_impeller_001351_s4185"),
    ("bellows",            "bellows",            "synth_bellows_000450_s4194"),
    ("heat_sink",          "heat_sink",          "synth_heat_sink_006182_s4420"),
    ("eyebolt",            "eyebolt",            "synth_eyebolt_000008_s4418"),
    ("turnbuckle",         "turnbuckle",         "synth_turnbuckle_000104_s41918"),
    ("hinge",              "hinge",              "synth_hinge_000216_s5184"),
    ("ratchet_sector",     "ratchet_sector",     "synth_ratchet_sector_008624_s4420"),
    ("double_simplex_sprocket", "double_simplex_sprocket", "synth_double_simplex_sprocket_000297_s4419"),
    ("t_pipe_fitting",     "t_pipe_fitting",     "synth_t_pipe_fitting_000198_s4420"),
    ("lathe_turned_part",  "lathe_turned_part",  "synth_lathe_turned_part_000123_s4185"),
    ("spline_hub",         "spline_hub",         "synth_spline_hub_000197_s4194"),
    ("fan_shroud",         "fan_shroud",         "synth_fan_shroud_000018_s4419"),
]

# Tilted rotation axis (5° off +Z around +X)
_t = math.radians(TILT_DEG)
ROT_AXIS = np.array([math.sin(_t), 0.0, math.cos(_t)])
ROT_AXIS /= np.linalg.norm(ROT_AXIS)

# Fixed camera position (3/4 view)
_e = math.radians(ELEV_DEG)
_a = math.radians(AZ_DEG)
CAM_EYE = LOOKAT + CAM_DIST * np.array([math.cos(_a) * math.cos(_e),
                                        math.sin(_a) * math.cos(_e),
                                        math.sin(_e)])


def load_mesh(stem: str) -> tuple[np.ndarray, np.ndarray]:
    stls = list((DATA / stem).rglob("mesh.stl"))
    if not stls:
        raise FileNotFoundError(f"no mesh.stl under {stem}")
    m = trimesh.load_mesh(str(stls[0]))
    v = np.asarray(m.vertices, dtype=np.float64)
    f = np.asarray(m.faces, dtype=np.int64)
    mn, mx = v.min(axis=0), v.max(axis=0)
    scale = 1.0 / max((mx - mn).max(), 1e-9)
    v = (v - (mn + mx) / 2.0) * scale + 0.5
    return v, f


def rotate_about_axis(verts: np.ndarray, theta_deg: float) -> np.ndarray:
    """Rodrigues rotation of verts around ROT_AXIS through LOOKAT."""
    t = math.radians(theta_deg)
    c, s = math.cos(t), math.sin(t)
    k = ROT_AXIS
    K = np.array([[0.0, -k[2], k[1]],
                  [k[2], 0.0, -k[0]],
                  [-k[1], k[0], 0.0]])
    R = np.eye(3) * c + s * K + (1.0 - c) * np.outer(k, k)
    return ((verts - LOOKAT) @ R.T) + LOOKAT


def render_frame(verts: np.ndarray, tris: np.ndarray) -> Image.Image:
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
    ep.SetLineWidth(1.8)
    ep.SetRepresentationToWireframe()
    ep.LightingOff()

    ren = vtk.vtkRenderer()
    ren.AddActor(actor)
    ren.AddActor(ea)
    ren.SetBackground(1.0, 1.0, 1.0)

    cam = ren.GetActiveCamera()
    cam.SetPosition(*CAM_EYE.tolist())
    cam.SetFocalPoint(*LOOKAT.tolist())
    cam.SetViewUp(0.0, 0.0, 1.0)
    cam.SetViewAngle(35.0)

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

    im = Image.fromarray(arr).resize((IMG_SIZE, IMG_SIZE), Image.LANCZOS)
    return im


def render_case(label: str, slug: str, stem: str, force: bool = False) -> None:
    out = OUT / f"{slug}.webp"
    if out.exists() and not force:
        print(f"  skip {slug} (exists)")
        return
    print(f"  rendering {slug} ← {stem}")
    v, f = load_mesh(stem)
    frames = []
    for i in range(N_FRAMES):
        theta = 360.0 * i / N_FRAMES
        v_rot = rotate_about_axis(v, theta)
        frames.append(render_frame(v_rot, f))
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        format="WEBP",
        duration=FRAME_MS,
        loop=0,
        quality=80,
        method=6,
    )
    print(f"    → {out.relative_to(ROOT)}  ({out.stat().st_size//1024} KB)")


def main() -> None:
    import sys
    force = "--force" in sys.argv
    for label, slug, stem in CASES:
        try:
            render_case(label, slug, stem, force=force)
        except Exception as e:
            print(f"  FAIL {slug}: {e}")


if __name__ == "__main__":
    main()
