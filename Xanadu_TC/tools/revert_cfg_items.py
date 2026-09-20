"""Round 6b: revert GBK CJK control strings in xanadu_cfg.exe to GOG English.

GBK-encoded CJK renders as garbage unless the system codepage is GBK;
the user asked menu selections back to English (ASCII works everywhere).
UTF-16 dialog text stays Traditional (renders locale-independent).

For each GBK CJK run in the TW file whose GOG same-span bytes are
ASCII/NUL (i.e. our conversion or CN's text over an English slot):
restore the GOG field bytes (run + dual-zero padding). Spans where GOG
is not ASCII are left untouched. Logs every revert for review.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="backslashreplace")

GOGP = r"C:\Users\champ\workspace\XanaduNext_workspace\XanaduNext\xanadu_cfg.exe"
TWP = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\patch\xanadu_cfg.exe"

# Runs whose TW text is in this set are KEPT in Traditional — but encoded
# as BIG5, not GBK: GBK bytes decode as garbage on Traditional-codepage
# systems (proven: GBK(視窗模式) as-Big5 == user-reported ?敦耀宅), while
# Big5 renders correctly there. Same byte lengths as GBK, so all fit
# results carry over.
KEEP_TW = ["視窗模式", "無邊框視窗模式"]


def main():
    gog = open(GOGP, "rb").read()
    tw = bytearray(open(TWP, "rb").read())
    assert len(gog) == len(tw)
    # GOG ASCII runs (English slots)
    gruns = [(m.start(), m.end()) for m in
             re.finditer(b"[\x20-\x7e]{2,}", bytes(gog))]
    n = len(tw)
    i = 0
    n_rev = n_skip = 0
    import bisect as _bisect
    restored_starts = []  # sorted starts, parallel ends for O(log n) check
    restored_ends = []

    def _covered(x):
        k = _bisect.bisect_right(restored_starts, x) - 1
        return k >= 0 and restored_starts[k] <= x < restored_ends[k]

    while i < n:
        if _covered(i):
            i += 1
            continue
        b = tw[i]
        if 0x81 <= b <= 0xFE:
            j = i
            while j + 1 < n:
                lb, tb = tw[j], tw[j + 1]
                if not (0x81 <= lb <= 0xFE
                        and 0x40 <= tb <= 0xFE and tb != 0x7F):
                    break
                j += 2
            if j - i >= 2:
                raw = bytes(tw[i:j])
                try:
                    t = raw.decode("gbk")
                except Exception:
                    t = None
                if (t is not None
                        and any("\u4e00" <= c <= "\u9fff" for c in t)):
                    if t in KEEP_TW:
                        if _covered(i):
                            n_skip += 1
                            i = j if j > i else i + 1
                            continue
                        try:
                            b5 = t.encode("big5")
                        except Exception:
                            print("BIG5-FAIL @%d %r" % (i, t[:20]))
                            n_skip += 1
                            i = j if j > i else i + 1
                            continue
                        if len(b5) != j - i:
                            print("BIG5-SIZE @%d %r" % (i, t[:20]))
                            n_skip += 1
                            i = j if j > i else i + 1
                            continue
                        tw[i:j] = b5
                        _k = _bisect.bisect_left(restored_starts, i)
                        restored_starts.insert(_k, i)
                        restored_ends.insert(_k, j)
                        print("KEEP-BIG5 @%d %r" % (i, t[:20]))
                        n_rev += 1
                        i = j if j > i else i + 1
                        continue
                    # overlapping GOG English slot? restore it wholly
                    # (run + its NUL padding) — GOG's own bytes always fit
                    hit = None
                    for a, bb in gruns:
                        if min(j, bb) - max(i, a) > 0:
                            hit = (a, bb)
                            break
                    if hit is None:
                        n_skip += 1
                    else:
                        a, bb = hit
                        e = bb
                        while e < n and gog[e] == 0 and e - bb < 64:
                            e += 1
                        tw[a:e] = gog[a:e]
                        _k = _bisect.bisect_left(restored_starts, a)
                        restored_starts.insert(_k, a)
                        restored_ends.insert(_k, e)
                        print("REVERT @%d [%d,%d) %r" % (i, a, e, t[:20]))
                        n_rev += 1
            i = j if j > i else i + 1
            continue
        i += 1
    open(TWP, "wb").write(bytes(tw))
    print("reverted=%d skipped=%d" % (n_rev, n_skip))


if __name__ == "__main__":
    main()
