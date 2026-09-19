"""Clean side-by-side: GOG | TW-new | CN-ref, big cells, real gaps, labels below."""
import os
import sys

sys.path.insert(0, r"C:\Users\champ\workspace\Xanadu_TC\tools")
from fontmap import idx_of_char
from PIL import Image, ImageDraw

WORK = r"C:\Users\champ\workspace\Xanadu_TC"
CN = r"C:\Users\champ\workspace\Xanadu_Steam_CN"

tw_raw = open(os.path.join(WORK, "patch", "font_scn_TW.raw"), "rb").read()
gog = open(os.path.join(WORK, "sources", "font_scn.raw"), "rb").read()
cn = open(os.path.join(CN, "Font", "font_scn_hack_0628"), "rb").read()

pairs = []
for line in open(os.path.join(WORK, "text_work_TW",
                              "Missing_Kanji_Dictionary_TW.txt"), encoding="utf-8"):
    p = line.split()
    pairs.append((p[0], p[1], p[2], idx_of_char(p[2])))

pairs = pairs[:12]

S = 6
CELL = 32 * S
GAP = 12
LABEL = 30
# block: 3 cells wide (GOG/TW/CN) + labels under each
BW = 3 * CELL + 4 * GAP
BH = CELL + LABEL + GAP
cols = 4
rows = (len(pairs) + cols - 1) // cols
img = Image.new("L", (cols * BW + GAP, rows * (BH + GAP) + GAP), 0)
d = ImageDraw.Draw(img)


def cell(raw, idx):
    g = raw[idx * 128:(idx + 1) * 128]
    im = Image.new("L", (32, 32), 0)
    px = im.load()
    for r in range(32):
        row = g[r * 4:r * 4 + 4]
        bstr = "".join(format(b, "08b") for b in row)[::-1]
        for c in range(32):
            if bstr[c] == "1":
                px[c, r] = 255
    return im.resize((CELL, CELL), Image.NEAREST)


for k, (code, tw, sub, idx) in enumerate(pairs):
    ox = (k % cols) * BW + GAP
    oy = (k // cols) * (BH + GAP) + GAP
    for j, (raw, tag) in enumerate(((gog, "GOG"), (tw_raw, "TW"), (cn, "CNref"))):
        x = ox + GAP + j * (CELL + GAP)
        img.paste(cell(raw, idx), (x, oy))
        d.text((x, oy + CELL + 2), tag, fill=180)
    d.text((ox + GAP, oy + CELL + 16), code, fill=200)
img.save(r"C:\Users\champ\AppData\Local\Temp\opencode\qa_clean.png")
print("saved", img.size)
