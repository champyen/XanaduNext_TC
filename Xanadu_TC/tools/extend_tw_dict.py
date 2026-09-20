"""Extend the TW remap dictionary with EQUIP.tbl-only miss chars (append-only).

EQUIP.tbl is binary (skipped in Phase 1), so its chars never entered the
TW inventory. Failing chars (U+9472 etc.) get fresh verified font slots;
the existing 116 entries are untouched (fonts already built on them).
"""
import io
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontmap import idx_of_char  # noqa: E402
from tblpatch import compute_groups  # noqa: E402

if (sys.stdout.encoding or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='backslashreplace')

WORK = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\text_work_TW"
DICT = os.path.join(WORK, "Missing_Kanji_Dictionary_TW.txt")
SIMP_DICT = (r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_Steam_CN\Tool"
             r"\Missing_Kanji_Dictionary.txt")
GOG_ARC = r"C:\Users\champ\workspace\XanaduNext_workspace\XanaduNext\DATA\equip\equip.arc"
GOG_DIR = r"C:\Users\champ\workspace\XanaduNext_workspace\XanaduNext\DATA\equip\equip.dir"
CN_ARC = (r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_Steam_CN\MainData\DATA\equip"
          r"\equip.arc")
CN_DIR = (r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_Steam_CN\MainData\DATA\equip"
          r"\equip.dir")


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


def main():
    from opencc import OpenCC
    cc = OpenCC("s2twp")
    rev = {}
    for line in open(SIMP_DICT, encoding="utf-8"):
        p = line.split()
        if len(p) >= 3:
            rev[p[2]] = p[1]

    gog = arc_get(GOG_ARC, GOG_DIR, b"EQUIP.tbl")
    cn = arc_get(CN_ARC, CN_DIR, b"EQUIP.tbl")
    groups = compute_groups(gog, cn)
    print("groups:", len(groups))

    # collect converted char inventory from CN hunk texts
    inv = set()
    for s, e in groups:
        # decode with edge extension like tblpatch
        text = None
        for dl, dr in ((0, 0), (0, 1), (0, 2), (-1, 1), (-1, 2), (-2, 2),
                       (0, 3), (-2, 3)):
            try:
                text = cn[s + dl:e + dr + 1].decode("cp932")
                break
            except Exception:
                pass
        if text is None:
            continue
        text = text.replace("\x00", "")
        for k, v in rev.items():
            if k in text:
                text = text.replace(k, v)
        inv.update(cc.convert(text))
    json.dump(sorted(inv),
              open(os.path.join(WORK, "_equip_inventory.json"), "w",
                   encoding="utf-8"),
              ensure_ascii=False)
    new_miss = sorted(c for c in inv
                      if (("\u4e00" <= c <= "\u9fff") or c in "·—")
                      and _fails_cp932(c))
    print("equip-only new misses:", len(new_miss),
          ["U+%04X" % ord(c) for c in new_miss])

    # existing dict entries (frozen) + exclusions
    have = {}
    used = set()
    for line in open(DICT, encoding="utf-8"):
        p = line.split()
        have[p[1]] = p[2]
        used.add(p[2])
    simp_sub = set()
    for line in open(SIMP_DICT, encoding="utf-8"):
        p = line.split()
        if len(p) >= 3:
            simp_sub.add(p[2])
    game_chars = set(open(os.path.join(WORK, "_tw_inventory.txt"),
                          encoding="utf-8").read()) | set(inv)

    fresh = [c for c in new_miss if c not in have]
    print("to add:", len(fresh))
    # verified-slot pool, L2-first, excluding everything used
    pool = []
    for cp in list(range(0x4E00, 0xA000)) + list(range(0xF900, 0xFB00)):
        c = chr(cp)
        if idx_of_char(c) is None:
            continue
        if c in game_chars or c in used or c in simp_sub or c in have:
            continue
        pool.append(c)
    pool.sort(key=lambda c: (0 if c.encode("cp932")[0] >= 0xE0 else 1,
                             ord(c)))
    added = []
    with open(DICT, "a", encoding="utf-8") as f:
        for c in fresh:
            while pool[0] in used:
                pool.pop(0)
            sub = pool.pop(0)
            assert idx_of_char(sub) is not None
            assert sub not in game_chars
            used.add(sub)
            f.write("{U+%04X} %s %s\n" % (ord(c), c, sub))
            added.append((c, sub))
    for c, sub in added:
        print("added U+%04X -> slot char U+%04X" % (ord(c), ord(sub)))
    print("dict now:", len(have) + len(added), "entries")


def _fails_cp932(c):
    try:
        c.encode("cp932")
        return False
    except Exception:
        return True


if __name__ == "__main__":
    main()
