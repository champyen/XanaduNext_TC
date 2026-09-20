"""Proof sheet for checking: smooth TTF reference next to actual game cells.

Per TW entry (sorted by frequency):
  [smooth 120px TTF render on white] [32px grayscale render] [game 1-bit cell 6x]
  label: U+XXXX  TW-char -> substitute  slot=idx
Pages of 29 rows x 2 cols.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontmap import idx_of_char  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

WORK = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC"
TW_RAW = os.path.join(WORK, "patch", "font_scn_TW.raw")
DICT = os.path.join(WORK, "text_work_TW", "Missing_Kanji_Dictionary_TW.txt")
OUT = r"C:\Users\champ\AppData\Local\Temp\opencode\proof_scn_p{}.png"

TTF = r"C:\Windows\Fonts\mingliu.ttc"
SIZE = 30
LABEL_FONT = ImageFont.truetype(r"C:\Windows\Fonts\msjh.ttc", 22)


def game_cell(raw, idx, scale):
    g = raw[idx * 128:(idx + 1) * 128]
    im = Image.new("L", (32, 32), 0)
    px = im.load()
    for r in range(32):
        for c in range(32):
            # row = u32, bit31 = leftmost
            if (g[r * 4 + (3 - c // 8)] >> (7 - c % 8)) & 1:
                px[c, r] = 255
    return im.resize((32 * scale, 32 * scale), Image.NEAREST)


def smooth_ref(ch, px_h):
    f = ImageFont.truetype(TTF, 120)
    img = Image.new("L", (160, 160), 255)
    d = ImageDraw.Draw(img)
    d.text((20, 10), ch, font=f, fill=0)
    bb = img.getbbox()
    crop = img.crop(bb)
    w, h = crop.size
    s = min((px_h) / h, (px_h) / w, 4.0)
    return crop.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)


def smooth_32(ch):
    f = ImageFont.truetype(TTF, SIZE)
    img = Image.new("L", (64, 64), 0)
    d = ImageDraw.Draw(img)
    d.text((16, 16), ch, font=f, fill=255)
    bb = img.getbbox()
    ink = img.crop(bb)
    w, h = ink.size
    if w > 32 or h > 32:
        sc = min(32.0 / w, 32.0 / h)
        ink = ink.resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.LANCZOS)
        w, h = ink.size
    cell = Image.new("L", (32, 32), 0)
    cell.paste(ink, ((32 - w) // 2, (32 - h) // 2), ink)
    return cell.resize((192, 192), Image.LANCZOS)


pairs = []
for line in open(DICT, encoding="utf-8"):
    p = line.split()
    pairs.append((p[0], p[1], p[2], idx_of_char(p[2])))
raw = open(TW_RAW, "rb").read()

PER_PAGE = 58
COL_W = 640
IMG_H = 200
LABEL_H = 30
ROW_H = IMG_H + LABEL_H
for page in range((len(pairs) + PER_PAGE - 1) // PER_PAGE):
    chunk = pairs[page * PER_PAGE:(page + 1) * PER_PAGE]
    ncols = 2
    nrows = (len(chunk) + ncols - 1) // ncols
    img = Image.new("L", (ncols * COL_W + 20, nrows * ROW_H + 20), 255)
    d = ImageDraw.Draw(img)
    for k, (code, tw, sub, idx) in enumerate(chunk):
        ox = (k % ncols) * COL_W + 10
        oy = (k // ncols) * ROW_H + 10
        ref = smooth_ref(tw, 150)
        img.paste(ref, (ox, oy + (IMG_H - ref.size[1]) // 2))
        g32 = smooth_32(tw)
        img.paste(g32, (ox + 170, oy + (IMG_H - 192) // 2))
        gc = game_cell(raw, idx, 6)
        bg = Image.new("L", (192 + 8, 192 + 8), 0)
        bg.paste(gc, (4, 4))
        img.paste(bg, (ox + 370, oy + (IMG_H - 200) // 2))
        d.text((ox + 8, oy + IMG_H + 4), "%s %s->%s slot=%d" % (code, tw, sub, idx),
               font=LABEL_FONT, fill=0)
    img.save(OUT.format(page + 1))
    print("saved page", page + 1, img.size)
