"""Exact 2D dieline builder -> DXF that ArtiosCAD imports with correct line types.

ArtiosCAD's "Artios DWG/DXF - Metric" import profile maps DXF ACI color -> line type
(see ServerLib/Artios_DXF_-_Metric.ITUNE), so each entity's color IS its line type.
Units: mm, y axis up (same as ArtiosCAD).
"""
import math
import ezdxf

# ArtiosCAD line types (= DXF color on import)
CUT = 1          # 切割线 (black in ArtiosCAD)
CREASE = 2       # 压痕线 (red)
PARTIAL = 3      # 半切/划痕 (inferred from DDES 300 range)
PERF = 4         # 打孔/齿刀 (inferred from DDES 400 range)
REV_CREASE = 8   # 反向压痕 (DDES 290; 设计2 uses it)
ANNOT = 7        # 注释/非结构线

TYPE_NAMES = {CUT: "cut", CREASE: "crease", PARTIAL: "partial", PERF: "perf",
              REV_CREASE: "rev_crease", ANNOT: "annot"}


def _rot(p, c, deg):
    a = math.radians(deg)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * math.cos(a) - y * math.sin(a), c[1] + x * math.sin(a) + y * math.cos(a))


class Line:
    def __init__(self, a, b, t=CUT):
        self.a, self.b, self.t = tuple(map(float, a)), tuple(map(float, b)), t

    def map(self, f, flip=False):
        return Line(f(self.a), f(self.b), self.t)

    def points(self):
        return [self.a, self.b]


class Arc:
    """Arc by center/radius/start/end angle (deg, CCW from start to end)."""
    def __init__(self, c, r, a0, a1, t=CUT):
        self.c, self.r, self.a0, self.a1, self.t = tuple(map(float, c)), float(r), a0 % 360, a1 % 360, t

    def p(self, ang):
        return (self.c[0] + self.r * math.cos(math.radians(ang)),
                self.c[1] + self.r * math.sin(math.radians(ang)))

    @property
    def start(self):
        return self.p(self.a0)

    @property
    def end(self):
        return self.p(self.a1)

    def map(self, f, flip=False):
        """Map through a rigid transform; flip=True for mirror transforms."""
        c = f(self.c)
        s, e = f(self.start), f(self.end)
        a0 = math.degrees(math.atan2(s[1] - c[1], s[0] - c[0]))
        a1 = math.degrees(math.atan2(e[1] - c[1], e[0] - c[0]))
        if flip:
            a0, a1 = a1, a0
        return Arc(c, self.r, a0, a1, self.t)

    def points(self, n=24):
        sweep = (self.a1 - self.a0) % 360 or 360
        return [self.p(self.a0 + sweep * i / n) for i in range(n + 1)]


class Dieline:
    def __init__(self, name="design"):
        self.name = name
        self.items = []
        self.notes = {}   # e.g. base panel point for 3D: notes["base"] = (x, y)

    # ---- primitives -------------------------------------------------
    def line(self, a, b, t=CUT):
        self.items.append(Line(a, b, t)); return self.items[-1]

    def poly(self, pts, t=CUT, closed=False):
        """Polyline; t may be a single type or a list (one per segment)."""
        segs = list(zip(pts, pts[1:] + (pts[:1] if closed else [])))
        ts = t if isinstance(t, (list, tuple)) else [t] * len(segs)
        return [self.line(a, b, tt) for (a, b), tt in zip(segs, ts)]

    def rect(self, x, y, w, h, t=CUT, types=None):
        """Axis-aligned rectangle; types=(bottom,right,top,left) overrides t."""
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        return self.poly(pts, list(types) if types else t, closed=True)

    def arc(self, c, r, a0, a1, t=CUT):
        self.items.append(Arc(c, r, a0, a1, t)); return self.items[-1]

    def arc3(self, p0, p1, r, t=CUT, ccw=True):
        """Arc from p0 to p1 with radius r (minor arc), CCW or CW."""
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        d = math.hypot(dx, dy)
        h = math.sqrt(max(r * r - d * d / 4, 0))
        s = 1 if ccw else -1
        c = (mx - s * dy / d * h, my + s * dx / d * h)
        a0 = math.degrees(math.atan2(p0[1] - c[1], p0[0] - c[0]))
        a1 = math.degrees(math.atan2(p1[1] - c[1], p1[0] - c[0]))
        return self.arc(c, r, a0, a1, t) if ccw else self.arc(c, r, a1, a0, t)

    def circle(self, c, r, t=CUT):
        return self.arc(c, r, 0, 360, t)

    # ---- corner rounding (ArtiosCAD REBLEND) --------------------------
    def fillet_poly(self, pts, radius, t=CUT, closed=False, radii=None):
        """Polyline with rounded inner vertices. radii: per-vertex radius list (0 = sharp)."""
        n = len(pts)
        rs = radii or [radius] * n
        idx = range(n) if closed else range(1, n - 1)
        cut = {}
        for i in idx:
            r = rs[i]
            if not r:
                continue
            p, a, b = pts[i], pts[i - 1], pts[(i + 1) % n]
            u = _unit(a, p); v = _unit(b, p)
            ang = math.acos(max(-1, min(1, u[0] * v[0] + u[1] * v[1])))
            if ang < 1e-3 or ang > math.pi - 1e-3:
                continue  # collinear or reversed: leave sharp
            k = r / math.tan(ang / 2)
            k = min(k, 0.49 * math.dist(a, p), 0.49 * math.dist(b, p))  # never overrun a segment
            rr = k * math.tan(ang / 2)
            s, e = (p[0] + u[0] * k, p[1] + u[1] * k), (p[0] + v[0] * k, p[1] + v[1] * k)
            bis = _unit((u[0] + v[0] + p[0], u[1] + v[1] + p[1]), p)
            dc = rr / math.sin(ang / 2)
            c = (p[0] + bis[0] * dc, p[1] + bis[1] * dc)
            turn = (p[0] - a[0]) * (b[1] - p[1]) - (p[1] - a[1]) * (b[0] - p[0])
            cut[i] = (s, e, c, rr, turn > 0)
        out = []
        seq = list(range(n)) + ([0] if closed else [])
        cur = cut[seq[0]][1] if seq[0] in cut else pts[seq[0]]
        for i in seq[1:]:
            if i in cut:
                s, e, c, rr, ccw = cut[i]
                out.append(self.line(cur, s, t))
                a0 = math.degrees(math.atan2(s[1] - c[1], s[0] - c[0]))
                a1 = math.degrees(math.atan2(e[1] - c[1], e[0] - c[0]))
                out.append(self.arc(c, rr, a0, a1, t) if ccw else self.arc(c, rr, a1, a0, t))
                cur = e
            else:
                out.append(self.line(cur, pts[i], t)); cur = pts[i]
        return out

    # ---- transforms (ArtiosCAD dup/trans) ---------------------------
    def _add_mapped(self, items, f, flip=False):
        new = [it.map(f, flip) for it in items]
        self.items.extend(new)
        return new

    def mirror_x(self, items, x0):
        """Mirror about vertical line x = x0 (ArtiosCAD 'neg x')."""
        return self._add_mapped(items, lambda p: (2 * x0 - p[0], p[1]), flip=True)

    def mirror_y(self, items, y0):
        """Mirror about horizontal line y = y0 (ArtiosCAD 'neg y')."""
        return self._add_mapped(items, lambda p: (p[0], 2 * y0 - p[1]), flip=True)

    def move(self, items, dx, dy):
        return self._add_mapped(items, lambda p: (p[0] + dx, p[1] + dy))

    def rotate_copy(self, items, center, deg):
        return self._add_mapped(items, lambda p: _rot(p, center, deg))

    def polar_array(self, items, center, count, step=None):
        """Copies rotated about center (设计2 style: 22.5/45/90 deg)."""
        step = step if step is not None else 360 / count
        out = []
        for k in range(1, count):
            out += self.rotate_copy(items, center, step * k)
        return out

    def set_type(self, items, t):
        for it in items:
            it.t = t

    # ---- cleanup / output -------------------------------------------
    def dedupe(self, tol=1e-3):
        """Remove overlapping duplicate lines (keep the stronger type: cut wins)."""
        seen = {}
        keep = []
        for it in self.items:
            if isinstance(it, Line):
                k = tuple(sorted([(round(it.a[0] / tol), round(it.a[1] / tol)),
                                  (round(it.b[0] / tol), round(it.b[1] / tol))]))
                if k in seen:
                    if it.t == CUT:
                        seen[k].t = CUT
                    continue
                seen[k] = it
            keep.append(it)
        self.items = keep

    def bbox(self):
        pts = [p for it in self.items for p in it.points()]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def to_dxf(self, path):
        self.dedupe()
        doc = ezdxf.new("R2000")
        doc.header["$INSUNITS"] = 4  # mm
        doc.header["$MEASUREMENT"] = 1
        msp = doc.modelspace()
        for it in self.items:
            att = {"color": it.t, "layer": TYPE_NAMES.get(it.t, str(it.t))}
            if isinstance(it, Line):
                msp.add_line(it.a, it.b, dxfattribs=att)
            elif abs((it.a1 - it.a0) % 360) < 1e-9:
                msp.add_circle(it.c, it.r, dxfattribs=att)
            else:
                msp.add_arc(it.c, it.r, it.a0, it.a1, dxfattribs=att)
        doc.saveas(path)
        return path

    def preview(self, path, px_per_mm=4, margin=20):
        """PNG preview with ArtiosCAD-like colors, for self-checking before import."""
        from PIL import Image, ImageDraw
        x0, y0, x1, y1 = self.bbox()
        W, H = int((x1 - x0) * px_per_mm) + 2 * margin, int((y1 - y0) * px_per_mm) + 2 * margin
        img = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(img)
        col = {CUT: (0, 0, 0), CREASE: (220, 0, 0), REV_CREASE: (0, 120, 255),
               PERF: (0, 160, 0), PARTIAL: (255, 140, 0)}
        tf = lambda p: (margin + (p[0] - x0) * px_per_mm, H - margin - (p[1] - y0) * px_per_mm)
        for it in self.items:
            pts = [tf(p) for p in it.points()]
            d.line(pts, fill=col.get(it.t, (128, 128, 128)), width=2)
        if "base" in self.notes:
            bx, by = tf(self.notes["base"]); d.ellipse((bx - 6, by - 6, bx + 6, by + 6), outline=(0, 0, 255), width=3)
        img.save(path)
        return path


def _unit(p, q):
    """Unit vector from q towards p."""
    dx, dy = p[0] - q[0], p[1] - q[1]
    L = math.hypot(dx, dy)
    return (dx / L, dy / L)


def board_mask(dl, size):
    """Filled silhouette of the flat board as an L-mode image of `size` (w, h), y up."""
    from PIL import Image, ImageDraw
    W, H = size
    x0, y0, x1, y1 = dl.bbox()
    m = 2
    sx, sy = (W - 2 * m) / (x1 - x0), (H - 2 * m) / (y1 - y0)
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    tf = lambda p: (m + (p[0] - x0) * sx, H - m - (p[1] - y0) * sy)
    for it in dl.items:
        if it.t == CUT:
            d.line([tf(p) for p in it.points()], fill=255, width=2)
    ImageDraw.floodfill(img, (0, 0), 128)           # outside
    return img.point(lambda v: 0 if v == 128 else 255)
