---
name: artioscad
description: Draw packaging dielines (折叠纸盒/包装结构设计作业) in Esko ArtiosCAD 23.07 on this PC and produce .ARD (2D), .A3D (folded 3D) and 效果图 PNGs. Use when the user asks to 绘图/画刀版/做作业/出效果图 in ArtiosCAD, gives box dimensions or a template ARD, or asks to read an .ARD/.A3D file.
---

# ArtiosCAD drawing skill

Paths below are relative to this skill folder. Python: a Windows Python 3.12 with
`pip install -r requirements.txt` (ezdxf, pywinauto, pywin32, pillow), run as `python -I`.
Pass Windows paths (`cygpath -w` under Git Bash) to it. If ArtiosCAD is not at
`C:\Esko\Artios\ArtiosCAD23.07\Program\ArtiosCAD.exe`, set the `ARTIOSCAD_EXE` env var.

## How it works (why it is stable)
1. **Geometry is computed, not clicked.** Write a design script using `acad/dieline.py`
   (lines, arcs, `fillet_poly` = REBLEND, `mirror_x/y` = dup neg, `rotate_copy`/`polar_array`
   = trans rot, `set_type` = cha). Output DXF where **DXF color = ArtiosCAD line type**
   (import profile `Artios DWG/DXF - Metric` maps color→type): 1 切割 CUT, 2 压痕 CREASE,
   8 反向压痕 REV_CREASE, 3 半切 PARTIAL, 4 打孔 PERF (3/4 inferred from DDES ranges — check on
   screen the first time they are used).
2. **ArtiosCAD is driven without focus or screen coordinates** (`acad/gui.py`):
   menu commands via `PostMessage(WM_COMMAND, id)` (ids in `reference/menu_ids.tsv`),
   dialog controls by control id, screenshots via `PrintWindow` (works behind the terminal).
   Canvas clicks (3D base panel, fold) are computed from the design bbox + detected board
   silhouette; `detect_orientation` handles the 3D top view being mirrored.
3. **Verify every step by reading the PNGs** it writes (`*_preview.png`, `*_2d.png`, `*_3d.png`).
   Never claim success without looking at them.

## Workflow for a new assignment
1. Read the assignment (PDF/text/screenshot). If dimensions or box style are unclear, ask.
2. Copy the closest script from `examples/` (e.g. `tuck_end_box.py`) to `work/<作业名>.py`;
   edit parameters/geometry. `build()` must return a `Dieline` and set
   `dl.notes["base"] = (x, y)` = a point inside the 3D base panel (usually front panel center).
3. Self-check first: `dl.preview(png)` and Read the PNG (black=cut, red=crease, blue=rev crease,
   blue circle = base point).
4. Run: `python.exe -I acad/pipeline.py <script.py> <out_dir> [--no3d] [--angle 90]`
   → `<name>.dxf/.ARD/.A3D`, `_2d.png`, `_3d.png`, `_report.json`.
5. Read `_2d.png` and `_3d.png`. Fold-all folds every crease to 90°; for partial folds or
   specific crease angles, use the 3D fold tool (25573) with `gui.post_click` +
   `gui.set_status_edit(0, angle)`.
6. Give the user the file paths; they open the ARD/A3D themselves to tweak and take report screenshots.

## Known dialog flow (ArtiosCAD 23.07 中文)
- Open DXF → "导入 DWG/DXF 文件" (tree 2990 → Artios/Artios DWG/DXF - Metric; file unit mm 2988,
  design unit mm 3003; OK 1) → "单一设计设置" (tree 2974 → Artios/Folding Carton/Folding Carton -
  Metric - Single design parameters; board edit 2780 default I-SBS-16; OK 1).
- Save As: WM_COMMAND 57604 → standard dialog, filename Edit id 1148, OK 1. Paths must use backslashes.
- 转为3D 26113 → if a 3D doc is open: dialog "转为3D" (2428 新建3D, OK) → "增加未折叠的设计"
  (preview Static 7281, click base panel, OK 1).
- 3D: 视图角度 25574 → status-bar edits [rotate, tilt, spin]; tilt 90 = top view; fit 27791.
  全部折叠工具 25588 → double-click a crease = fold all 90; status edit 0 = angle.
- If something unexpected pops up: `python.exe -I acad/gui.py dlgs`, then
  `gui.py dump "" <txt>` (writes controls + PNG) and handle it by control id; add it to this list.

## Learning from template ARDs
`tools/ard_history.py <file.ARD>` dumps ArtiosCAD's construction log. See
`reference/NOTES.md` for what the sample 设计2 (22.5° rotational 四重对称结构 with reverse
creases) contains.
