"""Whole-file JP normalization for cp932 binary tables (Object.tbl,
EQUIP.tbl, guardian.tbl, *.inf).

Those files are patched from GOG/CN binaries, so their text is NOT in
the working-copy tree and extend_dict_text/s2tw_convert never see it.
Untranslated CN regions therefore keep JP shinjitai (両乗亀体図...) even
though the named builders normalized only diff hunks.

normalize_blob() rewrites every cp932 CJK run that survives a strict
gate, applying the 1:1 JPNORM char map. All mapped targets are 2-byte
cp932 OR have a SUB slot, so every run keeps its exact byte length
(fixed-field safety); runs that would change length are refused and
reported. Binary noise is excluded by requiring >=2 CJK chars and no
control bytes in the run.

Used by patch_object.py and patch_equip.py after their diff pass.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="backslashreplace")


def build_map():
    from jpnorm import JPNORM
    chmap = {a: b for a, b in JPNORM if len(a) == 1 and len(b) == 1}
    return chmap


def load_sub():
    """UNENCODABLE TW char -> SUB slot char (TW dict, col3)."""
    work = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\text_work_TW"
    sub = {}
    for line in open(os.path.join(work, "Missing_Kanji_Dictionary_TW.txt"),
                     encoding="utf-8"):
        p = line.split()
        if len(p) >= 3:
            sub[p[1]] = p[2]
    return sub


def _is_cjk(ch):
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF
            or 0xF900 <= o <= 0xFAFF)


def normalize_blob(blob, chmap, sub, tag=""):
    """Return (new_bytes, stats). Only CJK runs are touched."""
    b = bytearray(blob)
    n = len(b)
    n_runs = n_conv = n_skip = 0
    i = 0
    while i < n - 1:
        lb = b[i]
        if not (0x81 <= lb <= 0x9F or 0xE0 <= lb <= 0xFC):
            i += 1
            continue
        j = i
        while j + 1 < n:
            l2, t2 = b[j], b[j + 1]
            if not ((0x81 <= l2 <= 0x9F or 0xE0 <= l2 <= 0xFC)
                    and 0x40 <= t2 <= 0xFC and t2 != 0x7F):
                break
            j += 2
        if j - i < 4:  # need >=2 chars
            # advance ONE byte, not past the run: a stray binary lead
            # byte (0xED before a real 0x93 0xAC) otherwise swallows the
            # true run start (round 11: missed '闘用' in Object.tbl).
            i += 1
            continue
        try:
            text = bytes(b[i:j]).decode("cp932")
        except Exception:
            i = j
            continue
        cjk = sum(1 for c in text if _is_cjk(c))
        kana = any(0x3040 <= ord(c) <= 0x30FF for c in text)
        # text-like run: >=1 CJK/kana char, no control bytes. Was >=2 CJK,
        # which skipped kana-led labels like 'ガルマップ壊れ' (round 11).
        if (cjk + (1 if kana else 0)) < 1 or any(
                0x00 <= ord(c) < 0x20 and c not in "\t" for c in text):
            i = j
            continue
        n_runs += 1
        out = []
        changed = False
        for c in text:
            nc = chmap.get(c, c)
            out.append(nc)
            if nc != c:
                changed = True
        if not changed:
            i = j
            continue
        enc = []
        ok = True
        for c in out:
            try:
                enc.append(c.encode("cp932"))
            except Exception:
                s = sub.get(c)
                if s is None:
                    print("NO-SUB %s U+%04X in %r" % (tag, ord(c), text[:24]))
                    ok = False
                    break
                enc.append(s.encode("cp932"))
        blob2 = b"".join(enc)
        if not ok or len(blob2) != j - i:
            print("LEN-CHANGE %s run@%d %d->%d %r" %
                  (tag, i, j - i, len(blob2), text[:24]))
            n_skip += 1
            i = j
            continue
        b[i:j] = blob2
        n_conv += 1
        i = j
    return bytes(b), (n_runs, n_conv, n_skip)


def main():
    """CLI: normalize a file in place (debug/one-off)."""
    p = sys.argv[1]
    blob = open(p, "rb").read()
    out, st = normalize_blob(blob, build_map(), load_sub(), os.path.basename(p))
    open(p, "wb").write(out)
    print("runs=%d converted=%d skipped=%d" % st)


if __name__ == "__main__":
    main()
