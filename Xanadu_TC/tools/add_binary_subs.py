"""Add SUB slots for JP-norm targets that occur ONLY in binary paths
(EQUIP.tbl etc.) so extend_dict_text's working-copy scan can't see them.
Same slot-pool rules as extend_dict_text (exclude used/simple-dict/game
chars, prefer 0xE0+ leads). Appends {U+XXXX} <char> <slot> lines.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontmap import idx_of_char  # noqa: E402

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="backslashreplace")

WORK = r"C:\Users\champ\workspace\Xanadu_TC\text_work_TW"
DICT = os.path.join(WORK, "Missing_Kanji_Dictionary_TW.txt")
SIMP_DICT = (r"C:\Users\champ\workspace\Xanadu_Steam_CN\Tool"
             r"\Missing_Kanji_Dictionary.txt")

TARGETS = ["雞", "醬"]


def main():
    used = set()
    have = set()
    for line in open(DICT, encoding="utf-8"):
        p = line.split()
        if len(p) >= 3:
            have.add(p[1])
            used.add(p[2])
    simp_sub = set()
    for line in open(SIMP_DICT, encoding="utf-8"):
        p = line.split()
        if len(p) >= 3:
            simp_sub.add(p[2])
    game = set()
    for root, _, fs in os.walk(WORK):
        for f in fs:
            if f.endswith(".utf8.txt"):
                game.update(open(os.path.join(root, f),
                                 encoding="utf-8").read())
    missing = [c for c in TARGETS if c not in have
               and idx_of_char(c) is None]
    if not missing:
        print("nothing to add")
        return
    pool = []
    for cp in list(range(0x4E00, 0xA000)) + list(range(0xF900, 0xFB00)):
        c = chr(cp)
        if idx_of_char(c) is None:
            continue
        if c in game or c in used or c in simp_sub or c in have:
            continue
        pool.append(c)
    pool.sort(key=lambda c: (0 if c.encode("cp932")[0] >= 0xE0 else 1,
                             ord(c)))
    with open(DICT, "a", encoding="utf-8") as f:
        for c in missing:
            while pool[0] in used:
                pool.pop(0)
            sub = pool.pop(0)
            assert idx_of_char(sub) is not None and sub not in game
            used.add(sub)
            f.write("{U+%04X} %s %s\n" % (ord(c), c, sub))
            print("added U+%04X -> U+%04X" % (ord(c), ord(sub)))
    print("dict entries now:",
          len(open(DICT, encoding="utf-8").read().splitlines()))


if __name__ == "__main__":
    main()
