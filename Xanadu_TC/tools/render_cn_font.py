"""Debug: rebuild SIMPLIFIED fonts from scratch with our pipeline.

Same recipe as TW fonts (Serif SemiBold 40 th96 / Sans Regular 30 th32)
but Simplified source: for each Missing_Kanji_Dictionary entry draw col2
(intended Simplified char) at idx(col3) (substitute slot). Multi-chunk
compress + strict-validate. Output: patch/cn_test/font_scn_CN.* etc.
Proves/isolates the font pipeline independent of prebuilt Font/*.dat.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontmap import idx_of_char  # noqa: E402
from chr_compress import compress_container_multi, validate_container  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

WORK = r"C:\Users\champ\workspace\Xanadu_TC"
SRC = os.path.join(WORK, "sources")
OUT = os.path.join(WORK, "patch", "cn_test")
SIMP_DICT = (r"C:\Users\champ\workspace\Xanadu_Steam_CN\Tool"
             r"\Missing_Kanji_Dictionary.txt")
FONTDIR = os.path.join(SRC, "fonts")

FONTS = {
    "scn": (os.path.join(FONTDIR, "NotoSerifSC.ttf"), "SemiBold", 40, 96,
            os.path.join(SRC, "font_scn.raw")),
    "sys": (os.path.join(FONTDIR, "NotoSansSC.ttf"), "Regular", 30, 32,
            os.path.join(SRC, "font_sys.raw")),
}

SPECIAL_CN = {
    "—": (15, 16, 2, 29),  # bar rows + cols (inclusive, matches TW)
    "·": (14, 17, 14, 17),  # dot rows + cols
}


def draw_special(r0, r1, c0, c1):
    out = bytearray(128)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            out[r * 4 + (3 - c // 8)] |= 1 << (7 - c % 8)
    return bytes(out)


def draw_cell(ttf, variation, size, thresh, ch):
    f = ImageFont.truetype(ttf, size)
    try:
        f.set_variation_by_name(variation)
    except Exception:
        pass
    img = Image.new("L", (96, 96), 0)
    d = ImageDraw.Draw(img)
    d.text((16, 16), ch, font=f, fill=255)
    bb = img.getbbox()
    if not bb:
        return None
    ink = img.crop(bb)
    w, h = ink.size
    if w > 32 or h > 32:
        sc = min(32.0 / w, 32.0 / h)
        ink = ink.resize((max(1, int(w * sc)), max(1, int(h * sc))),
                         Image.LANCZOS)
        w, h = ink.size
    cell = Image.new("L", (32, 32), 0)
    cell.paste(ink, ((32 - w) // 2, (32 - h) // 2), ink)
    px = cell.load()
    out = bytearray(128)
    for r in range(32):
        for c in range(32):
            if px[c, r] >= thresh:
                out[r * 4 + (3 - c // 8)] |= 1 << (7 - c % 8)
    return bytes(out)


def main():
    pairs = []
    for line in open(SIMP_DICT, encoding="utf-8"):
        p = line.split()
        if len(p) < 3:
            continue
        cn_char, sub = p[1], p[2]
        idx = idx_of_char(sub)
        if idx is None:
            print("SKIP unmapped sub for", p[0])
            continue
        pairs.append((cn_char, sub, idx))
    print("slots: %d" % len(pairs))
    os.makedirs(OUT, exist_ok=True)
    for name, (ttf, var, size, th, src_raw) in FONTS.items():
        raw = bytearray(open(src_raw, "rb").read())
        assert len(raw) == 1351680
        missing = []
        for ch, sub, idx in pairs:
            if ch in SPECIAL_CN:
                r0, r1, c0, c1 = SPECIAL_CN[ch]
                cell = draw_special(r0, r1, c0, c1)
            else:
                cell = draw_cell(ttf, var, size, th, ch)
            if cell is None:
                missing.append(ch)
                continue
            raw[idx * 128:(idx + 1) * 128] = cell
        rp = os.path.join(OUT, "font_%s_CN.raw" % name)
        open(rp, "wb").write(bytes(raw))
        comp = compress_container_multi(bytes(raw))
        n = validate_container(comp, bytes(raw))
        dp = os.path.join(OUT, "font_%s_CN.dat" % name)
        open(dp, "wb").write(comp)
        print("%s slots missing=%s dat=%dB chunks=%d" %
              (name, len(missing), len(comp), n))


if __name__ == "__main__":
    main()
