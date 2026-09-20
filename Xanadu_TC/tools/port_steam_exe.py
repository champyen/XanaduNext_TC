"""Build Steam-version TW exes by porting GOG-flow conversions.

No pristine Steam English base exists (only CN-patched Steam exes), so
instead of diff-hunks we port byte spans: for every diff hunk between
the CN source and our TW output (GOG flow), find those CN bytes in the
Steam CN file and write the TW bytes with a fit gate (TW must fit the
matched span; zero-pad the rest). Same translation => same bytes, so
matches are exact; misses (different translation/layout) stay CN and
are logged for review. Sizes never change.
Output: MainData.TW/Steam.exe/{XANADU.exe,xanadu_cfg.exe}
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="backslashreplace")

WS = r"C:\Users\champ\workspace\XanaduNext_workspace"
GOGCN_EXE = os.path.join(WS, "Xanadu_Steam_CN", "GOG", "GOG_XANADU.exe")
GOGTW_EXE = os.path.join(WS, "Xanadu_TC", "patch", "XANADU.exe")
STCN_EXE = os.path.join(WS, "Xanadu_Steam_CN", "MainData", "XANADU.exe")
GOGCN_CFG = os.path.join(WS, "Xanadu_Steam_CN", "GOG", "GOG_xanadu_cfg.exe")
GOGTW_CFG = os.path.join(WS, "Xanadu_TC", "patch", "xanadu_cfg.exe")
STCN_CFG = os.path.join(WS, "Xanadu_Steam_CN", "MainData", "xanadu_cfg.exe")
OUTDIR = os.path.join(WS, "MainData.TW", "Steam.exe")


def hunks(a, b):
    assert len(a) == len(b)
    d = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    if not d:
        return []
    out = []
    s = p = d[0]
    for i in d[1:]:
        if i == p + 1:
            p = i
        else:
            out.append((s, p))
            s = p = i
    out.append((s, p))
    return out


def expand_port(cn, s, e, tspan, st, diff_note):
    """Port one missed hunk by expanding to a full string.

    Returns a list of (pos, new_bytes, field_end) writes (NOT applied).
    Expands the CN hunk bytes to the enclosing NUL-bounded run, decodes
    (cp932/gbk/utf-16-le, first clean CJK decode wins), converts
    (tblpatch.convert_text for single-byte, OpenCC+jpnorm for UTF-16),
    locates the CN bytes in Steam and proposes fit-gated writes.
    Binary regions fail the CJK decode and stay out.
    """
    import sys as _sys
    _sys.path.insert(0, r"C:\Users\champ\workspace\XanaduNext_workspace"
                        r"\Xanadu_TC\tools")
    lo, hi = s, e + 1
    while lo - 1 >= 0 and cn[lo - 1] != 0 and lo - s < 200:
        lo -= 1
    while hi < len(cn) and cn[hi] != 0 and hi - e < 200:
        hi += 1
    raw = bytes(cn[lo:hi]).rstrip(b"\x00")
    if len(raw) < 2:
        return []
    text, enc = None, None
    for cand in ("cp932", "gbk", "utf-16-le"):
        try:
            t = raw.decode(cand)
        except Exception:
            continue
        if any("\u4e00" <= c <= "\u9fff" for c in t) and all(
                c == "\x00" or 0x20 <= ord(c) <= 0x9FFF or
                0xFF00 <= ord(c) <= 0xFFEF or c in "—…·×÷°±《》〈〉「」『』"
                for c in t):
            text, enc = t, cand
            break
    if text is None:
        return []
    if enc == "utf-16-le":
        from opencc import OpenCC
        from jpnorm import normalize as _normalize
        tw = _normalize(OpenCC("s2twp").convert(text))
    else:
        from tblpatch import convert_text
        tw = convert_text(text)
        if tw is None:
            return []
    if tw == text:
        return []  # nothing to port (identity)
    try:
        tenc = tw.encode("utf-16-le" if enc == "utf-16-le" else
                         ("gbk" if enc == "gbk" else "cp932"))
    except Exception:
        return []
    try:
        cenc = text.encode("utf-16-le" if enc == "utf-16-le" else
                           ("gbk" if enc == "gbk" else "cp932"))
    except Exception:
        return []
    if cenc != raw[:len(cenc)]:
        return []
    writes = []
    i = st.find(cenc)
    while i >= 0 and len(writes) < 64:
        f = i + len(cenc)
        while f < len(st) and st[f] == 0 and f - i < 200:
            f += 1
        if len(tenc) + (2 if enc == "utf-16-le" else 1) <= f - i:
            writes.append((i, tenc, f, "expand@%d" % s))
        else:
            writes.append(None)
        i = st.find(cenc, i + 1)
    return writes


def protected_ranges(path):
    """File ranges that must never be written: PE headers (below first
    section), executable code, and import structures (descriptors,
    ILT/IAT, hint/name strings). Round-12 lesson: exact text spans can
    coincide with import names ('b' inside FreeLibrary), killing APIs.
    """
    import pefile as _pe
    ranges = []
    try:
        pe = _pe.PE(path)
    except Exception:
        return [(0, 4096)]
    data_start = min(s.PointerToRawData for s in pe.sections)
    ranges.append((0, data_start))
    for s in pe.sections:
        if s.Characteristics & 0x20:  # IMAGE_SCN_CNT_CODE
            ranges.append((s.PointerToRawData,
                           s.PointerToRawData + s.SizeOfRawData))
    try:
        dd = pe.OPTIONAL_HEADER.DATA_DIRECTORY[
            _pe.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
        if dd.Size:
            o = pe.get_offset_from_rva(dd.VirtualAddress)
            ranges.append((o, o + dd.Size))
    except Exception:
        pass
    try:
        blob = open(path, "rb").read()
        for e in pe.DIRECTORY_ENTRY_IMPORT:
            nim = len(e.imports)
            for rva in (e.OriginalFirstThunk, e.FirstThunk):
                if rva:
                    try:
                        o = pe.get_offset_from_rva(rva)
                        ranges.append((o, o + (nim + 1) * 4))
                    except Exception:
                        pass
            for imp in e.imports:
                try:
                    toff = pe.get_offset_from_rva(imp.address)
                    hn = int.from_bytes(blob[toff:toff + 4], "little")
                    if hn == 0:
                        continue
                    ho = pe.get_offset_from_rva(hn)
                    nm = imp.name or b""
                    ranges.append((ho, ho + 2 + len(nm) + 1))
                except Exception:
                    pass
    except Exception:
        pass
    return sorted(ranges)


def port(cn_src, tw_src, st_src, tag):
    cn = open(cn_src, "rb").read()
    tw = open(tw_src, "rb").read()
    st = bytearray(open(st_cn, "rb").read())
    assert len(cn) == len(tw)
    hs = hunks(cn, tw)
    n_ok = n_miss = n_fit = n_claim = n_gate = 0
    misses = []
    writes = []
    # NOTE: st is pristine during collection; nothing is written until
    # the claim phase, so short strings can never clobber longer ones
    # they sit inside (round-12 lesson: 窗口模式 inside 无边框窗口模式).
    for s, e in hs:
        cspan = bytes(cn[s:e + 1])
        tspan = bytes(tw[s:e + 1])
        # find all occurrences in Steam file
        offs = []
        i = st.find(cspan)
        while i >= 0:
            offs.append(i)
            i = st.find(cspan, i + 1)
            if len(offs) > 64:
                break
        if not offs:
            # leftover: expand the CN hunk to its full NUL-bounded string,
            # convert directly, locate in Steam, fit-gated write. This
            # handles any size (single chars, fragments, padding drift)
            # that exact matching cannot.
            got = expand_port(cn, s, e, tspan, st, (tag, s))
            if not got:
                n_miss += 1
                if len(misses) < 15:
                    misses.append((s, cspan[:24].hex(" ")))
            else:
                for w in got:
                    if w is None:
                        n_fit += 1
                    else:
                        writes.append(w)
            continue
        for o in offs:
            if len(tspan) <= len(cspan):
                # text-likeness gate: version-drift bytes (e.g. a lone
                # 0x62) match thousands of binary spots incl. import
                # names — round-12 lesson (killed 5 imports). Only port
                # spans that decode to CJK text; binary drift is skipped
                # (leaving Steam's own bytes, which are correct there).
                istext = False
                for enc in ("cp932", "gbk", "utf-16-le"):
                    try:
                        if any("\u4e00" <= c <= "\u9fff"
                               for c in cspan.decode(enc)):
                            istext = True
                            break
                    except Exception:
                        continue
                if not istext:
                    n_gate += 1
                    continue
                writes.append((o, tspan, o + len(cspan),
                               "exact@%d" % s))
            else:
                n_fit += 1
    # claim biggest-first so short strings never clobber longer ones
    # they sit inside (e.g. 窗口模式 inside 无边框窗口模式).
    writes.sort(key=lambda w: len(w[1]), reverse=True)
    claimed = []
    n_skip = 0
    # never touch PE headers: text lives in sections, never below the
    # first section's raw offset (round-12 lesson: a 2-byte cspan matched
    # inside e_lfanew and killed the binary).
    import pefile as _pe
    try:
        _pef = _pe.PE(st_src)
        data_start = min(s.PointerToRawData for s in _pef.sections)
    except Exception:
        data_start = 4096
    prot = protected_ranges(st_src)
    n_hdr = 0
    for pos, newb, fend, lab in writes:
        if pos < data_start:
            n_hdr += 1
            continue
        if any(pos < pe and ps < fend for ps, pe in prot):
            n_hdr += 1
            continue
        if any(pos < ce and cs < fend for cs, ce in claimed):
            n_skip += 1
            continue
        st[pos:pos + len(newb)] = newb
        for k in range(pos + len(newb), fend):
            st[k] = 0
        claimed.append((pos, fend))
        n_ok += 1
    print("%s hunks=%d applied=%d miss=%d fit-skip=%d overlap-skip=%d hdr-skip=%d" %
          (tag, len(hs), n_ok, n_miss, n_fit, n_skip, n_hdr))
    for s, h in misses:
        print("  MISS @%d %s" % (s, h))
    return bytes(st)


def main():
    global st_cn
    os.makedirs(OUTDIR, exist_ok=True)
    st_cn = STCN_EXE
    out = port(GOGCN_EXE, GOGTW_EXE, STCN_EXE, "XANADU.exe")
    open(os.path.join(OUTDIR, "XANADU.exe"), "wb").write(out)
    st_cn = STCN_CFG
    out = port(GOGCN_CFG, GOGTW_CFG, STCN_CFG, "xanadu_cfg.exe")
    open(os.path.join(OUTDIR, "xanadu_cfg.exe"), "wb").write(out)


if __name__ == "__main__":
    main()
