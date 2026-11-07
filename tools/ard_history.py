"""Dump the geometry command history embedded in an ArtiosCAD .ARD file.

ARD is a binary 'I-code' format, but ArtiosCAD keeps the construction log as
readable commands (rect by, rectangle offset, cen radius, SPLIT, dup, trans rot,
cha ... type N). Reading it shows exactly how a template was drawn.
Usage: python -I ard_history.py <file.ARD> [out.txt]
"""
import re, sys

KEYS = re.compile(r"^(rect|rectangle|to |at |cen |con |circle|move|SPLIT|del |dup|copyd|trans|paste|"
                  r"cha |REBLEND|PICKUP|ASIZE|DSIZE|TSIZE|GRAIN|[A-Z]:?Defaults)")


def history(path):
    data = open(path, "rb").read()
    out = []
    for m in re.finditer(rb"[\x20-\x7e]{6,}", data):
        s = m.group().decode("latin1")
        s2 = s[1:] if s and not KEYS.match(s) and KEYS.match(s[1:]) else s   # strip length-prefix byte
        if KEYS.match(s2) or "Defaults\\" in s2:
            out.append(s2)
    return out


if __name__ == "__main__":
    lines = history(sys.argv[1])
    txt = "\n".join(lines)
    if len(sys.argv) > 2:
        open(sys.argv[2], "w", encoding="utf-8").write(txt)
    sys.stdout.buffer.write(txt.encode("utf-8") + b"\n")
