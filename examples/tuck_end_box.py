"""Reverse tuck end box (反插式管式折叠纸盒, ECMA A20-like), parametric.

Layout along x: glue flap | side W | front L | side W | back L ; body height D.
Top lid + tuck on back panel, bottom lid + tuck on front panel (reverse tuck).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "acad"))
from dieline import Dieline, CUT, CREASE

L, W, D = 60, 30, 100      # 内尺寸 长 宽 高 (mm)
GLUE = 14                  # 糊头宽
TUCK = 15                  # 插舌高
DUST = 0.8                 # 防尘翼高 = DUST * W
R = 5                      # 圆角


def build():
    dl = Dieline(f"tuck_end_{L}x{W}x{D}")
    x = [0, GLUE, GLUE + W, GLUE + W + L, GLUE + 2 * W + L, GLUE + 2 * W + 2 * L]
    g, s1, f, s2, b = (x[0], x[1]), (x[1], x[2]), (x[2], x[3]), (x[3], x[4]), (x[4], x[5])

    # vertical panel creases
    for xi in x[1:5]:
        dl.line((xi, 0), (xi, D), CREASE)
    dl.line((x[5], 0), (x[5], D), CUT)                       # free edge of back panel
    # glue flap (chamfered)
    dl.poly([(x[1], 0), (0, 6), (0, D - 6), (x[1], D)], CUT)

    # panel top/bottom edges
    dl.line((f[0], D), (f[1], D), CUT)                       # front top: free
    dl.line((b[0], 0), (b[1], 0), CUT)                       # back bottom: free
    for a, c in (s1, s2):
        dl.line((a, D), (c, D), CREASE); dl.line((a, 0), (c, 0), CREASE)
    dl.line((b[0], D), (b[1], D), CREASE)                    # top lid hinge
    dl.line((f[0], 0), (f[1], 0), CREASE)                    # bottom lid hinge

    def lid(x0, x1, y0, sgn):
        """Lid of depth W plus rounded tuck flap, growing in direction sgn (+1 up, -1 down)."""
        y1 = y0 + sgn * W
        y2 = y1 + sgn * TUCK
        dl.line((x0, y0), (x0, y1), CUT); dl.line((x1, y0), (x1, y1), CUT)
        dl.line((x0 + 1, y1), (x1 - 1, y1), CREASE)          # tuck crease
        dl.line((x0, y1), (x0 + 1, y1), CUT); dl.line((x1 - 1, y1), (x1, y1), CUT)
        pts = [(x0 + 1, y1), (x0 + 1, y2), (x1 - 1, y2), (x1 - 1, y1)]
        dl.fillet_poly(pts, R, CUT)

    def dust(x0, x1, y0, sgn):
        h = DUST * W
        pts = [(x0, y0), (x0 + 2, y0 + sgn * h), (x1 - 6, y0 + sgn * h), (x1 - 1, y0 + sgn * 4), (x1, y0)]
        dl.fillet_poly(pts, 3, CUT)

    lid(b[0], b[1], D, +1)
    lid(f[0], f[1], 0, -1)
    for a, c in (s1, s2):
        dust(a, c, D, +1)
    # bottom dust flaps mirrored so the relief faces the lid side
    for a, c in (s1, s2):
        h = DUST * W
        pts = [(c, 0), (c - 2, -h), (a + 6, -h), (a + 1, -4), (a, 0)]
        dl.fillet_poly(pts, 3, CUT)

    dl.notes["base"] = ((f[0] + f[1]) / 2, D / 2)            # 3D 底面: front panel
    return dl
