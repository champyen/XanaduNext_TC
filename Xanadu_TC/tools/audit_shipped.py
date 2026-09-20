"""Round-11 audit v2: scan SHIPPED game text for JP shinjitai leftovers,
with SUB-slot translation and canonical-file filtering.

Key fixes over v1 (which produced 98 phantom hits):
1. Substitute slots: the game font renders our TW art in the SUB's
   cp932 slot, so the raw bytes contain the SUB char (e.g. 濛) not the
   TW char (e.g. 總). Translate SUB -> TW before scanning, else every
   mapped char looks like an unmapped JP char.
2. Canonical files only: patch/map dirs may hold editor backups with
   mojibake names (0093(OLD), <copy> 等). Scan the 205 scripts that
   build_scp actually shipped + the arc entries actually in the dir.

Output: temp/opencode/shipped3.txt (HIT lines + contexts).
"""
import io
import os
import re
import struct
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="backslashreplace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jpnorm import JPNORM  # noqa: E402
from tblpatch import compute_groups, _decode_span  # noqa: E402

TW = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TW"
TC = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC"
GOGP = r"C:\Users\champ\workspace\XanaduNext_workspace\XanaduNext\XANADU.exe"
CNP = (r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_Steam_CN\GOG\GOG_XANADU.exe")

# SUB slot char -> TW char (translate slot bytes to intended meaning)
SUB2TW = {}
for line in open(os.path.join(TC, "text_work_TW",
                              "Missing_Kanji_Dictionary_TW.txt"),
                 encoding="utf-8"):
    p = line.split()
    if len(p) >= 3:
        SUB2TW[p[2]] = p[1]

SUSPECT_EXTRA = (
    "体鶏殴画歯雑沢没択浄浅涙渇湾湿潜独盗着"
    "挿掲揺拠塁壌堕峡暁昼断斉担携釈穂税穏錬窃粛"
    "聴脱臓舎芦桟殻覇訳誉讃豊豫醸劔頚減遡閑汎渕"
    "嚢噂覗箇罠掴呑呉况厨厦徊遅"
)
# valid in Traditional Chinese / context-dependent: excluded from the
# suspect scan so they don't generate false positives.
VALID_TW = set("為涼余弁芸徊減豫着閑汎箇")
jp_srcs = set(a for a, b in JPNORM if len(a) == 1)
suspects = (jp_srcs | set(SUSPECT_EXTRA)) - VALID_TW

BODY = re.compile(r'(?:MSG|SEL)\("([^"\x00-\x1f\x7f]{1,400})"')


def xlate(t):
    return "".join(SUB2TW.get(c, c) for c in t)


def arc_entries(arc, dirp):
    d = open(dirp, "rb").read()
    a = open(arc, "rb").read()
    offs = 0
    out = []
    for i in range((len(d) - 4) // 108):
        e = d[i * 108:(i + 1) * 108]
        nm = e[:100].split(b"\x00")[0].decode("cp932", "replace")
        sz = struct.unpack("<I", e[100:104])[0]
        out.append((nm, a[offs:offs + sz]))
        offs += sz
    return out


def cjk_runs(blob):
    n = len(blob)
    i = 0
    while i < n - 1:
        b = blob[i]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            j = i
            units = 0
            while j + 1 < n:
                lb, tb = blob[j], blob[j + 1]
                if not ((0x81 <= lb <= 0x9F or 0xE0 <= lb <= 0xFC)
                        and (0x40 <= tb <= 0xFC and tb != 0x7F)):
                    break
                j += 2
                units += 1
            if units >= 2:
                try:
                    t = blob[i:j].decode("cp932")
                    if any("\u4e00" <= c <= "\u9fff" for c in t):
                        yield t
                except Exception:
                    pass
                i = j
                continue
        i += 1


# canonical script set: exactly what build_scp shipped
canon = set()
pdir = os.path.join(TC, "patch", "map")
for area in os.listdir(pdir):
    adir = os.path.join(pdir, area)
    if os.path.isdir(adir):
        for f in os.listdir(adir):
            if f.endswith(".scp"):
                canon.add(f)

corpus = []
for area in ("area00", "area05", "area06", "area07", "area08", "area09",
             "area10"):
    for nm, blob in arc_entries(
            os.path.join(TW, "DATA", "Map", "%s.arc" % area),
            os.path.join(TW, "DATA", "Map", "%s.dir" % area)):
        if not nm.endswith(".scp") or nm not in canon:
            continue
        try:
            t = xlate(blob.decode("cp932"))
        except Exception:
            continue
        for m in BODY.finditer(t):
            corpus.append(("%s/%s" % (area, nm), m.group(1)))

corpus.append(("Object.tbl", xlate("\n".join(cjk_runs(
    open(os.path.join(TW, "DATA", "chr", "Object.tbl"), "rb").read())))))
for nm, blob in arc_entries(os.path.join(TW, "DATA", "equip", "equip.arc"),
                            os.path.join(TW, "DATA", "equip", "equip.dir")):
    if nm.endswith(".tbl"):
        corpus.append(("equip/%s" % nm, xlate("\n".join(cjk_runs(blob)))))
for area in ("area00", "area05", "area06", "area07", "area08", "area09",
             "area10"):
    p = os.path.join(TW, "DATA", "Map", "%s.inf" % area)
    if os.path.exists(p):
        corpus.append(("%s.inf" % area, xlate("\n".join(cjk_runs(
            open(p, "rb").read())))))

gog = open(GOGP, "rb").read()
cn = open(CNP, "rb").read()
twex = open(os.path.join(TW, "XANADU.exe"), "rb").read()
exe_texts = []
for s, e in compute_groups(gog, cn):
    dec = _decode_span(twex, s, e)
    if dec is not None:
        exe_texts.append(xlate(dec[2]))
corpus.append(("XANADU.exe", "\n".join(exe_texts)))

alltext = "\n".join(t for _, t in corpus)
out = ["== JP suspects in shipped outputs (SUB-translated) =="]
for ch in sorted(suspects):
    n = alltext.count(ch)
    if n:
        ctxs = []
        for origin, t in corpus:
            i = t.find(ch)
            while i >= 0 and len(ctxs) < 3:
                seg = t[max(0, i - 14):i + 14].replace("\n", " ")
                ctxs.append("%s :: %r" % (origin[:26], seg))
                i = t.find(ch, i + 1)
            if len(ctxs) >= 3:
                break
        out.append("HIT %r x%d" % (ch, n))
        out.extend("    " + c for c in ctxs)
open(r"C:\Users\champ\AppData\Local\Temp\opencode\shipped3.txt", "w",
     encoding="utf-8").write("\n".join(out))
print("hits:", sum(1 for l in out if l.startswith("HIT")))
