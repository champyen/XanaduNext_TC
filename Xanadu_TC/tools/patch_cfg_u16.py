"""Phase 5e: xanadu_cfg.exe dialog strings -> Traditional.

The cfg tool is a Windows dialog app: UI text lives in dialog resources
(UTF-16LE runs AND GBK-encoded fixed control strings — the Simplified
author used GBK for button/combo labels), NOT the game bitmap font, so
pure Unicode conversion applies: no Shift-JIS remap, no missing-kanji
problem. For each CJK run: decode -> OpenCC s2twp (+ Taiwan term fixes)
-> re-encode in the ORIGINAL encoding, must fit the original span
(null-pad). Byte size never changes (VS_VERSIONINFO length fields stay
valid). Applied on top of patch/xanadu_cfg.exe (CN baseline + hunk
conversions). cp932 hunk conversions take priority: the GBK pass only
claims spans whose cp932 reading is not legit CJK text.
"""
import io
import os
import re
import sys

if (sys.stdout.encoding or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='backslashreplace')

PATCH = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\patch\xanadu_cfg.exe"

# UTF-16LE units: printable ASCII, CJK, kana, CJK punct, fullwidth forms
# (pattern built by build_pat() below to avoid escaping pain)


def build_pat():
    import re as _re
    ascii_u = b"[\\x20-\\x7e]\\x00"
    cjk = (b"(?:[\\x00-\\xff]\\x30"      # U+3000-30FF punct/kana
           b"|[\\x00-\\xff][\\x34-\\x4d]"  # U+3400-4DFF ext-A
           b"|[\\x00-\\xff][\\x4e-\\x9f]"  # U+4E00-9FFF main
           b"|[\\x00-\\xff][\\xf9-\\xfa]"  # compat
           b"|[\\x00-\\xff]\\xff)")       # fullwidth
    return _re.compile(b"((?:" + ascii_u + b"|" + cjk + b"){2,})\\x00\\x00")


def text_ok(text):
    """Real UI text only: common CJK + ASCII + CJK/fullwidth punct.
    Rejects binary lookalikes (PUA, CJK-A/B rare, controls)."""
    if len(text) < 2:
        return False
    for ch in text:
        o = ord(ch)
        ok = (0x20 <= o <= 0x7E or 0x3000 <= o <= 0x303F
              or 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF
              or 0xFF00 <= o <= 0xFFEF or ch in "—…·\t\r\n"
              or 0x2010 <= o <= 0x201F or ch in "×÷°±《》〈〉「」『』")
        if not ok:
            return False
    return True


def main():
    from opencc import OpenCC
    from jpnorm import normalize as _normalize
    cc = OpenCC("s2twp")
    blob = bytearray(open(PATCH, "rb").read())
    # NOTE (round 6): an earlier English-only policy for this file was
    # reversed — combo-BOX ITEMS go English (separate revert step), all
    # other dialog text stays Traditional. So this pass always runs.
    # diff-driven: only touch strings the Simplified author changed
    # (GOG-vs-CN byte diffs). Untouched regions stay byte-identical, so
    # binary lookalikes elsewhere can never be corrupted.
    gog = open(r"C:\Users\champ\workspace\XanaduNext_workspace\XanaduNext\xanadu_cfg.exe",
               "rb").read()
    cn0 = open(r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_Steam_CN\GOG\GOG_xanadu_cfg.exe",
               "rb").read()
    diff = set(i for i, (x, y) in enumerate(zip(gog, cn0)) if x != y)
    pat = build_pat()
    n_hit = n_fit = n_skip = 0
    out = []
    data = bytes(blob)
    pos = 0
    # NOTE: even alignment is enforced DURING matching, not after: an
    # odd-start match (later discarded) must not consume bytes belonging
    # to an even run (e.g. odd junk ending at 121097 orphaned the 开 at
    # 121096, leaving half-converted 开啟V-Sync). Re-scan from odd+1.
    while True:
        m = pat.search(data, pos)
        if m is None:
            break
        if m.start() % 2 == 1:
            pos = m.start() + 1
            continue
        if not any(i in diff for i in range(m.start(), m.end())):
            pos = m.end()
            continue
        raw = m.group(1)
        try:
            text = raw.decode("utf-16-le")
        except Exception:
            pos = m.end()
            continue
        if not any("\u4e00" <= ch <= "\u9fff" for ch in text):
            pos = m.end()
            continue
        if not text_ok(text):
            pos = m.end()
            continue
        n_hit += 1
        tw = cc.convert(text)
        tw = _normalize(tw)
        enc = tw.encode("utf-16-le")
        if len(enc) <= len(raw):
            blob[m.start():m.start() + len(enc)] = enc
            for i in range(m.start() + len(enc), m.start() + len(raw)):
                blob[i] = 0
            n_fit += 1
            out.append((text, tw))
        else:
            n_skip += 1
            print("TOO-LONG @%d: %s -> %s" % (m.start(), text, tw))
        pos = m.end()
    open(PATCH, "wb").write(bytes(blob))
    print("cjk-runs=%d converted=%d too-long-skipped=%d" % (n_hit, n_fit, n_skip))
    for a, b in out[:30]:
        if a != b:
            print("  %s -> %s" % (a, b))
    print("total changed:", sum(1 for _ in out if _[0] != _[1]))
    # GBK pass: the Simplified author's single-byte control strings are
    # GBK-encoded (button/combo labels like 窗口模式/默认/启动游戏). The
    # hunk engine reads them as cp932 mojibake, so handle them here from
    # the CN baseline. cp932 hunk conversions take priority (checked
    # first); u16-converted spans are never touched.
    u16_spans = []
    _pos = 0
    _data = bytes(cn0)
    while True:
        _m = pat.search(_data, _pos)
        if _m is None:
            break
        if _m.start() % 2 == 1:
            _pos = _m.start() + 1
            continue
        if any(i in diff for i in range(_m.start(), _m.end())):
            u16_spans.append((_m.start(), _m.end()))
        _pos = _m.end()
    n_gbk = n_gbk_skip = 0
    i, n = 0, len(cn0)
    while i < n:
        b = cn0[i]
        if 0x81 <= b <= 0xFE:
            j = i
            while j + 1 < n:
                lb, tb = cn0[j], cn0[j + 1]
                if not (0x81 <= lb <= 0xFE
                        and 0x40 <= tb <= 0xFE and tb != 0x7F):
                    break
                j += 2
            if j - i >= 4:
                raw = cn0[i:j]
                # real control strings live in NUL-padded fixed fields;
                # binary lookalikes sit inside non-zero bytes. Require
                # NUL (or ASCII edge) on both sides.
                if not ((i == 0 or cn0[i - 1] == 0) and cn0[j] == 0):
                    i = j
                    continue
                if any(k in diff for k in range(i, j)):
                    try:
                        gtext = raw.decode("gbk")
                    except Exception:
                        gtext = None
                    if (gtext is not None
                            and any("\u4e00" <= c <= "\u9fff"
                                    for c in gtext)
                            and text_ok(gtext)
                            and not any(s < j and i < e
                                        for s, e in u16_spans)):
                        # cp932 priority: legit cp932 CJK belongs to hunks
                        try:
                            ctext = raw.decode("cp932")
                            cp932_legit = (
                                any("\u4e00" <= c <= "\u9fff"
                                    for c in ctext)
                                and text_ok(ctext))
                        except Exception:
                            cp932_legit = False
                        if not cp932_legit:
                            gtw = _normalize(cc.convert(gtext))
                            if gtw != gtext:
                                try:
                                    genc = gtw.encode("gbk")
                                except Exception:
                                    genc = None
                                if genc is not None and len(genc) <= len(raw):
                                    blob[i:i + len(genc)] = genc
                                    for k in range(i + len(genc), j):
                                        blob[k] = 0
                                    n_gbk += 1
                                    print("  GBK %s -> %s" %
                                          (gtext, gtw))
                                else:
                                    n_gbk_skip += 1
                i = j
                continue
        i += 1
    open(PATCH, "wb").write(bytes(blob))
    print("gbk-runs converted=%d skipped=%d" % (n_gbk, n_gbk_skip))


if __name__ == "__main__":
    main()
