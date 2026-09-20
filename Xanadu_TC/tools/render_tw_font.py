"""Phase 3: render Traditional glyphs into substitute font slots.

Recipe mirrors the Simplified author's (Source Han Sans for both after
the user-approved Round-9 switch; the original game font is gothic and
Noto Sans matches it better than Serif at 32px):
- scn (dialogue, Gothic style): NotoSansTC Regular, size 44, thresh 96
  (calibrated: meanabs 36.8 vs original, closest static setting)
- sys (UI, Gothic style):       NotoSansTC Regular, size 30, thresh 32
- Per-char fallback to SC fonts (NotoSansSC) when the TC font
  lacks the glyph (else Pillow draws .notdef tofu into the game font!
  e.g. 戱 U+6231, 嘇 U+5607). Coverage checked via fontTools cmap.
- SLOT_SPECIAL: native slots redrawn with different art (説-slot gets 說,
  since 説/說 share cp932 bytes and the game can only show slot art).
- Only dict substitute slots (+ specials) are redrawn; everything else
  stays byte-identical to GOG (minimal diff).
- 1bpp packing: each row is a u32, bit31 = leftmost pixel (verified: the
  earlier LSB packing mirrored glyphs; caught on CJK, proven with 'B').
- Output: Xanadu_TC/patch/font_scn_TW.raw / font_sys_TW.raw
"""
import os
import sys

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="backslashreplace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontmap import idx_of_char  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402

WORK = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC"
SRC = os.path.join(WORK, "sources")
PATCH = os.path.join(WORK, "patch")
DICT = os.path.join(WORK, "text_work_TW", "Missing_Kanji_Dictionary_TW.txt")
FONTDIR = os.path.join(SRC, "fonts")

FONTS = {
    # name: (ttf, fallback_ttf, variation, size, thresh, src_raw, dst_raw)
    "scn": (os.path.join(FONTDIR, "NotoSansTC.ttf"),
            os.path.join(FONTDIR, "NotoSansSC.ttf"),
            "Regular", 44, 96,
            os.path.join(SRC, "font_scn.raw"),
            os.path.join(PATCH, "font_scn_TW.raw")),
    "sys": (os.path.join(FONTDIR, "NotoSansTC.ttf"),
            os.path.join(FONTDIR, "NotoSansSC.ttf"),
            "Regular", 30, 32,
            os.path.join(SRC, "font_sys.raw"),
            os.path.join(PATCH, "font_sys_TW.raw")),
}

# native slot char -> art to draw there (codec collisions: game can only
# show whatever art sits in the shared slot)
SLOT_SPECIAL = {"説": "說"}


def draw_bar_cell():
    """Em dash: full-width 2px bar (JIS ─ metrics), programmatic."""
    out = bytearray(128)
    for r in (15, 16):
        for c in range(2, 30):
            out[r * 4 + (3 - c // 8)] |= 1 << (7 - c % 8)
    return bytes(out)


def draw_dot_cell():
    """Middle dot: centered 4x4 block, programmatic."""
    out = bytearray(128)
    for r in range(14, 18):
        for c in range(14, 18):
            out[r * 4 + (3 - c // 8)] |= 1 << (7 - c % 8)
    return bytes(out)


SPECIAL = {"—": draw_bar_cell, "·": draw_dot_cell}


_cmaps = {}


def pick_font(ttf, fallback, ch):
    """(ttf, used_fallback_bool): TC-first, SC fallback when the glyph is
    absent (prevents .notdef tofu baked into the game font)."""
    global _cmaps
    for key, path in (("main", ttf), ("fb", fallback)):
        if path not in _cmaps:
            _cmaps[path] = TTFont(path).getBestCmap()
        if ord(ch) in _cmaps[path]:
            return path, key == "fb"
    return ttf, False


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
        scale = min(32.0 / w, 32.0 / h)
        ink = ink.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                         Image.LANCZOS)
        w, h = ink.size
    cell = Image.new("L", (32, 32), 0)
    cell.paste(ink, ((32 - w) // 2, (32 - h) // 2), ink)
    px = cell.load()
    out = bytearray(128)
    for r in range(32):
        for c in range(32):
            if px[c, r] >= thresh:
                # row = u32, bit31 = leftmost: byte order reversed, MSB-left
                out[r * 4 + (3 - c // 8)] |= 1 << (7 - c % 8)
    return bytes(out)


def main():
    pairs = []
    for line in open(DICT, encoding="utf-8"):
        p = line.split()
        tw, sub = p[1], p[2]
        idx = idx_of_char(sub)
        assert idx is not None, "unmapped slot for " + sub
        pairs.append((tw, sub, idx))
    print("slots: %d" % len(pairs))
    assert len({i for _, _, i in pairs}) == len(pairs), "duplicate slots"

    for name, (ttf, fallback, variation, size, thresh, src_raw,
               dst_raw) in FONTS.items():
        raw = bytearray(open(src_raw, "rb").read())
        assert len(raw) == 1351680
        missing = []
        nfb = 0
        for tw, sub, idx in pairs:
            if tw in SPECIAL:
                cell = SPECIAL[tw]()
            else:
                use, fb = pick_font(ttf, fallback, tw)
                nfb += fb
                cell = draw_cell(use, variation, size, thresh, tw)
            if cell is None:
                missing.append(tw)
                continue
            raw[idx * 128:(idx + 1) * 128] = cell
        for slot_ch, art_ch in SLOT_SPECIAL.items():
            idx = idx_of_char(slot_ch)
            use, fb = pick_font(ttf, fallback, art_ch)
            nfb += fb
            cell = draw_cell(use, variation, size, thresh, art_ch)
            raw[idx * 128:(idx + 1) * 128] = cell
            print("%s special: slot(%s)=%s art" % (name, slot_ch, art_ch))
        open(dst_raw, "wb").write(bytes(raw))
        print("%s -> %s missing=%d %s fallback=%d" %
              (name, dst_raw, len(missing), missing, nfb))


if __name__ == "__main__":
    main()
