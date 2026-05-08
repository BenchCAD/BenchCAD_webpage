"""Render every .step in previews/q3vl_wins_step_archive/<case>/ as a
1024x1024 iso PNG saved next to the .step (gt.step -> gt.png, etc.).

Pipeline per file: cadquery.importers.importStep -> exporters.export STL
-> trimesh load -> normalize to [0,1]^3 -> VTK iso render (same camera /
material as render_hires.py, just hi-res).
"""

from __future__ import annotations

import math
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import trimesh
import vtk
from PIL import Image
from vtk.util.numpy_support import numpy_to_vtk

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "previews/q3vl_wins_step_archive"

# Hi-res iso render config
IMG_SIZE = 1024
SS = 2
ELEV_DEG = math.degrees(math.atan(1.0 / math.sqrt(2.0)))
AZ_DEG = 45.0
CAM_DIST = 1.9
LOOKAT = np.array([0.5, 0.5, 0.5])
MESH_COLOR = np.array([129, 216, 208]) / 255.0
EDGE_COLOR = (0.0, 0.0, 0.0)


def _patch_ocp_hashcode() -> None:
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


def cam_eye() -> np.ndarray:
    e, a = math.radians(ELEV_DEG), math.radians(AZ_DEG)
    return LOOKAT + CAM_DIST * np.array([
        math.cos(a) * math.cos(e),
        math.sin(a) * math.cos(e),
        math.sin(e),
    ])


CAM_EYE = cam_eye()


def step_to_stl(step: Path, dst: Path) -> None:
    import cadquery as cq

    shape = cq.importers.importStep(str(step))
    cq.exporters.export(shape, str(dst), tolerance=0.05, angularTolerance=0.2)


def load_mesh_norm(stl: Path):
    m = trimesh.load_mesh(str(stl))
    if isinstance(m, trimesh.Scene):
        m = trimesh.util.concatenate(tuple(m.dump()))
    v = np.asarray(m.vertices, dtype=np.float64)
    f = np.asarray(m.faces, dtype=np.int64)
    if len(v) == 0 or len(f) == 0:
        raise RuntimeError("empty mesh")
    mn, mx = v.min(axis=0), v.max(axis=0)
    scale = 1.0 / max((mx - mn).max(), 1e-9)
    v = (v - (mn + mx) / 2.0) * scale + 0.5
    return v, f


def render_iso(verts: np.ndarray, tris: np.ndarray) -> Image.Image:
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
    mapper.ScalarVisibilityOff()
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
    em.ScalarVisibilityOff()
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
    cam.SetPosition(*CAM_EYE.tolist())
    cam.SetFocalPoint(*LOOKAT.tolist())
    cam.SetViewUp(0.0, 0.0, 1.0)
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


def render_step(step: Path) -> Image.Image:
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as fp:
        stl = Path(fp.name)
    try:
        step_to_stl(step, stl)
        v, f = load_mesh_norm(stl)
        return render_iso(v, f)
    finally:
        stl.unlink(missing_ok=True)


def main() -> None:
    case_dirs = sorted(d for d in ARCHIVE.iterdir() if d.is_dir())
    print(f"{len(case_dirs)} cases")
    n_ok = n_fail = 0
    for case in case_dirs:
        steps = sorted(case.glob("*.step"))
        if not steps:
            continue
        print(f"\n{case.name}  ({len(steps)} step files)")
        for step in steps:
            out = step.with_suffix(".png")
            t0 = time.time()
            try:
                im = render_step(step)
                im.save(out, optimize=True)
                print(f"  {step.name:<22} -> {out.name}  {time.time()-t0:5.1f}s  "
                      f"{out.stat().st_size//1024} KB")
                n_ok += 1
            except Exception as e:
                print(f"  {step.name:<22} FAIL: {e}")
                n_fail += 1
    print(f"\ndone: {n_ok} ok, {n_fail} failed")


if __name__ == "__main__":
    main()
