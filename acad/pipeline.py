"""End-to-end: Dieline -> DXF -> ArtiosCAD ARD -> 3D fold -> A3D + 效果图 PNG.

Usage (CLI):
    python -I pipeline.py <design_script.py> <out_dir> [--no3d] [--angle 90]
The design script must define build() -> dieline.Dieline (with notes["base"] set
for 3D). Every step is verified with a PrintWindow screenshot saved in out_dir.
"""
import os, sys, time, importlib.util, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gui
from dieline import CREASE, Line

BOARD = "I-SBS-16"   # board used in the sample design 设计2


def _handle_import_dialogs(stem, timeout=60):
    """Answer the DXF import / 单一设计设置 dialogs (any order) until the doc `stem` is open."""
    t = time.time()
    while time.time() - t < timeout:
        dl = gui.dialogs()
        for h, title in dl:
            try:
                d = gui.app().window(handle=h)
                if "DXF" in title or "DWG" in title:
                    gui.ctrl(d, 2990).get_item(["Artios", "Artios DWG/DXF - Metric"]).select()
                    time.sleep(0.5)
                    gui.ctrl(d, 2988, "Button").click()   # 文件单位: 毫米
                    gui.ctrl(d, 3003, "Button").click()   # 设计单位: 毫米
                    gui.ctrl(d, 1, "Button").click()
                elif "设计设置" in title:
                    gui.ctrl(d, 2974).get_item(["Artios", "Folding Carton",
                                                "Folding Carton - Metric - Single design parameters"]).select()
                    time.sleep(0.5)
                    gui.ctrl(d, 1, "Button").click()
            except Exception:
                pass  # dialog closed/replaced while we looked at it; re-scan
            time.sleep(1.5)
            break
        if not dl and stem.upper() in gui.main().window_text().upper():
            return True
        time.sleep(1)
    raise TimeoutError(f"{stem} not opened; dialogs={gui.dialogs()}")


def close_all():
    """Close every open document without saving (start each run from a clean state)."""
    gui.command(27899, 2)                      # 关闭所有
    for _ in range(20):
        dl = gui.dialogs()
        if not dl:
            return
        for h, title in dl:
            try:
                d = gui.app().window(handle=h)
                btns = {b.window_text(): b for b in d.wrapper_object().descendants()
                        if b.class_name() == "Button"}
                for k in ("否(&N)", "否", "不保存(&N)", "不保存"):
                    if k in btns:
                        btns[k].click(); break
                else:
                    gui.dump(d, os.path.join(os.environ.get("TEMP", "."), "acad_unknown_dialog.txt"))
                    raise RuntimeError(f"unexpected dialog while closing: {title}")
            except RuntimeError:
                raise
            except Exception:
                pass
        time.sleep(1)


def open_dxf(dxf):
    dxf = os.path.normpath(dxf)
    stem = os.path.splitext(os.path.basename(dxf))[0]
    if not gui._main_handle():
        gui.launch(dxf)
    else:
        close_all()
        gui.command("open", 2)
        gui.set_file_dialog_path(gui.wait_dialog(None, 20), dxf)
    _handle_import_dialogs(stem)
    time.sleep(2)


def convert_3d(dl):
    gui.command("convert_3d", 4)
    # If another 3D doc is open, ArtiosCAD first asks 更新/增加到/新建 3D -> always 新建3D
    for h, title in gui.dialogs():
        if title == "转为3D":
            d = gui.app().window(handle=h)
            gui.ctrl(d, 2428, "Button").click(); gui.ctrl(d, 1, "Button").click()
            time.sleep(3)
    d = gui.wait_dialog("折叠", 20)
    bb = dl.bbox()
    gui.click_design_point(d, 7281, bb, dl.notes["base"])
    gui.ctrl(d, 1, "Button").click()
    t = time.time()
    while time.time() - t < 30 and "a3d" not in gui.main().window_text().lower():
        time.sleep(1)
    time.sleep(2)


def fold_all(dl, angle=90, shot_dir="."):
    """Fold all creases: top view, fold-all tool, double-click a crease, then set angle."""
    gui.view3d_top()
    shot = os.path.join(shot_dir, "_top.png")
    gui.capture_main(shot)
    crease = next(it for it in dl.items if isinstance(it, Line) and it.t == CREASE)
    mid = ((crease.a[0] + crease.b[0]) / 2, (crease.a[1] + crease.b[1]) / 2)
    gui.command(25588, 1.5)                     # 全部折叠工具
    orient = gui.detect_orientation(dl, shot)
    sx, sy = gui.canvas_point(dl.bbox(), mid, shot, orient)
    gui.post_click(sx, sy, double=True)         # double-click = fold all 90
    if angle != 90:
        gui.set_status_edit(0, angle)
    time.sleep(2)


def run(design_path, out_dir, do3d=True, angle=90, view=(35, 30, 0)):
    os.makedirs(out_dir, exist_ok=True)
    spec = importlib.util.spec_from_file_location("design", design_path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    dl = mod.build()
    name = dl.name
    p = lambda ext: os.path.normpath(os.path.join(out_dir, name + ext))
    dl.to_dxf(p(".dxf")); dl.preview(p("_preview.png"))
    report = {"bbox_mm": [round(v, 2) for v in dl.bbox()], "items": len(dl.items)}

    open_dxf(p(".dxf"))
    gui.command(27791, 1.5)
    gui.capture_canvas(p("_2d.png"))
    report["ard"] = gui.save_as(p(".ARD"))

    if do3d:
        convert_3d(dl)
        fold_all(dl, angle, out_dir)
        gui.deselect()
        gui.view3d_angle(*view)
        gui.deselect()
        gui.capture_canvas(p("_3d.png"))
        report["a3d"] = gui.save_as(p(".A3D"))
    json.dump(report, open(p("_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return report


if __name__ == "__main__":
    args = sys.argv[1:]
    angle = float(args[args.index("--angle") + 1]) if "--angle" in args else 90
    print(run(args[0], args[1], do3d="--no3d" not in args, angle=angle))
