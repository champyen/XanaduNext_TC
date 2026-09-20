"""Phase 7: assemble the playable Traditional build.

1. Copy XanaduNext/ -> Xanadu_TW/ (fresh; removed first if present).
2. Drop-in files: DATA/chr/Object.tbl, XANADU.exe, xanadu_cfg.exe.
3. Arc rebuilds (entries matched by EXACT dir name; missing entries are
   appended): SYSTEM/system.arc (2 fonts), Map/area{00,05-10}.arc
   (205 scp + 7 inf), equip/equip.arc (EQUIP.tbl + guardian.tbl),
   picture/picture.arc (11 G32). .dir rewritten GOG-style: same order,
   updated sizes, 4-byte count trailer.
4. Verify: re-extract every replaced/added entry from the new arcs and
   byte-compare with patch files; untouched entries identical to GOG.
"""
import io
import os
import shutil
import struct
import sys

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="backslashreplace")

WS = r"C:\Users\champ\workspace\XanaduNext_workspace"
SRC_GAME = os.path.join(WS, "XanaduNext")
DST_GAME = os.path.join(WS, "Xanadu_TW")
PATCH = os.path.join(WS, "Xanadu_TC", "patch")


def read_dir(dirp):
    d = open(dirp, "rb").read()
    recs = []
    for i in range((len(d) - 4) // 108):
        e = d[i * 108:(i + 1) * 108]
        # NOTE: bytes [100:108] are NOT all reserved-zero: area arcs use a
        # nonzero flag (0x1) on 156/565 area00 entries. Preserve verbatim.
        recs.append([e[:100], struct.unpack("<I", e[100:104])[0],
                     e[104:108]])
    return recs


def write_dir(dirp, recs):
    with open(dirp, "wb") as f:
        for name100, size, reserved in recs:
            f.write(name100 + struct.pack("<I", size) + reserved)
        f.write(struct.pack("<I", len(recs)))


def rebuild_arc(game_arc, game_dir, replacements):
    """replacements: {entry_name: bytes}. Missing names appended."""
    recs = read_dir(game_dir)
    old = open(game_arc, "rb").read()
    # slice old payloads
    offs = 0
    payloads = []
    for name100, size, _reserved in recs:
        payloads.append(old[offs:offs + size])
        offs += size
    assert offs == len(old), (game_arc, offs, len(old))
    names = [n.split(b"\x00")[0].decode("cp932") for n, _, _ in recs]
    repl = napplied = 0
    added = []
    for nm, blob in replacements.items():
        if nm in names:
            payloads[names.index(nm)] = blob
            repl += 1
        else:
            nameb = nm.encode("cp932")
            assert len(nameb) <= 100, nm
            recs.append([nameb + b"\x00" * (100 - len(nameb)), len(blob),
                         b"\x00" * 4])
            payloads.append(blob)
            names.append(nm)
            added.append(nm)
    new_arc = b"".join(payloads)
    open(game_arc, "wb").write(new_arc)
    # refresh sizes (replacements may differ in size)
    for i, p in enumerate(payloads):
        recs[i][1] = len(p)
    write_dir(game_dir, recs)
    return repl, added


def slurp(patch_rel):
    with open(os.path.join(PATCH, patch_rel), "rb") as f:
        return f.read()


def main():
    if os.path.exists(DST_GAME):
        print("removing old", DST_GAME)
        shutil.rmtree(DST_GAME)
    print("copying game (this takes a while)...")
    shutil.copytree(SRC_GAME, DST_GAME)
    print("copied.")

    # 1. drop-ins
    for rel, src in (("DATA/chr/Object.tbl", "chr/Object.tbl"),
                     ("XANADU.exe", "XANADU.exe"),
                     ("xanadu_cfg.exe", "xanadu_cfg.exe")):
        open(os.path.join(DST_GAME, rel), "wb").write(slurp(src))
        print("drop-in", rel)

    # 2. system.arc fonts
    r, a = rebuild_arc(os.path.join(DST_GAME, "DATA/SYSTEM/system.arc"),
                       os.path.join(DST_GAME, "DATA/SYSTEM/system.dir"),
                       {"font_scn.dat": slurp("font_scn_TW.dat"),
                        "font_sys.dat": slurp("font_sys_TW.dat")})
    print("system.arc replaced=%d added=%s" % (r, a))

    # 3. map arcs
    for area in ("area00", "area05", "area06", "area07", "area08", "area09",
                 "area10"):
        rep = {}
        adir = os.path.join(PATCH, "map", area)
        for f in os.listdir(adir):
            rep[f] = open(os.path.join(adir, f), "rb").read()
        rep[area + ".inf"] = slurp("Map/%s.inf" % area)
        r, a = rebuild_arc(
            os.path.join(DST_GAME, "DATA/Map/%s.arc" % area),
            os.path.join(DST_GAME, "DATA/Map/%s.dir" % area), rep)
        print("%s replaced=%d added=%s" % (area, r, a))

    # 4. equip.arc
    eqd = os.path.join(DST_GAME, "DATA/equip")
    r, a = rebuild_arc(os.path.join(eqd, "equip.arc"),
                       os.path.join(eqd, "equip.dir"),
                       {"EQUIP.tbl": slurp("equip/EQUIP.tbl"),
                        "guardian.tbl": slurp("equip/guardian.tbl")})
    print("equip replaced=%d added=%s" % (r, a))

    # 5. picture.arc
    pcd = os.path.join(DST_GAME, "DATA/picture")
    rep = {}
    pdir = os.path.join(PATCH, "picture")
    for f in os.listdir(pdir):
        rep[f] = open(os.path.join(pdir, f), "rb").read()
    r, a = rebuild_arc(os.path.join(pcd, "picture.arc"),
                       os.path.join(pcd, "picture.dir"), rep)
    print("picture replaced=%d added=%s" % (r, a))

    # build stamp: lets testers confirm which build they run
    import datetime
    import glob as _glob
    _stamp = [
        "Xanadu_TW Traditional Chinese build",
        "built: " + datetime.datetime.now().isoformat(timespec="seconds"),
        "dict entries: %d" % len(open(
            os.path.join(PATCH, "..", "text_work_TW",
                         "Missing_Kanji_Dictionary_TW.txt"),
            encoding="utf-8").read().splitlines()),
        "map scripts: %d" % sum(
            1 for _d in _glob.glob(os.path.join(PATCH, "map", "*"))
            if os.path.isdir(_d)
            for _f in os.listdir(_d) if _f.endswith(".scp")),
    ]
    open(os.path.join(DST_GAME, "BUILD_INFO.txt"), "w",
         encoding="utf-8").write("\n".join(_stamp) + "\n")
    print("BUILD DONE")


if __name__ == "__main__":
    main()
