"""Verify Phase 1-5 artifacts. Prints PASS/FAIL per check; exit 0 iff all pass."""
import io
import os
import sys

if (sys.stdout.encoding or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='backslashreplace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontmap import idx_of_char  # noqa: E402
from chr_decompress import decompress  # noqa: E402
from g32 import decode_to_rgba as _g32dec  # noqa: E402
from render_tw_font import SLOT_SPECIAL as _SLOT_SPECIAL  # noqa: E402

WS = r"C:\Users\champ\workspace"
TC = os.path.join(WS, "Xanadu_TC")
TW = os.path.join(TC, "text_work_TW")
SRC = os.path.join(TC, "sources")
PATCH = os.path.join(TC, "patch")
CN_TEXT = os.path.join(WS, "Xanadu_Steam_CN", "Text")
NDICT = len(open(os.path.join(TW, "Missing_Kanji_Dictionary_TW.txt"), encoding="utf-8").read().splitlines())
NSLOTS = NDICT + len(_SLOT_SPECIAL)  # dict subs + native-slot art swaps

fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (" | " + detail if detail else ""))
    if not cond:
        fails.append(name)


def walk_utf8():
    for root, _, fs in os.walk(TW):
        for f in fs:
            if f.endswith(".utf8.txt"):
                yield os.path.join(root, f)


# ---------------- Phase 1 ----------------
files = list(walk_utf8())
check("P1 count working copies == 243", len(files) == 243, str(len(files)))
logp = os.path.join(TW, "_encodings.log")
log = open(logp, encoding="utf-8").read().splitlines() if os.path.exists(logp) else []
check("P1 encodings log 244 lines", len(log) == 244, str(len(log)))
check("P1 EQUIP.tbl logged binary-skip",
      any("EQUIP.tbl" in l and "BINARY" in l for l in log))
mp = os.path.join(TW, "map", "Final_Size_Control", "area00",
                  "MP_0040.scp.utf8.txt")
t = open(mp, encoding="utf-8").read() if os.path.exists(mp) else ""
check("P1 MP_0040 decodes cp932-correct (SET_NAME)",
      'SET_NAME("MAG","' in t and "浠" not in t)
check("P1 MP_0040 has Traditional dialogue", "你好" in t)
exe = [f for f in os.listdir(TW) if f in ("Object_TW.txt",)]
check("P1 Object_TW.txt reference present", len(exe) == 1, ",".join(exe))
inv = open(os.path.join(TW, "_tw_inventory.txt"), encoding="utf-8").read()
miss = open(os.path.join(TW, "_tw_miss.txt"), encoding="utf-8").read()
check("P1 inventory 2179 / miss 116", len(inv) == 2179 and len(miss) == 116,
      "%d/%d" % (len(inv), len(miss)))

# ---------------- Phase 2 ----------------
dp = os.path.join(TW, "Missing_Kanji_Dictionary_TW.txt")
dlines = open(dp, encoding="utf-8").read().splitlines() if os.path.exists(dp) else []
check("P2 dict entries", len(dlines) == NDICT, str(len(dlines)))
subs, tws, fmt_ok = [], [], True
for ln in dlines:
    p = ln.split()
    if len(p) != 3 or not p[0].startswith("{U+"):
        fmt_ok = False
    else:
        tws.append(p[1])
        subs.append(p[2])
check("P2 dict format {U+XXXX} TW sub", fmt_ok)
check("P2 substitutes unique", len(set(subs)) == len(subs), str(len(subs)))
check("P2 no substitute inside game text",
      not (set(subs) & set(inv)), str(len(set(subs) & set(inv))))
dmap = dict(zip(tws, subs))
allmapped = all(idx_of_char(s) is not None for s in subs)
check("P2 every substitute has verified font slot", allmapped)
bad = n = 0
for f in files:
    tt = open(f, encoding="utf-8").read()
    for k, v in dmap.items():
        tt = tt.replace(k, v)
    n += 1
    try:
        tt.encode("cp932")
    except Exception:
        bad += 1
check("P2 all files cp932-encodable after substitution", bad == 0,
      "%d files" % n)

# ---------------- Phase 3 ----------------
for f in ("font_scn.raw", "font_sys.raw"):
    p = os.path.join(SRC, f)
    check("P3 extracted " + f, os.path.exists(p) and os.path.getsize(p) == 1351680,
          str(os.path.getsize(p)) if os.path.exists(p) else "missing")
check("P3 fontmap A=33 / space=0 / disasm-model (祢=4441, 亜=1886)",
      idx_of_char("A") == 33 and idx_of_char(" ") == 0
      and idx_of_char("祢") == 4441 and idx_of_char("亜") == 1886)
for name, orig_size in (("scn", 560037), ("sys", 526381)):
    rawp = os.path.join(PATCH, "font_%s_TW.raw" % name)
    datp = os.path.join(PATCH, "font_%s_TW.dat" % name)
    ok_raw = os.path.exists(rawp) and os.path.getsize(rawp) == 1351680
    check("P3 patch font_%s_TW.raw 1351680B" % name, ok_raw)
    if not ok_raw:
        continue
    gogp = os.path.join(SRC, "font_%s.dat" % name)
    gog = decompress(open(gogp, "rb").read())
    twraw = open(rawp, "rb").read()
    ndiff = sum(1 for i in range(10560)
                if gog[i * 128:(i + 1) * 128] != twraw[i * 128:(i + 1) * 128])
    check("P3 %s glyphs redrawn (=dict)" % name, ndiff == NSLOTS, str(ndiff))
    if os.path.exists(datp):
        rt = decompress(open(datp, "rb").read())
        check("P3 %s .dat roundtrips to .raw" % name, rt == twraw,
              "%dB (orig %dB)" % (os.path.getsize(datp), orig_size))
        # changed slots must be non-empty
        empty = [s for s in subs
                 if twraw[idx_of_char(s) * 128:(idx_of_char(s) + 1) * 128] == bytes(128)]
        check("P3 %s no empty redrawn slots" % name, not empty, str(empty))
    else:
        check("P3 %s .dat exists" % name, False)

print("----")
print("RESULT: %s (%d failures)" % ("ALL PASS" if not fails else "FAILURES", len(fails)))

# ---------------- Phase 4 (map scripts; non-fatal extras below) ----------------
import re as _re
_KEY4 = _re.compile(r"sys|sel\(|set_name|msg", _re.I)
_PMAP = os.path.join(TC, "patch", "map")
_cnt = sum(1 for _, _, fs in os.walk(_PMAP) for _f in fs
           if _f.endswith(".scp")) if os.path.exists(_PMAP) else 0
check("P4 205 game-ready scp built", _cnt == 205, str(_cnt))
if os.path.exists(_PMAP):
    _bad_line = _bad_key = _bad_enc = _bad_end = 0
    _areas = sorted(d for d in os.listdir(_PMAP)
                    if os.path.isdir(os.path.join(_PMAP, d)))
    check("P4 7 areas (+0087 in area00, 0699 in area06)",
          len(_areas) == 7
          and os.path.exists(os.path.join(_PMAP, "area00", "MP_0087.scp"))
          and os.path.exists(os.path.join(_PMAP, "area06", "MP_0699.scp")),
          ",".join(_areas))
    for _area in _areas:
        for _fn in os.listdir(os.path.join(_PMAP, _area)):
            _p = os.path.join(_PMAP, _area, _fn)
            _b = open(_p, "rb").read()
            if b"\r\r\n" in _b:
                _bad_end += 1
            try:
                _t = _b.decode("cp932")
            except Exception:
                _bad_enc += 1
                continue
            _sp = os.path.join(CN_TEXT, "map", "Final_Size_Control", _area, _fn)
            if _fn == "MP_0087.scp" and _area == "area00":
                _sp = None
                for _r, _, _fs in os.walk(os.path.join(CN_TEXT, "map")):
                    if "Final_Size_Control" in _r:
                        continue
                    if _fn in _fs:
                        _sp = os.path.join(_r, _fn)
            if _fn == "MP_0699.scp":
                _sp = None  # draft source; line parity checked at build
            if _sp and os.path.exists(_sp):
                _st = open(_sp, "rb").read().decode("cp932", "replace")
                if len(_t.splitlines()) != len(_st.splitlines()):
                    _bad_line += 1
                _ks = len([_l for _l in _st.splitlines()
                           if "//" not in _l and _KEY4.search(_l)])
                _kt = len([_l for _l in _t.splitlines()
                           if "//" not in _l and _KEY4.search(_l)])
                if _ks != _kt:
                    _bad_key += 1
    check("P4 all outputs strict-cp932", _bad_enc == 0, str(_bad_enc))
    check("P4 no doubled line endings", _bad_end == 0, str(_bad_end))
    check("P4 line-count parity with sources", _bad_line == 0, str(_bad_line))
    check("P4 key-line parity with sources", _bad_key == 0, str(_bad_key))

print("----")
print("FINAL: %s (%d failures)" % ("ALL PASS" if not fails else "FAILURES", len(fails)))

# ---------------- Phase 5 (tbl/inf/exe) ----------------
import re as _re2
import struct as _struct


def _arc_get(_arc, _dirp, _want):
    _d = open(_dirp, "rb").read()
    _offs = 0
    for _i in range((len(_d) - 4) // 108):
        _e = _d[_i * 108:(_i + 1) * 108]
        _nm = _e[:100].split(b"\x00")[0]
        _sz = _struct.unpack("<I", _e[100:104])[0]
        if _nm == _want:
            return open(_arc, "rb").read()[_offs:_offs + _sz]
        _offs += _sz
    raise KeyError(_want)


_GCHR = os.path.join(WS, "XanaduNext", "DATA", "chr", "Object.tbl")
_POBJ = os.path.join(PATCH, "chr", "Object.tbl")
if os.path.exists(_POBJ):
    _go = open(_GCHR, "rb").read()
    _to = open(_POBJ, "rb").read()
    check("P5 Object.tbl same size", len(_go) == len(_to), str(len(_to)))
    _an = _re2.compile(rb"M_[0-9A-Za-z]{4}\x00")
    check("P5 Object.tbl 138 anchors", len(_an.findall(_to)) == 138)
    _m0 = _re2.search(rb"M_0000\x00", _to)
    _s0 = _m0.end()
    while _to[_s0] == 0:
        _s0 += 1
    _e0 = _s0
    while _to[_e0] != 0:
        _e0 += 1
    check("P5 Object.tbl M_0000=TW", _to[_s0:_e0].decode("cp932") != "",
          _to[_s0:_e0].decode("cp932", "replace"))
else:
    check("P5 Object.tbl exists", False)

_PEQ = os.path.join(PATCH, "equip", "EQUIP.tbl")
if os.path.exists(_PEQ):
    _ge = _arc_get(os.path.join(WS, "XanaduNext", "DATA", "equip", "equip.arc"),
                   os.path.join(WS, "XanaduNext", "DATA", "equip", "equip.dir"),
                   b"EQUIP.tbl")
    _te = open(_PEQ, "rb").read()
    check("P5 EQUIP.tbl same size", len(_ge) == len(_te) == 708608,
          str(len(_te)))
    _ae = _re2.compile(rb"SL\d_[0-9A-Fa-f]{4}")
    check("P5 EQUIP.tbl anchors", len(_ae.findall(_ge)) == len(_ae.findall(_te)),
          str(len(_ae.findall(_te))))
else:
    check("P5 EQUIP.tbl exists", False)

_PG = os.path.join(PATCH, "equip", "guardian.tbl")
try:
    open(_PG, encoding="cp932").read()
    check("P5 guardian.tbl cp932-ok", True, str(os.path.getsize(_PG)))
except Exception as ex:
    check("P5 guardian.tbl cp932-ok", False, str(ex))

_PMAP = os.path.join(PATCH, "Map")
_infs = sorted(f for f in os.listdir(_PMAP) if f.endswith(".inf")) \
    if os.path.exists(_PMAP) else []
check("P5 7 area inf built", len(_infs) == 7, ",".join(_infs))
_badinf = 0
for _f in _infs:
    try:
        open(os.path.join(_PMAP, _f), encoding="cp932").read()
    except Exception:
        _badinf += 1
check("P5 inf cp932-ok", _badinf == 0, str(_badinf))

for _exe, _size in (("XANADU.exe", 1259008), ("xanadu_cfg.exe", 129536)):
    _p = os.path.join(PATCH, _exe)
    check("P5 patch/%s size" % _exe,
          os.path.exists(_p) and os.path.getsize(_p) == _size,
          str(os.path.getsize(_p)) if os.path.exists(_p) else "missing")

# cfg containment: TW-vs-CN changes only inside GOG-vs-CN diff regions
_CG, _CC = (os.path.join(WS, "XanaduNext", "xanadu_cfg.exe"),
            os.path.join(WS, "Xanadu_Steam_CN", "GOG", "GOG_xanadu_cfg.exe"))
_PC = os.path.join(PATCH, "xanadu_cfg.exe")
if all(os.path.exists(p) for p in (_CG, _CC, _PC)):
    _g, _c, _t = (open(_CG, "rb").read(), open(_CC, "rb").read(),
                  open(_PC, "rb").read())
    _diff = set(i for i, (x, y) in enumerate(zip(_g, _c)) if x != y)
    _out = [i for i, (x, y) in enumerate(zip(_c, _t)) if x != y
            and not any(abs(i - d) <= 2 for d in _diff)]
    check("P5 cfg changes contained", not _out, str(len(_out)))
else:
    check("P5 cfg files present", False)

# ---------------- Phase 6 (picture cards) ----------------
_PP = os.path.join(PATCH, "picture")
_pic = sorted(f for f in os.listdir(_PP) if f.endswith(".G32")) \
    if os.path.exists(_PP) else []
check("P6 11 cards built (6 area + 5 boss)", len(_pic) == 11, str(len(_pic)))
_badpic = []
for _f in _pic:
    try:
        _w, _h, _px = _g32dec(open(os.path.join(_PP, _f), "rb").read())
        if (_w, _h) != (256, 256):
            _badpic.append(_f)
    except Exception:
        _badpic.append(_f)
check("P6 cards decode 256x256 G32", not _badpic, str(_badpic))

print("----")
print("FINAL2: %s (%d failures)" % ("ALL PASS" if not fails else "FAILURES", len(fails)))
sys.exit(1 if fails else 0)
