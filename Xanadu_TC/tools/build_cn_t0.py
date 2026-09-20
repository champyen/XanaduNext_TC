"""Debug single-variable builds (all from clean GOG):
T0a: stock + Simplified GOG exes only (exe suspect?)
T0b: stock + repacked area00 only, GOG exe (arc/text suspect?)
Compare against STOCK (user tests XanaduNext unmodified) and T1 (both).
"""
import io
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from repack import rebuild_arc  # noqa: E402

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="backslashreplace")

WS = r"C:\Users\champ\workspace\XanaduNext_workspace"
GOG = os.path.join(WS, "XanaduNext")
CN = os.path.join(WS, "Xanadu_Steam_CN")


def build(tag, exes, area00):
    import re
    dst = os.path.join(WS, tag)
    if os.path.exists(dst):
        print("removing old", tag)
        shutil.rmtree(dst)
    print("copying for", tag)
    shutil.copytree(GOG, dst)
    if exes:
        for local, cn_name in (("XANADU.exe", "GOG_XANADU.exe"),
                               ("xanadu_cfg.exe", "GOG_xanadu_cfg.exe")):
            open(os.path.join(dst, local), "wb").write(
                open(os.path.join(CN, "GOG", cn_name), "rb").read())
        print(tag, "exes swapped")
    if area00:
        CANON = re.compile(r"^MP_([0-9a-f]{4})\.scp$", re.IGNORECASE)

        def num_of(fn):
            m = re.search(r"MP_([0-9a-f]{4})\.scp$", fn, re.IGNORECASE)
            return m.group(1).lower() if m else None

        ap = os.path.join(CN, "Text", "map", "Final_Size_Control", "area00")
        by_num = {}
        for f in os.listdir(ap):
            n = num_of(f)
            if n:
                by_num.setdefault(n, []).append(f)
        rep = {}
        for n, fs in by_num.items():
            canon = [f for f in fs if CANON.match(f)]
            if canon:
                rep[canon[0]] = open(os.path.join(ap, canon[0]), "rb").read()
        for root, _, fs in os.walk(os.path.join(CN, "Text", "map")):
            if os.path.abspath(root) == os.path.abspath(
                    os.path.join(CN, "Text", "map", "Final_Size_Control")):
                continue
            for f in fs:
                if num_of(f) == "0087":
                    rep["MP_0087.scp"] = open(os.path.join(root, f),
                                              "rb").read()
        rep["area00.inf"] = open(os.path.join(CN, "Text", "Map_name",
                                              "area00.inf"), "rb").read()
        r, a = rebuild_arc(os.path.join(dst, "DATA/Map/area00.arc"),
                           os.path.join(dst, "DATA/Map/area00.dir"), rep)
        print(tag, "area00 replaced=%d added=%s" % (r, a))
    print(tag, "DONE")


if __name__ == "__main__":
    build("Xanadu_CN_T0a", exes=True, area00=False)
    build("Xanadu_CN_T0b", exes=False, area00=True)
