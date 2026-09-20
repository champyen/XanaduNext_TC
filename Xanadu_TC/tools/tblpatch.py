"""Shared fixed-field tbl patch engine (Object.tbl, EQUIP.tbl).

Diff GOG vs Simplified-CN bytes -> hunk spans (changed regions only).
Merge hunks split by coincidental byte equality (NONZERO gaps <= 2).
Per group: decode CN bytes (the final Simplified string), reverse-substitute,
OpenCC s2twp, TW remap, re-encode; write back null-terminated (if CN had a
null there) or exact-fit fixed-width (shared-suffix case), zero-padded.
Never write outside group span (+capped zero extension for null-style).
"""
import io
import os
import sys

if (sys.stdout.encoding or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='backslashreplace')

SIMP_DICT = (r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_Steam_CN\Tool"
             r"\Missing_Kanji_Dictionary.txt")
TW_DICT = (r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\text_work_TW"
           r"\Missing_Kanji_Dictionary_TW.txt")

_rev = None
_twd = None
_cc = None


def _converters():
    global _rev, _twd, _cc
    if _rev is None:
        from opencc import OpenCC
        _cc = OpenCC("s2twp")

        def load(path, reverse):
            d = {}
            for line in open(path, encoding="utf-8"):
                p = line.split()
                if len(p) >= 3:
                    if reverse:
                        d[p[2]] = p[1]
                    else:
                        d[p[1]] = p[2]
            return d

        _rev = load(SIMP_DICT, True)
        _twd = load(TW_DICT, False)
    return _rev, _twd, _cc


def convert_text(cn_text):
    rev, twd, cc = _converters()
    from jpnorm import normalize as _normalize
    text = cn_text.replace("\x00", "")
    if not text.strip():
        return None  # intentionally wiped field
    for k, v in rev.items():
        if k in text:
            text = text.replace(k, v)
    text = cc.convert(text)
    text = _normalize(text)
    for k, v in twd.items():
        if k in text:
            text = text.replace(k, v)
    return text


def compute_groups(gog, cnb):
    assert len(gog) == len(cnb)
    diffs = [i for i, (x, y) in enumerate(zip(gog, cnb)) if x != y]
    hunks = []
    s = p = diffs[0]
    for i in diffs[1:]:
        if i == p + 1:
            p = i
        else:
            hunks.append((s, p))
            s = p = i
    hunks.append((s, p))
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
    return groups


def _decode_span(cnb, s, e):
    for dl, dr in ((0, 0), (0, 1), (0, 2), (-1, 1), (-1, 2), (-2, 2),
                   (0, 3), (-2, 3)):
        try:
            if s + dl < 0:
                continue
            t = cnb[s + dl:e + dr + 1].decode("cp932")
            return s + dl, e + dr, t
        except Exception:
            pass
    return None


def _printable_ok(text):
    """Strict gate for binary-adjacent files (e.g. dialog resources):
    converted text must be printable (C0 allowed only tab/CR/LF) and
    substantial: contain CJK, or be >= 8 printable chars. Anything else
    is left as the CN bytes (the shipped working baseline)."""
    t = text.strip()
    if len(t) < 2:
        return False
    for ch in t:
        o = ord(ch)
        if o < 0x20 and ch not in "\t\r\n":
            return False
    if any("\u4e00" <= ch <= "\u9fff" or ch in "·—" for ch in t):
        return True
    return len(t) >= 8 and all(0x20 <= ord(ch) < 0x7F or ch in "\t\r\n"
                               for ch in t)


def patch_buffer(gog, cnb, tag="", accept=None):
    """Return (patched_bytes, (n_ok, n_skip, n_warn))."""
    out = bytearray(cnb)
    groups = compute_groups(gog, cnb)
    print("%s groups: %d" % (tag, len(groups)))
    n_ok = n_warn = n_skip = 0
    for s, e in groups:
        dec = _decode_span(cnb, s, e)
        if dec is None:
            print("DECODE-FAIL offs %d" % s)
            n_warn += 1
            continue
        es, ee, text = dec
        src = text.replace("\x00", "")
        text = convert_text(text)
        if text is None:
            n_skip += 1
            continue
        if accept is not None and not accept(text):
            n_skip += 1
            continue
        if text == src:
            # Identity: converted text equals source text. Keep the
            # ORIGINAL bytes untouched — re-encoding may pick a different
            # but equivalent byte form (e.g. NEC duplicates FB51 vs EDF2
            # for 炅), pointlessly churning shipped bytes. (Found via
            # xanadu_cfg.exe 确定/攻击 corruption scare.)
            n_skip += 1
            continue
        try:
            blob = text.encode("cp932")
        except Exception as ex:
            print("ENCODE-FAIL offs %d: %s" % (s, ex))
            n_warn += 1
            continue
        span = ee - es + 1
        cn_span = bytes(out[es:ee + 1])
        if len(cn_span.rstrip(b"\x00")) < len(cn_span):
            if len(blob) + 1 > span:
                limit = ee + 1
                nxt = [g[0] for g in groups if g[0] > ee]
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
            if len(blob) > span:
                print("OVERFLOW-FIXED offs %d: need %d have %d text=%s" %
                      (s, len(blob), span, text))
                n_warn += 1
                continue
            if len(blob) < span:
                print("SHORT-FIXED offs %d: %d < %d text=%s" %
                      (s, len(blob), span, text))
        out[es:es + len(blob)] = blob
        out[es + len(blob):ee + 1] = b"\x00" * (ee + 1 - es - len(blob))
        n_ok += 1
    return bytes(out), (n_ok, n_skip, n_warn)
