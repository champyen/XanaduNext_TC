"""Debug builds: Simplified-from-scratch flow validation.

T1 (repack-only): GOG + Simplified area00 scripts/inf (Text sources as-is)
  + Simplified GOG exes. GOG fonts untouched.
T2 (full-CN): T1 + our rebuilt Simplified fonts in system.arc.
Run both to name entry:
  T1 crashes        -> repack/scripts/exe issue (not fonts)
  T1 works+T2 fails -> font pipeline issue (likely .dat size!)
  both work         -> flow valid; TW-data bug -> bisect TW assets
"""
import io
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from repack import rebuild_arc  # noqa: E402

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="backslashreplace")

WS = r"C:\Users\champ\workspace"
GOG = os.path.join(WS, "XanaduNext")
CN_TEXT = os.path.join(WS, "Xanadu_Steam_CN")
CANON = re.compile(r"^MP_([0-9a-f]{4})\.scp$", re.IGNORECASE)


def num_of(fn):
    m = re.search(r"MP_([0-9a-f]{4})\.scp$", fn, re.IGNORECASE)
    return m.group(1).lower() if m else None


def area00_sources():
    ap = os.path.join(CN_TEXT, "Text", "map", "Final_Size_Control", "area00")
    by_num = {}
    for f in os.listdir(ap):
        n = num_of(f)
        if n:
            by_num.setdefault(n, []).append(f)
    out = {}
    for n, fs in by_num.items():
        canon = [f for f in fs if CANON.match(f)]
        if canon:
            out[canon[0]] = open(os.path.join(ap, canon[0]), "rb").read()
    # extra boss fix (no canonical in area00 set)
    for root, _, fs in os.walk(os.path.join(CN_TEXT, "Text", "map")):
        if os.path.abspath(root) == os.path.abspath(
                os.path.join(CN_TEXT, "Text", "map", "Final_Size_Control")):
            continue
        for f in fs:
            if num_of(f) == "0087":
                out["MP_0087.scp"] = open(os.path.join(root, f), "rb").read()
    return out


def build(tag, with_fonts):
    dst = os.path.join(WS, tag)
    if os.path.exists(dst):
        print("removing old", tag)
        shutil.rmtree(dst)
    print("copying for", tag)
    shutil.copytree(GOG, dst)
    # exes: Simplified GOG builds (known-good baseline, not under test)
    for local, cn_name in (("XANADU.exe", "GOG_XANADU.exe"),
                           ("xanadu_cfg.exe", "GOG_xanadu_cfg.exe")):
        open(os.path.join(dst, local), "wb").write(
            open(os.path.join(CN_TEXT, "GOG", cn_name), "rb").read())
    # area00 scripts + inf (Simplified Text sources as-is)
    rep = area00_sources()
    rep["area00.inf"] = open(os.path.join(
        CN_TEXT, "Text", "Map_name", "area00.inf"), "rb").read()
    r, a = rebuild_arc(os.path.join(dst, "DATA/Map/area00.arc"),
                       os.path.join(dst, "DATA/Map/area00.dir"), rep)
    print(tag, "area00 replaced=%d added=%s" % (r, a))
    if with_fonts:
        fdir = os.path.join(WS, "Xanadu_TC", "patch", "cn_test")
        r, a = rebuild_arc(
            os.path.join(dst, "DATA/SYSTEM/system.arc"),
            os.path.join(dst, "DATA/SYSTEM/system.dir"),
            {"font_scn.dat": open(os.path.join(fdir, "font_scn_CN.dat"),
                                  "rb").read(),
             "font_sys.dat": open(os.path.join(fdir, "font_sys_CN.dat"),
                                  "rb").read()})
        print(tag, "fonts replaced=%d added=%s" % (r, a))
    print(tag, "DONE")


if __name__ == "__main__":
    build("Xanadu_CN_T1", with_fonts=False)
    build("Xanadu_CN_T2", with_fonts=True)
