"""Phase 6: rebuild 11 picture cards in Traditional Chinese.

Title cards (AREANAME01-06, BOSS01-03): CN image kept as base (black bg +
gold bar identical across cards), title + reflection bands erased, TW titles
redrawn in 標楷體 (matches CN calligraphy style), synthetic reflections
(flipped + faded + blurred). Glossary (BOSS04-05): EN + dividers kept, only
sub-text bands erased and redrawn (Noto Serif SemiBold, matches CN subs).
G32 re-encode via g32enc (sizes change -> .dir update in Phase 7).
Output: patch/picture/*.G32 + QA sheet in temp.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g32 import decode_to_rgba  # noqa: E402
from g32enc import encode_rgba  # noqa: E402
from PIL import Image, ImageDraw, ImageFont, ImageFilter  # noqa: E402

CN_ARC = r"C:\Users\champ\workspace\Xanadu_Steam_CN\MainData\DATA\picture\picture.arc"
CN_DIR = r"C:\Users\champ\workspace\Xanadu_Steam_CN\MainData\DATA\picture\picture.dir"
PATCH = r"C:\Users\champ\workspace\Xanadu_TC\patch\picture"
QADIR = r"C:\Users\champ\AppData\Local\Temp\opencode\pic6q"
KAI = r"C:\Windows\Fonts\kaiu.ttf"
SERIF = r"C:\Users\champ\workspace\Xanadu_TC\sources\fonts\NotoSerifTC.ttf"

# name: (kind, lines|subs, bands)
# title bands: [(title_rows, refl_rows)], glossary: [sub_row_centers]
CARDS = {
    "AREANAME01.G32": ("title", ["哈萊克鎮", "千古迷道"],
                       [((10, 38), (57, 83)), ((106, 133), (157, 182))]),
    "AREANAME02.G32": ("title", ["三葉草遺跡", "伊格利特山"],
                       [((9, 36), (58, 83)), ((108, 136), (159, 183))]),
    "AREANAME03.G32": ("title", ["奇岩城", "仙那度·魔幻迷宮"],
                       [((13, 40), (61, 87)), ((110, 128), (157, 174))]),
    "AREANAME04.G32": ("title", ["魔牧森林", "湖底的遺跡"],
                       [((10, 37), (61, 86)), ((106, 134), (151, 176))]),
    "AREANAME05.G32": ("title", ["時之狹間", "鎮外的遺跡"],
                       [((10, 37), (59, 84)), ((107, 134), (158, 183))]),
    "AREANAME06.G32": ("title", ["奇岩城·城內", "死者的異界"],
                       [((14, 36), (57, 75)), ((98, 119), (137, 157))]),
    "BOSS01.G32": ("title", ["樹妖貝里拉德", "斯寇圖拉"],
                   [((10, 31), (59, 78)), ((112, 134), (157, 176))]),
    "BOSS02.G32": ("title", ["邪惡亞龍", "洛蕾萊"],
                   [((16, 37), (66, 87)), ((109, 131), (156, 177))]),
    "BOSS03.G32": ("title", ["加爾西斯"], [((15, 36), (60, 80))]),
    "BOSS04.G32": ("gloss",
                   ["樹妖貝里拉德", "斯寇圖拉", "邪惡亞龍", "阿斯科莫伊德"],
                   [56.5, 121.5, 185.5, 234]),
    "BOSS05.G32": ("gloss", ["洛蕾親", "魔王加爾西斯"], [56, 115.5]),
}


def load_cn():
    d = open(CN_DIR, "rb").read()
    arc = open(CN_ARC, "rb").read()
    out = {}
    offs = 0
    for i in range((len(d) - 4) // 108):
        e = d[i * 108:(i + 1) * 108]
        nm = e[:100].split(b"\x00")[0].decode("cp932")
        sz = struct.unpack("<I", e[100:104])[0]
        if nm in CARDS:
            w, h, px = decode_to_rgba(arc[offs:offs + sz])
            img = Image.frombytes("RGBA", (w, h), px)
            out[nm] = img
        offs += sz
    return out


def ink_bbox(img, thresh=128):
    """Ink bounding box of a grayscale image, or None."""
    bb = img.getbbox() if isinstance(img, Image.Image) else None
    if bb is None:
        return None
    return bb


def band_ink(cn_gray, y0, y1, thresh=128):
    """Measure ink bbox of CN base within rows [y0, y1]. Returns
    (cx, cy, w, h) in full-image coords."""
    crop = cn_gray.crop((0, y0, 256, y1 + 1))
    px = crop.load()
    xs, ys = [], []
    for y in range(crop.size[1]):
        for x in range(crop.size[0]):
            if px[x, y] >= thresh:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return (sum(xs) / len(xs), y0 + sum(ys) / len(ys),
            max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)


def render_text_mask(text, font):
    tmp = Image.new("L", (512, 128), 0)
    d = ImageDraw.Draw(tmp)
    d.text((256, 64), text, font=font, fill=255, anchor="mm")
    bb = tmp.getbbox()
    return tmp.crop(bb)


def draw_centered_sub(base, text, font, cx, cy):
    ink = render_text_mask(text, font)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.paste(Image.merge("RGB", (ink, ink, ink)),
                (int(cx - ink.size[0] / 2), int(cy - ink.size[1] / 2)), ink)
    base.alpha_composite(layer)


def main():
    os.makedirs(PATCH, exist_ok=True)
    os.makedirs(QADIR, exist_ok=True)
    cns = load_cn()
    kai = ImageFont.truetype(KAI, 32)
    serif = ImageFont.truetype(SERIF, 15)
    try:
        serif.set_variation_by_name("SemiBold")
    except Exception:
        pass
    qa = []
    for name, (kind, lines, bands) in CARDS.items():
        img = cns[name].copy()
        gray = cns[name].convert("RGB").convert("L")
        px = img.load()
        if kind == "title":
            for text, ((t0, t1), (r0, r1)) in zip(lines, bands):
                for y in range(max(0, t0 - 3), min(256, t1 + 4)):
                    for x in range(256):
                        px[x, y] = (0, 0, 0, 255)
                for y in range(max(0, r0 - 3), min(256, r1 + 4)):
                    for x in range(256):
                        px[x, y] = (0, 0, 0, 255)
                tm = band_ink(gray, t0, t1)
                rm = band_ink(gray, r0, r1)
                ink = render_text_mask(text, kai)
                tw, th = ink.size
                # scale TW ink to CN ink box (reproduces wide calligraphy)
                scx = tm[2] / tw if tm else 1.0
                scy = tm[3] / th if tm else 1.0
                ink = ink.resize((max(1, int(tw * scx)),
                                  max(1, int(th * scy))), Image.LANCZOS)
                # bolden to CN stroke weight (measured bright-px parity)
                ink = ink.filter(ImageFilter.MaxFilter(3))
                layer = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
                white = Image.merge("RGB", (ink, ink, ink))
                layer.paste(white,
                            (int(tm[0] - ink.size[0] / 2),
                             int(tm[1] - ink.size[1] / 2)), ink)
                img.alpha_composite(layer)
                # shadow-glow: same-orientation faded blurred copy below
                # the title (NOT a mirror - verified by cross-correlation:
                # same-orient 0.785 vs flipped 0.502 on CN cards)
                fw, fh = ink.size
                fp = ink.load()

                def _ramp(a0, a1, blur):
                    ramp = Image.new("L", (fw, fh), 0)
                    rp = ramp.load()
                    for yy in range(fh):
                        a = int(a0 * (1 - yy / fh) + a1 * (yy / fh))
                        for xx in range(fw):
                            if fp[xx, yy] > 128:
                                rp[xx, yy] = a
                    return ramp.filter(ImageFilter.GaussianBlur(blur)) \
                        if blur else ramp

                rcx, rcy = (rm[0], rm[1]) if rm else (128, (r0 + r1) / 2)
                rlay = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
                rwhite = Image.new("RGB", (fw, fh), (255, 255, 255))
                rlay.paste(rwhite, (int(rcx - fw / 2), int(rcy - fh / 2)),
                           _ramp(200, 60, 0))
                rlay.paste(rwhite, (int(rcx - fw / 2), int(rcy - fh / 2)),
                           _ramp(90, 15, 12))
                img.alpha_composite(rlay)
        else:
            for text, cy in zip(lines, bands):
                y0, y1 = int(cy) - 9, int(cy) + 9
                for y in range(max(0, y0), min(256, y1 + 1)):
                    for x in range(256):
                        px[x, y] = (0, 0, 0, 255)
                draw_centered_sub(img, text, serif, 128, cy)
        w, h = img.size
        raw = img.tobytes()
        blob = encode_rgba(w, h, raw)
        open(os.path.join(PATCH, name), "wb").write(blob)
        print("%s -> %dB" % (name, len(blob)))
        side = Image.new("RGB", (512, 256), (40, 40, 40))
        side.paste(cns[name].convert("RGB"), (0, 0))
        side.paste(img.convert("RGB"), (256, 0))
        side.save(os.path.join(QADIR, "qa_" + name.replace(".G32", ".png")))
    print("QA in", QADIR)


if __name__ == "__main__":
    main()
