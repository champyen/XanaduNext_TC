"""Phase 7 build verification (run after tools/repack.py).

For every rebuilt arc: .dir parses (sum == arc len, count trailer),
every replaced entry re-extracts byte-identical to its patch file,
every untouched entry identical to the GOG original. Drop-ins compared.
"""
import io
import os
import struct
import sys

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="backslashreplace")

WS = r"C:\Users\champ\workspace"
GOG = os.path.join(WS, "XanaduNext")
TW = os.path.join(WS, "Xanadu_TW")
PATCH = os.path.join(WS, "Xanadu_TC", "patch")

fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (" | " + detail if detail else ""))
    if not cond:
        fails.append(name)


def read_dir(dirp):
    d = open(dirp, "rb").read()
    recs = []
    for i in range((len(d) - 4) // 108):
        e = d[i * 108:(i + 1) * 108]
        recs.append((e[:100].split(b"\x00")[0].decode("cp932"),
                     struct.unpack("<I", e[100:104])[0]))
    cnt = struct.unpack("<I", d[-4:])[0]
    return recs, cnt, d


def slice_arc(arcp, recs):
    blob = open(arcp, "rb").read()
    out, offs = {}, 0
    for nm, sz in recs:
        out[nm] = blob[offs:offs + sz]
        offs += sz
    assert offs == len(blob), (arcp, offs, len(blob))
    return out


def check_arc(sub, repl_map):
    """repl_map: {entry_name: patch_relpath}."""
    g_arc = os.path.join(GOG, sub + ".arc")
    g_dir = os.path.join(GOG, sub + ".dir")
    t_arc = os.path.join(TW, sub + ".arc")
    t_dir = os.path.join(TW, sub + ".dir")
    gr, gc, _ = read_dir(g_dir)
    tr, tc, _ = read_dir(t_dir)
    check("%s dir count" % sub, tc == len(tr), str(tc))
    check("%s entry sets equal" % sub,
          [n for n, _ in gr] == [n for n, _ in tr])
    # flag bytes [104:108] (e.g. compressed marker) must be preserved
    _gd = open(g_dir, "rb").read()
    _td = open(t_dir, "rb").read()
    _n = (len(_gd) - 4) // 108
    _flagbad = sum(1 for _i in range(_n)
                   if _gd[_i * 108 + 104:_i * 108 + 108]
                   != _td[_i * 108 + 104:_i * 108 + 108])
    check("%s dir flags preserved" % sub, _flagbad == 0, str(_flagbad))
    gp = slice_arc(g_arc, gr)
    tp = slice_arc(t_arc, tr)
    ok_r = ok_u = 0
    for nm in tp:
        if nm in repl_map:
            want = open(os.path.join(PATCH, repl_map[nm]), "rb").read()
            if tp[nm] == want:
                ok_r += 1
            else:
                check("%s REPLACE %s" % (sub, nm), False, "bytes differ")
        else:
            if tp[nm] == gp[nm]:
                ok_u += 1
            else:
                check("%s UNTOUCHED %s" % (sub, nm), False, "bytes differ")
    # .dir sizes
    tmap = dict(tr)
    bad = [n for n, s in tmap.items()
           if s != (len(open(os.path.join(PATCH, repl_map[n]), "rb").read())
                    if n in repl_map else dict(gr)[n])]
    check("%s dir sizes" % sub, not bad, str(bad[:3]))
    print("  %s: replaced-ok=%d untouched-ok=%d" % (sub, ok_r, ok_u))


def main():
    pmap = {}
    for area in ("area00", "area05", "area06", "area07", "area08", "area09",
                 "area10"):
        for f in os.listdir(os.path.join(PATCH, "map", area)):
            pmap[f] = "map/%s/%s" % (area, f)
        pmap[area + ".inf"] = "Map/%s.inf" % area
    # split per arc (inf names unique per area dir listing below)
    for area in ("area00", "area05", "area06", "area07", "area08", "area09",
                 "area10"):
        rep = {f: "map/%s/%s" % (area, f)
               for f in os.listdir(os.path.join(PATCH, "map", area))}
        rep[area + ".inf"] = "Map/%s.inf" % area
        check_arc("DATA/Map/" + area, rep)
    check_arc("DATA/SYSTEM/system",
              {"font_scn.dat": "font_scn_TW.dat",
               "font_sys.dat": "font_sys_TW.dat"})
    check_arc("DATA/equip/equip",
              {"EQUIP.tbl": "equip/EQUIP.tbl",
               "guardian.tbl": "equip/guardian.tbl"})
    rep = {f: "picture/" + f for f in os.listdir(os.path.join(PATCH, "picture"))}
    check_arc("DATA/picture/picture", rep)
    for rel in ("DATA/chr/Object.tbl", "XANADU.exe", "xanadu_cfg.exe"):
        a = open(os.path.join(TW, rel), "rb").read()
        if rel.startswith("DATA"):
            src = {"DATA/chr/Object.tbl": "chr/Object.tbl"}[rel]
        else:
            src = rel
        b = open(os.path.join(PATCH, src), "rb").read()
        check("drop-in %s" % rel, a == b, str(len(a)))
    print("----")
    print("BUILD-VERIFY: %s (%d failures)" %
          ("ALL PASS" if not fails else "FAILURES", len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
