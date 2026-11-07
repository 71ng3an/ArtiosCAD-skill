# artioscad — 让 Claude Code 自动在 ArtiosCAD 里画刀版

[English](#english) | 中文

一个 [Claude Code](https://claude.com/claude-code) Skill：用自然语言描述纸盒（或给出尺寸 / 作业要求），
它会在 **Esko ArtiosCAD 23.07（中文界面）** 里全自动完成：

**尺寸 → 精确刀版 DXF → 导入为 `.ARD`（2D）→ 转 3D → 全部折叠 → 保存 `.A3D` + 2D/3D 效果图 PNG**

适合包装工程 / 包装结构设计课程的作业、折叠纸盒快速打样。

## 特点
- **几何靠计算，不靠点鼠标**：刀版在 Python 里精确生成（直线、圆弧、倒圆角、镜像、旋转阵列），
  DXF 颜色 = ArtiosCAD 线型（1 切割、2 压痕、8 反向压痕……），导入后线型自动正确。
- **不抢键盘、不依赖屏幕坐标**：菜单用 `WM_COMMAND` id，对话框按控件 id 操作，截图用 `PrintWindow`，
  ArtiosCAD 被别的窗口挡住也能跑。
- **每一步都截图自检**：`_preview.png` / `_2d.png` / `_3d.png`，AI 看图确认后才报告完成。
- **能读你的模板**：`tools/ard_history.py` 可以导出 `.ARD` 里的建模命令历史，用来学习老师给的模板画法。

## 环境要求
- Windows + 已授权的 Esko ArtiosCAD 23.07 **中文界面**（对话框按中文标题匹配）
- Python 3.12：`pip install -r requirements.txt`（ezdxf、pywinauto、pywin32、pillow）
- ArtiosCAD 不在默认位置 `C:\Esko\Artios\ArtiosCAD23.07\Program\ArtiosCAD.exe` 时，设置环境变量 `ARTIOSCAD_EXE`

## 安装为 Claude Code Skill
```bash
git clone https://github.com/71ng3an/artioscad-skill ~/.claude/skills/artioscad
```
之后在 Claude Code 里直接说，例如：
> 用 ArtiosCAD 画一个 60×30×100 的反插式管式盒，出 3D 效果图

## 不用 AI，单独跑流水线
```bash
python -I acad/pipeline.py examples/tuck_end_box.py out/tuck
```
输出 `tuck_end_60x30x100.{dxf,ARD,A3D}`、`_preview.png`、`_2d.png`、`_3d.png`、`_report.json`。
参数：`--no3d` 只出 2D；`--angle 60` 折叠角度。

自己设计：复制 `examples/tuck_end_box.py`，改尺寸 / 几何，`build()` 返回 `Dieline`，
并设置 `dl.notes["base"] = (x, y)`（3D 底面上的一点）。

## 目录
| 路径 | 作用 |
|---|---|
| `SKILL.md` | 给 Claude 读的工作流程与已知对话框流程 |
| `acad/dieline.py` | 刀版构建器（线、弧、圆角、镜像、阵列）→ DXF / 预览 PNG |
| `acad/gui.py` | ArtiosCAD 界面自动化工具 |
| `acad/pipeline.py` | 端到端命令行 |
| `examples/tuck_end_box.py` | 参数化反插式管式盒 |
| `tools/ard_history.py` | 导出 `.ARD` 的建模命令历史 |
| `reference/menu_ids.tsv` | ArtiosCAD 23.07 菜单 → `WM_COMMAND` id 对照表 |
| `reference/NOTES.md`、`设计2_history.txt` | 示例设计的笔记与建模日志 |

## 已知限制
- 只在 ArtiosCAD 23.07 中文版上验证过；其他版本菜单 id / 对话框可能不同（可用 `gui.py dlgs` / `dump` 排查）。
- “全部折叠”统一折到同一角度；局部折叠需要用 3D 折叠工具手动指定。
- 半切（3）/ 打孔（4）线型的映射是推断的，首次使用请在屏幕上确认。

## 免责声明
本项目与 Esko 无关。ArtiosCAD 是 Esko-Graphics 的商标。请使用你自己合法授权的软件。
本仓库不包含任何 ArtiosCAD 程序文件。

## 许可证
[MIT](LICENSE)

---

<a id="english"></a>
## English

A Claude Code skill that draws folding-carton dielines in **Esko ArtiosCAD 23.07 (Chinese UI)** and produces
`.ARD` (2D), `.A3D` (folded 3D) and rendered PNGs, fully unattended.

1. Geometry is computed in Python (`acad/dieline.py`) and written as DXF where **DXF color = ArtiosCAD line type**.
2. ArtiosCAD is driven without keyboard focus or screen coordinates (`acad/gui.py`):
   `WM_COMMAND` menu ids, dialog control ids, `PrintWindow` screenshots.
3. `acad/pipeline.py`: DXF → import → save ARD → convert to 3D → fold all → save A3D + PNGs.

Requirements: Windows, a licensed ArtiosCAD 23.07 with Chinese UI, Python 3.12 + `requirements.txt`.
Set `ARTIOSCAD_EXE` if ArtiosCAD is not in the default location.

Not affiliated with Esko. ArtiosCAD is a trademark of Esko-Graphics. MIT licensed.
