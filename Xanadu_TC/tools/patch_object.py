"""Phase 5a: patch Object.tbl monster names (Simplified -> Traditional).

Method: diff GOG vs Simplified-CN Object.tbl -> 147 hunk spans (all
name-length). Per hunk: take the CN bytes (= final Simplified string),
cp932-decode (extending 1-2 bytes into identical neighbours when a
multi-byte char straddles the hunk edge, e.g. M_0310 獄 = 92 6E where 6E
coincides with GOG 'n'), reverse-substitute, OpenCC s2twp, apply TW
remap dict, re-encode. Write back zero-padded; never exceed the hunk
span (+1-2 byte extension). Output: patch/chr/Object.tbl
"""
import io
import os
import re
import sys

if (sys.stdout.encoding or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='backslashreplace')

GOG = r"C:\Users\champ\workspace\XanaduNext_workspace\XanaduNext\DATA\chr\Object.tbl"
CN = (r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_Steam_CN\MainData\DATA\chr"
      r"\Object.tbl")
WORK = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\text_work_TW"
PATCH = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\patch\chr\Object.tbl"
DICT = os.path.join(WORK, "Missing_Kanji_Dictionary_TW.txt")
SIMP_DICT = (r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_Steam_CN\Tool"
             r"\Missing_Kanji_Dictionary.txt")


def load_sub(path, reverse):
    d = {}
    for line in open(path, encoding="utf-8"):
        p = line.split()
        if len(p) >= 3:
            if reverse:
                d[p[2]] = p[1]
            else:
                d[p[1]] = p[2]
    return d


def main():
    from opencc import OpenCC
    cc = OpenCC("s2twp")
    rev = load_sub(SIMP_DICT, True)
    twd = load_sub(DICT, False)

    a = open(GOG, "rb").read()
    cnb = open(CN, "rb").read()
    assert len(a) == len(cnb)
    out = bytearray(cnb)  # start from CN layout, swap text in place
    diffs = [i for i, (x, y) in enumerate(zip(a, cnb)) if x != y]
    hunks = []
    s = p = diffs[0]
    for i in diffs[1:]:
        if i == p + 1:
            p = i
        else:
            hunks.append((s, p))
            s = p = i
    hunks.append((s, p))

    # Merge hunks split by coincidental byte equality (NONZERO gaps <= 2,
    # e.g. M_0310 地獄 where CN trail 6E == GOG 'n'). Zero gaps are real
    # field boundaries and must NOT merge (they hold C-string terminators).
    groups = []
    gs, ge = hunks[0]
    for s, e in hunks[1:]:
        gap = cnb[ge + 1:s]
        if len(gap) <= 2 and all(b != 0 for b in gap):
            ge = e
        else:
            groups.append((gs, ge))
            gs, ge = s, e
    groups.append((gs, ge))
    print("hunks: %d groups: %d" % (len(hunks), len(groups)))
    hunks = groups

    written = bytearray(len(a))  # track touched spans
    n_ok = n_warn = n_skip = 0
    for s, e in hunks:
        if written[s]:
            continue  # covered by a neighbour's extension
        # extend span until CN bytes decode cleanly (split-char edges).
        # Try smallest extensions first, preferring right (a hunk ending on
        # a lead byte is the common case, e.g. M_0310 獄 = 92 6E).
        es, ee, ok_dec = s, e, False
        for dl, dr in ((0, 0), (0, 1), (0, 2), (-1, 1), (-1, 2), (-2, 2),
                       (0, 3), (-2, 3)):
            try:
                if s + dl < 0:
                    continue
                cnb[s + dl:e + dr + 1].decode("cp932")
                es, ee, ok_dec = s + dl, e + dr, True
                break
            except Exception:
                pass
        if not ok_dec:
            print("DECODE-FAIL offs %d" % s)
            n_warn += 1
            continue
        text = cnb[es:ee + 1].decode("cp932")
        text = text.replace("\x00", "")
        if not text.strip():
            n_skip += 1
            continue
        for k, v in rev.items():
            if k in text:
                text = text.replace(k, v)
        text = cc.convert(text)
        # jpnorm (shinjitai -> TW) was MISSING here until round 11:
        # Object.tbl kept JP forms (図両亜絵転...) in every translated
        # name because this builder bypassed the shared normalizer.
        from jpnorm import normalize as _normalize
        text = _normalize(text)
        for k, v in twd.items():
            if k in text:
                text = text.replace(k, v)
        try:
            blob = text.encode("cp932")
        except Exception as ex:
            print("ENCODE-FAIL offs %d: %s" % (s, ex))
            n_warn += 1
            continue
        span = ee - es + 1
        cn_span = bytes(out[es:ee + 1])  # still pristine CN bytes here
        stripped = cn_span.rstrip(b"\x00")
        if len(stripped) < len(cn_span):
            # null-terminated style: CN text + null + zero padding.
            # TW needs text + null; may extend into zero padding (capped).
            if len(blob) + 1 > span:
                limit = ee + 1
                nxt = [g[0] for g in hunks if g[0] > ee]
                stop = min(nxt) if nxt else len(out)
                while (len(blob) + 1 > (limit - es) and limit < stop
                       and limit < ee + 9 and out[limit] == 0):
                    limit += 1
                if len(blob) + 1 > (limit - es):
                    print("OVERFLOW offs %d: need %d have %d text=%s" %
                          (s, len(blob) + 1, limit - es, text))
                    n_warn += 1
                    continue
                ee = limit - 1
                span = ee - es + 1
        else:
            # fixed-width style (no null in CN span: tail bytes shared with
            # GOG, e.g. subtitle suffix). TW must fit exactly, no null added.
            if len(blob) > span:
                print("OVERFLOW-FIXED offs %d: need %d have %d text=%s" %
                      (s, len(blob), span, text))
                n_warn += 1
                continue
            if len(blob) < span:
                print("SHORT-FIXED offs %d: %d < %d text=%s (zero-padded)" %
                      (s, len(blob), span, text))
        out[es:es + len(blob)] = blob
        out[es + len(blob):ee + 1] = b"\x00" * (ee + 1 - es - len(blob))
        for i in range(es, ee + 1):
            written[i] = 1
        n_ok += 1
    os.makedirs(os.path.dirname(PATCH), exist_ok=True)
    # Whole-file JP normalization: the diff pass above only normalizes
    # hunks the CN author translated; untranslated regions keep JP
    # shinjitai (両乗亀体図...) which the player still sees in the
    # monster/item encyclopedia. jpscan is a length-preserving 1:1
    # char map over cp932 CJK runs (SUB slots for unencodable targets).
    from jpscan import build_map as _js_map
    from jpscan import load_sub as _js_sub
    from jpscan import normalize_blob as _js_norm
    out2, st = _js_norm(bytes(out), _js_map(), _js_sub(), "Object.tbl")
    print("jp-scan runs=%d converted=%d skipped=%d" % st)
    open(PATCH, "wb").write(out2)
    print("patched=%d skipped-empty=%d warnings=%d" % (n_ok, n_skip, n_warn))


if __name__ == "__main__":
    main()
