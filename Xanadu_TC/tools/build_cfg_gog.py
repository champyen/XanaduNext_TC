"""Phase 5g: xanadu_cfg.exe rebuilt from the English GOG binary.

Instead of patching the CN binary (which inherits CN byte quirks), take
the GOG English file as baseline and translate each UI string in place,
using the CN file only as translation reference:
  GOG English slot --(same offset)--> CN Simplified --(convert)--> TW,
  written back into the GOG copy.
Encodings: GOG ASCII slots -> TW GBK (CN precedent, system fonts render
it); GOG UTF-16 slots -> TW UTF-16LE. Only strings inside GOG-vs-CN
diffs are touched; everything else stays byte-identical GOG English
(same coverage as the CN patch). Fit: TW bytes + NUL must fit the slot
field, else keep GOG English + warn. Overlapping candidate writes are
resolved biggest-first.
Output: patch/xanadu_cfg.exe (overwrites the CN-patched one).
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from patch_cfg_u16 import build_pat, text_ok  # noqa: E402
from opencc import OpenCC  # noqa: E402
from jpnorm import normalize as _normalize  # noqa: E402

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="backslashreplace")

GOGP = r"C:\Users\champ\workspace\XanaduNext_workspace\XanaduNext\xanadu_cfg.exe"
CNP = (r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_Steam_CN\GOG\GOG_xanadu_cfg.exe")
PATCH = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\patch\xanadu_cfg.exe"


def ascii_runs(blob):
    return [(m.start(), m.end(), m.group().decode("ascii"))
            for m in re.finditer(b"[\x20-\x7e]{2,}", bytes(blob))]


def u16_runs(blob):
    pat = build_pat()
    out = []
    for m in pat.finditer(bytes(blob)):
        if m.start() % 2 == 1:
            continue
        try:
            t = m.group(1).decode("utf-16-le")
        except Exception:
            continue
        out.append((m.start(), m.end(), t))
    return out


def gbk_runs(blob, diff):
    """GBK CJK runs in diff regions with spans (baseline CN only)."""
    out = []
    i, n = 0, len(blob)
    while i < n:
        b = blob[i]
        if 0x81 <= b <= 0xFE:
            j = i
            while j + 1 < n:
                lb, tb = blob[j], blob[j + 1]
                if not (0x81 <= lb <= 0xFE
                        and 0x40 <= tb <= 0xFE and tb != 0x7F):
                    break
                j += 2
            # NOTE: single-unit runs are collected too (combo-box items
            # like 中/高); the NUL-context + diff + GOG-slot pairing
            # gates below keep binary out.
            if j - i >= 2:
                if ((i == 0 or blob[i - 1] == 0) and blob[j] == 0
                        and any(k in diff for k in range(i, j))):
                    try:
                        t = blob[i:j].decode("gbk")
                    except Exception:
                        t = None
                    if (t is not None
                            and any("\u4e00" <= c <= "\u9fff" for c in t)
                            and (text_ok(t) or (
                                len(t) == 1
                                and "\u4e00" <= t <= "\u9fff"))):
                        out.append((i, j, t))
            i = j if j > i else i + 1
            continue
        i += 1
    return out


def convert(text):
    return _normalize(OpenCC("s2twp").convert(text))


def main():
    # RETIRED (English policy for xanadu_cfg.exe + GOG/CN layout mismatch
    # proven in xanadu_tc.md round 4). Refuse to run so it can never
    # overwrite patch/xanadu_cfg.exe again.
    print("build_cfg_gog retired: xanadu_cfg.exe stays GOG English")
    return
    cc_dummy = None
    gog = open(GOGP, "rb").read()
    cn = open(CNP, "rb").read()
    assert len(gog) == len(cn)
    diff = set(i for i, (x, y) in enumerate(zip(gog, cn)) if x != y)
    out = bytearray(gog)

    g_ascii = [(s, e, t) for s, e, t in ascii_runs(gog)
               if any(i in diff for i in range(s, e))]
    g_u16 = [(s, e, t) for s, e, t in u16_runs(gog)
             if any(i in diff for i in range(s, e))]
    c_ascii = ascii_runs(cn)
    c_gbk = gbk_runs(cn, diff)
    c_u16 = u16_runs(cn)

    # invert: one write per CN run (encoding follows the CN run, so
    # merged GOG fragments like System+Menu -> 系统菜单 convert once)
    by_cn = {}
    n_pair = n_skip = 0
    for s, e, gt, is_u16 in ([(s, e, t, False) for s, e, t in g_ascii] +
                             [(s, e, t, True) for s, e, t in g_u16]):
        picked = None
        best_ov = 0
        cands = ([(s, e, t, "a") for s, e, t in c_ascii] +
                 [(s, e, t, "g") for s, e, t in c_gbk] +
                 [(s, e, t, "u") for s, e, t in c_u16])
        for cs, ce, ct, ckind in cands:
            ov = min(e, ce) - max(s, cs)
            if ov <= best_ov:
                continue
            if ct == gt:
                continue
            picked = (cs, ce, ct, ckind)
            best_ov = ov
        if picked is None:
            n_skip += 1
            continue
        cs, ce, ct, ckind = picked
        key = (cs, ce)
        if key not in by_cn:
            by_cn[key] = [ct, ckind, []]
            n_pair += 1
        by_cn[key][2].append((s, e))

    writes = []  # (span_len, start, end, bytes, label, gog_spans)
    for (cs, ce), (ct, ckind, gspans) in by_cn.items():
        tw = convert(ct)
        try:
            enc = tw.encode("utf-16-le" if ckind == "u" else "gbk")
        except Exception:
            print("UNENCODABLE: %r -> %r" % (ct, tw))
            n_skip += 1
            continue
        writes.append((ce - cs, cs, ce, enc, "%r -> %r" % (ct, tw),
                       gspans, tw == ct,
                       any("\u4e00" <= c <= "\u9fff" for c in tw)))

    # claim non-overlapping, biggest first; fit against field
    writes.sort(reverse=True)
    claimed = []
    n_ok = n_over = n_fit = 0
    for _, s, e, enc, label, gspans, ident, has_cjk in writes:
        if any(s < ce and cs < e for cs, ce in claimed):
            continue
        if ident and not has_cjk:
            # bring-over of non-Chinese (class names, binary-paired
            # fragments like '!P', version bits): GOG bytes stay.
            # Writing them once zeroed whole fields and killed launch.
            continue
        # field = union of CN span + paired GOG spans, plus trailing
        # zeros (merged runs like System+Menu -> 系统菜单 share one
        # field; TW overwrites from the CN start)
        f0 = min([s] + [a for a, b in gspans])
        f = max([e] + [b for a, b in gspans])
        while f < len(out) and out[f] == 0 and f - f0 < 96:
            f += 1
        if any(f0 < ce and cs < f for cs, ce in claimed):
            continue
        if len(enc) + 1 > f - s:
            print("OVERFLOW [%d]: %s" % (s, label))
            n_fit += 1
            continue
        if bytes(out[s:s + len(enc)]) == bytes(enc) and all(
                b == 0 for b in out[s + len(enc):f]):
            # already correct (e.g. previous identical write) — no-op
            claimed.append((f0, f))
            continue
        if all(b == 0 for b in out[f0:s]):
            pass
        elif any(0x20 <= b <= 0x7E for b in out[f0:s]):
            print("HEAD-TEXT [%d,%d): leaving GOG head, check: %s" %
                  (f0, s, label))
            f0 = s
        else:
            print("HEAD-BINARY [%d,%d): refusing write: %s" % (f0, s, label))
            continue
        out[s:s + len(enc)] = enc
        # zero-fill ONLY proven padding (zero in the GOG baseline);
        # never erase baseline-nonzero bytes (dialog structs live next
        # to strings — zeroing them kills launch).
        for k in list(range(f0, s)) + list(range(s + len(enc), f)):
            if gog[k] == 0:
                out[k] = 0
            elif k >= s + len(enc):
                print("NOZERO [%d] in write: %s" % (k, label))
        claimed.append((f0, f))
        n_ok += 1
    open(PATCH, "wb").write(bytes(out))
    print("paired=%d unpaired=%d written=%d overlap-skip fit-skip=%d" %
          (n_pair, n_skip, n_ok, n_fit))


if __name__ == "__main__":
    main()
