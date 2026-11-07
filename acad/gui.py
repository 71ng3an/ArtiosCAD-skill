"""ArtiosCAD GUI automation helpers.

Design rule: never rely on keyboard focus or screen coordinates.
- Menu commands are sent with PostMessage(WM_COMMAND, id) to the main window.
- Dialog controls are driven by control_id via pywinauto (win32 backend).
- Screenshots use PrintWindow, so they work even when other windows cover ArtiosCAD.
"""
import os, sys, time, subprocess
import win32gui, win32con, win32ui
from ctypes import windll
from PIL import Image
from pywinauto import Application, Desktop

# Set ARTIOSCAD_EXE if ArtiosCAD is not installed in the default location.
EXE = os.environ.get("ARTIOSCAD_EXE",
                     r"C:\Esko\Artios\ArtiosCAD23.07\Program\ArtiosCAD.exe")
MAIN_CLASS = "ArtiosCAD_Application_Class"

# WM_COMMAND ids (from ResDll_cn.dll menu resources, ArtiosCAD 23.07)
CMD = {
    "open": 57601, "close": 57602, "save": 57603, "save_as": 57604,
    "import": 26168, "convert_3d": 26113, "exit": 57665,
}


def _main_handle():
    h = win32gui.FindWindow(MAIN_CLASS, None)
    return h or None


def app():
    return Application(backend="win32").connect(class_name=MAIN_CLASS)


def main():
    return app().window(class_name=MAIN_CLASS)


def launch(path=None, timeout=120):
    """Start ArtiosCAD (optionally with a file) or reuse a running instance."""
    if _main_handle() and path:
        subprocess.Popen([EXE, path])
    elif not _main_handle():
        subprocess.Popen([EXE] + ([path] if path else []))
    t = time.time()
    while time.time() - t < timeout:
        if _main_handle():
            return main()
        time.sleep(1)
    raise TimeoutError("ArtiosCAD did not start")


def command(name_or_id, wait=2.0):
    cid = CMD.get(name_or_id, name_or_id)
    win32gui.PostMessage(_main_handle(), win32con.WM_COMMAND, cid, 0)
    time.sleep(wait)


def dialogs():
    """Visible top-level dialogs owned by ArtiosCAD: list of (handle, title)."""
    a = app()
    return [(w.handle, w.window_text()) for w in a.windows()
            if w.is_visible() and w.class_name() == "#32770"]


def wait_dialog(title_part=None, timeout=30):
    t = time.time()
    while time.time() - t < timeout:
        for h, title in dialogs():
            if title_part is None or title_part in title:
                return app().window(handle=h)
        time.sleep(0.5)
    raise TimeoutError(f"dialog {title_part!r} not found")


def ctrl(dlg, cid, cls=None):
    """First descendant with this control id (and class, if given)."""
    for c in dlg.wrapper_object().descendants():
        if c.control_id() == cid and (cls is None or c.class_name() == cls):
            return c
    raise LookupError(f"control {cid} {cls or ''} not found")


def dump(dlg, path=None):
    """Write dialog controls (id, class, text) as UTF-8 for inspection."""
    lines = [f"DIALOG {dlg.window_text()!r}"]
    for c in dlg.wrapper_object().descendants():
        lines.append(f"{c.control_id()}\t{c.class_name()}\t{c.window_text()!r}")
    s = "\n".join(lines)
    if path:
        open(path, "w", encoding="utf-8").write(s)
    return s


def capture(hwnd, path):
    """Screenshot a window via PrintWindow (works when occluded)."""
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    w, h = r - l, b - t
    hdc = win32gui.GetWindowDC(hwnd)
    mfc = win32ui.CreateDCFromHandle(hdc)
    mem = mfc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc, w, h)
    mem.SelectObject(bmp)
    windll.user32.PrintWindow(hwnd, mem.GetSafeHdc(), 2)  # PW_RENDERFULLCONTENT
    info = bmp.GetInfo()
    img = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]),
                           bmp.GetBitmapBits(True), "raw", "BGRX", 0, 1)
    img.save(path)
    win32gui.DeleteObject(bmp.GetHandle()); mem.DeleteDC(); mfc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hdc)
    return path


def capture_main(path):
    return capture(_main_handle(), path)


def set_file_dialog_path(dlg, path):
    """Fill the filename edit (id 1148) of a standard open/save dialog and press OK."""
    ctrl(dlg, 1148, "Edit").set_edit_text(os.path.normpath(path))
    ctrl(dlg, 1, "Button").click()


if __name__ == "__main__":
    # CLI: gui.py shot <png> | gui.py dlgs | gui.py dump <title_part> <txt> | gui.py cmd <name|id>
    op = sys.argv[1]
    if op == "shot":
        print(capture_main(sys.argv[2]))
    elif op == "dlgs":
        for h, t in dialogs():
            print(h, t)
    elif op == "dump":
        d = wait_dialog(sys.argv[2] or None, 5)
        capture(d.handle, sys.argv[3] + ".png")
        dump(d, sys.argv[3])
    elif op == "cmd":
        command(int(sys.argv[2]) if sys.argv[2].isdigit() else sys.argv[2])


def _content_bbox(img):
    """Pixel bbox of non-background (drawn) content in a preview image."""
    g = img.convert("L").point(lambda v: 255 if v < 200 else 0)
    return g.getbbox()


def click_design_point(dlg, preview_id, design_bbox, pt, shot=None):
    """Click design coordinate pt=(x,y) inside a dialog preview control.

    design_bbox=(xmin,ymin,xmax,ymax) of the flat design in mm. The preview's
    drawn extents are detected from a PrintWindow capture and mapped linearly
    (design y up -> screen y down). The click is posted to the control, so no
    focus is needed.
    """
    pv = ctrl(dlg, preview_id)
    tmp = shot or os.path.join(os.environ.get("TEMP", "."), "acad_preview.png")
    capture(pv.handle, tmp)
    img = Image.open(tmp)
    # ignore a 4px frame border of the control itself
    inner = img.crop((4, 4, img.width - 4, img.height - 4))
    l, t, r, b = _content_bbox(inner)
    l, t, r, b = l + 4, t + 4, r + 4, b + 4
    xmin, ymin, xmax, ymax = design_bbox
    px = l + (pt[0] - xmin) / (xmax - xmin) * (r - l)
    py = b - (pt[1] - ymin) / (ymax - ymin) * (b - t)
    # Static previews don't take mouse input; the dialog does, in its client coords.
    pl, pt_ = win32gui.GetWindowRect(pv.handle)[:2]
    cx, cy = win32gui.ScreenToClient(dlg.handle, (pl + int(px), pt_ + int(py)))
    lp = (cy << 16) | (cx & 0xFFFF)
    win32gui.PostMessage(dlg.handle, win32con.WM_MOUSEMOVE, 0, lp)
    win32gui.PostMessage(dlg.handle, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
    win32gui.PostMessage(dlg.handle, win32con.WM_LBUTTONUP, 0, lp)
    time.sleep(1.5)
    return int(px), int(py)


def _deepest_child(parent, sx, sy):
    """Deepest visible child window containing screen point (sx, sy)."""
    h = parent
    while True:
        cx, cy = win32gui.ScreenToClient(h, (sx, sy))
        c = win32gui.ChildWindowFromPointEx(h, (cx, cy), 1 | 4)  # skip invisible/transparent
        if not c or c == h:
            return h
        h = c


def _board_mask(img):
    """Mask of board-colored pixels: the dominant non-white color (+-40), ignores UI/axis icons."""
    small = img.resize((img.width // 4, img.height // 4))
    hist = {}
    for c in small.getdata():
        if min(c) < 235 and max(c) - min(c) < 80:
            k = (c[0] // 8, c[1] // 8, c[2] // 8)
            hist[k] = hist.get(k, 0) + 1
    k = max(hist, key=hist.get)
    ref = (k[0] * 8 + 4, k[1] * 8 + 4, k[2] * 8 + 4)
    px = img.load()
    m = Image.new("L", img.size, 0); mp = m.load()
    for y in range(0, img.height):
        for x in range(0, img.width):
            c = px[x, y]
            if abs(c[0] - ref[0]) + abs(c[1] - ref[1]) + abs(c[2] - ref[2]) < 60:
                mp[x, y] = 255
    return m


def board_bbox_in_view(shot, _cache={}):
    """Screen bbox + mask of the board drawn in the canvas."""
    key = (shot, os.path.getmtime(shot))
    if key in _cache:
        return _cache[key][0]
    l, t = win32gui.GetWindowRect(_main_handle())[:2]
    img = Image.open(shot).convert("RGB")
    view = _view_rect()
    vx0, vy0, vx1, vy1 = (view[0] - l + 8, view[1] - t + 8, view[2] - l - 8, view[3] - t - 8)
    mask = _board_mask(img.crop((vx0, vy0, vx1, vy1)))
    bx = mask.getbbox()
    res = (l + vx0 + bx[0], t + vy0 + bx[1], l + vx0 + bx[2], t + vy0 + bx[3])
    _cache.clear(); _cache[key] = (res, mask.crop(bx))
    return res


def board_mask_in_view(shot):
    board_bbox_in_view(shot)
    return board_bbox_in_view.__defaults__[0][(shot, os.path.getmtime(shot))][1]


def _view_rect():
    """Screen rect of the active document canvas (largest AfxFrameOrView child)."""
    best = None
    def cb(c, _):
        nonlocal best
        if win32gui.IsWindowVisible(c) and win32gui.GetClassName(c).startswith("AfxFrameOrView"):
            r = win32gui.GetWindowRect(c)
            a = (r[2] - r[0]) * (r[3] - r[1])
            if best is None or a > best[0]:
                best = (a, r)
    win32gui.EnumChildWindows(_main_handle(), cb, None)
    return best[1]


ORIENTS = ("normal", "mirror_x", "mirror_y", "rot180")


def detect_orientation(dl, shot):
    """Which way the flat board appears in a top-down canvas shot.

    Compares the captured board silhouette with the design silhouette in the four
    axis-aligned orientations and returns the best match (3D top view is usually
    mirror_x because it shows the design from the inside)."""
    from dieline import board_mask
    from PIL import ImageOps, ImageChops
    cap = board_mask_in_view(shot).resize((200, 200))
    ref = board_mask(dl, (200, 200))
    cands = {"normal": ref, "mirror_x": ImageOps.mirror(ref),
             "mirror_y": ImageOps.flip(ref), "rot180": ref.rotate(180)}
    def score(m):
        diff = ImageChops.difference(cap, m).convert("L")
        return sum(diff.histogram()[128:])
    return min(cands, key=lambda k: score(cands[k]))


def canvas_point(design_bbox, pt, shot, orient="normal"):
    """Map a design point (mm) to screen coords using the board's drawn extents.

    Requires a top-down, fit-zoomed view (3D: tilt 90 + fit; 2D: fit)."""
    l, t, r, b = board_bbox_in_view(shot)
    xmin, ymin, xmax, ymax = design_bbox
    u = (pt[0] - xmin) / (xmax - xmin)
    v = (pt[1] - ymin) / (ymax - ymin)
    if orient in ("mirror_x", "rot180"):
        u = 1 - u
    if orient in ("mirror_y", "rot180"):
        v = 1 - v
    return int(l + u * (r - l)), int(b - v * (b - t))


def post_click(sx, sy, double=False):
    """Post a (double) left click at screen point to the window under it inside ArtiosCAD."""
    h = _deepest_child(_main_handle(), sx, sy)
    cx, cy = win32gui.ScreenToClient(h, (sx, sy))
    lp = (cy << 16) | (cx & 0xFFFF)
    win32gui.PostMessage(h, win32con.WM_MOUSEMOVE, 0, lp)
    win32gui.PostMessage(h, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
    win32gui.PostMessage(h, win32con.WM_LBUTTONUP, 0, lp)
    if double:
        win32gui.PostMessage(h, win32con.WM_LBUTTONDBLCLK, win32con.MK_LBUTTON, lp)
        win32gui.PostMessage(h, win32con.WM_LBUTTONUP, 0, lp)
    time.sleep(1.5)
    return h


def status_edits():
    """Visible Edit controls in the bottom status/tool bar, left to right."""
    eds = []
    mb = win32gui.GetWindowRect(_main_handle())[3]
    def cb(c, _):
        if win32gui.IsWindowVisible(c) and win32gui.GetClassName(c) == "Edit":
            r = win32gui.GetWindowRect(c)
            if r[1] > mb - 120:
                eds.append((r[0], c))
    win32gui.EnumChildWindows(_main_handle(), cb, None)
    return [c for _, c in sorted(eds)]


def set_status_edit(index, value):
    e = status_edits()[index]
    win32gui.SendMessage(e, win32con.WM_SETTEXT, 0, str(value))
    win32gui.PostMessage(e, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
    win32gui.PostMessage(e, win32con.WM_CHAR, 13, 0)
    win32gui.PostMessage(e, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
    time.sleep(1.5)


def view3d_top():
    """3D: look straight down and fit, so canvas_point() mapping works."""
    command(25574, 1.5)          # view angle tool -> status bar edits: rotate, tilt, spin
    set_status_edit(0, 0); set_status_edit(1, 90); set_status_edit(2, 0)
    command(27791, 1.5)          # fit zoom


def view3d_angle(rotate=35, tilt=30, spin=0):
    command(25574, 1.5)
    set_status_edit(0, rotate); set_status_edit(1, tilt); set_status_edit(2, spin)
    command(27791, 1.5)


def capture_canvas(path, pad=10):
    """Save only the drawing canvas (for 效果图), cropped to the visible content."""
    full = path + ".full.png"
    capture_main(full)
    l, t = win32gui.GetWindowRect(_main_handle())[:2]
    v = _view_rect()
    img = Image.open(full).crop((v[0] - l + 6, v[1] - t + 6, v[2] - l - 6, v[3] - t - 6))
    mask = img.convert("L").point(lambda x: 255 if x < 235 else 0)
    bb = mask.getbbox()
    if bb:
        img = img.crop((max(bb[0] - pad, 0), max(bb[1] - pad, 0),
                        min(bb[2] + pad, img.width), min(bb[3] + pad, img.height)))
    img.save(path)
    os.remove(full)
    return path


def save_as(path, timeout=20):
    """Save the active document (ARD in 2D, A3D in 3D) to an absolute path."""
    path = os.path.normpath(path)
    if os.path.exists(path):
        os.remove(path)
    command("save_as", 2)
    set_file_dialog_path(wait_dialog(None, timeout), path)
    t = time.time()
    while time.time() - t < timeout and not os.path.exists(path):
        time.sleep(0.5)
    if not os.path.exists(path):
        raise RuntimeError(f"save failed: {path}; dialogs={dialogs()}")
    return path


def deselect():
    """Drop the current tool/selection (Esc to the canvas) so renders show true colors."""
    v = _view_rect()
    h = _deepest_child(_main_handle(), (v[0] + v[2]) // 2, (v[1] + v[3]) // 2)
    for _ in range(2):
        win32gui.PostMessage(h, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        win32gui.PostMessage(h, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
        time.sleep(0.5)
