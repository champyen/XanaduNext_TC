"""Phase 5b: patch EQUIP.tbl item names/descriptions (same hunk engine)."""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tblpatch import patch_buffer  # noqa: E402


def arc_get(arc, dirp, want):
    d = open(dirp, "rb").read()
    offs = 0
    for i in range((len(d) - 4) // 108):
        e = d[i * 108:(i + 1) * 108]
        nm = e[:100].split(b"\x00")[0]
        sz = struct.unpack("<I", e[100:104])[0]
        if nm == want:
            return open(arc, "rb").read()[offs:offs + sz]
        offs += sz
    raise KeyError(want)


GOG_ARC = r"C:\Users\champ\workspace\XanaduNext_workspace\XanaduNext\DATA\equip\equip.arc"
GOG_DIR = r"C:\Users\champ\workspace\XanaduNext_workspace\XanaduNext\DATA\equip\equip.dir"
CN_ARC = (r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_Steam_CN\MainData\DATA\equip"
          r"\equip.arc")
CN_DIR = (r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_Steam_CN\MainData\DATA\equip"
          r"\equip.dir")
OUT = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\patch\equip\EQUIP.tbl"


def main():
    gog = arc_get(GOG_ARC, GOG_DIR, b"EQUIP.tbl")
    cn = arc_get(CN_ARC, CN_DIR, b"EQUIP.tbl")
    assert len(gog) == len(cn) == 708608
    out, (ok, skip, warn) = patch_buffer(gog, cn, tag="EQUIP.tbl")
    assert len(out) == 708608
    # whole-file JP normalization (untranslated regions keep JP forms;
    # see jpscan docstring). Length-preserving, SUB slots as needed.
    from jpscan import build_map as _js_map
    from jpscan import load_sub as _js_sub
    from jpscan import normalize_blob as _js_norm
    out2, st = _js_norm(out, _js_map(), _js_sub(), "EQUIP.tbl")
    print("jp-scan runs=%d converted=%d skipped=%d" % st)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "wb").write(out2)
    print("patched=%d skipped=%d warnings=%d -> %s" % (ok, skip, warn, OUT))


if __name__ == "__main__":
    main()
