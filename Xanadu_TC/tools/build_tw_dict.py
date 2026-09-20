"""Phase 2: build Missing_Kanji_Dictionary_TW.txt.

- TW miss chars identical to a Simplified intended char reuse the same
  substitute (keeps font slots compatible with the Simplified patch).
- New TW-only miss chars get fresh substitutes: cp932-encodable CJK that
  appear nowhere in the TW game text and were never used as substitutes
  in the Simplified dictionary.
- Output format matches the Simplified dict so Missing_Kanji_Instead.py
  works unchanged:  {U+XXXX} <TW char> <substitute>
  sorted by in-game frequency (most frequent first).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontmap import idx_of_char

SIMP_DICT = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_Steam_CN\Tool\Missing_Kanji_Dictionary.txt"
WORK = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\text_work_TW"
OUT = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\text_work_TW\Missing_Kanji_Dictionary_TW.txt"


def main():
    simp_sub = {}   # intended Simplified char -> substitute
    simp_sub_used = set()
    for line in open(SIMP_DICT, encoding="utf-8"):
        p = line.split()
        if len(p) >= 3:
            simp_sub[p[1]] = p[2]
            simp_sub_used.add(p[2])

    inventory = set(open(os.path.join(WORK, "_tw_inventory.txt"), encoding="utf-8").read())
    miss = open(os.path.join(WORK, "_tw_miss.txt"), encoding="utf-8").read()
    freq = json.load(open(os.path.join(WORK, "_tw_miss_freq.json"), encoding="utf-8"))

    # Candidate pool: ONLY slots verified to exist in the font (fontmap.py):
    # JIS kanji in leads 0x88-0x9F / 0xE0-0xE8, outside game text and outside
    # every Simplified substitute slot. (Leads like 0xED/0xEE decode in
    # Python's cp932 but have no verified font slots - must not be used.)
    # Reuse applies only when the Simplified slot is itself verified-mapped;
    # otherwise a fresh verified slot is assigned (self-consistent TW font).
    pool = []
    for cp in list(range(0x4E00, 0xA000)) + list(range(0xF900, 0xFB00)):
        c = chr(cp)
        if idx_of_char(c) is None:
            continue
        if c in inventory or c in simp_sub_used or c in simp_sub:
            continue
        pool.append(c)
    # Prefer JIS X 0208 Level 2 (rare) kanji as substitute slots: in cp932
    # these have lead byte >= 0xE0. Common (Level 1) kanji may still occur in
    # untranslated Japanese leftover lines, which would then misrender.
    # (Reused Simplified slots were already chosen obscure by its author.)
    def lead(b):
        return b[0]

    pool.sort(key=lambda c: (0 if lead(c.encode("cp932")) >= 0xE0 else 1, ord(c)))
    print("pool L2-first: %d" % sum(1 for c in pool if c.encode("cp932")[0] >= 0xE0))

    used = set()  # freshly assigned substitutes (reuse slots are pre-cleared below)
    lines = []
    n_reuse_mapped = 0
    for c in sorted(miss, key=lambda x: -freq.get(x, 0)):
        if (c in simp_sub and simp_sub[c] not in inventory
                and idx_of_char(simp_sub[c]) is not None):
            sub = simp_sub[c]
            n_reuse_mapped += 1
        else:
            # fresh slot: skip pool chars already taken or literally in game text
            while pool[0] in used or pool[0] in inventory:
                pool.pop(0)
            sub = pool.pop(0)
        assert sub not in used, "duplicate substitute " + sub
        assert sub not in inventory, "substitute in game text " + sub
        assert idx_of_char(sub) is not None, "unmapped slot " + sub
        used.add(sub)
        sub.encode("cp932")
        lines.append("{U+%04X} %s %s" % (ord(c), c, sub))

    assert len(lines) == len(miss) == 116, (len(lines), len(miss))
    open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("wrote %s entries=%d reuse_mapped=%d fresh=%d"
          % (OUT, len(lines), n_reuse_mapped, len(lines) - n_reuse_mapped))


if __name__ == "__main__":
    sys.exit(main())
