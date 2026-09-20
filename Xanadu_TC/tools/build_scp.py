"""Phase 4: build game-ready TW .scp files.

Source selection (Final_Size_Control + one extra fix):
  * canonical MP_XXXX.scp files (drafts/backups with prefixed names are older
   /smaller work copies - verified: canonical is always the largest content)
  * area06/MP_0699: no canonical; use larger "(3)" draft (9043B)
  * area00/MP_0087.scp: absent; use Extra-fixes MP_0087 (boss-rotation fix)
Transform per file: working copy (.utf8.txt, Traditional) -> apply TW
remap dictionary -> strict cp932 encode -> CRLF bytes.
Output: Xanadu_TC/patch/map/areaXX/MP_XXXX.scp
Validation: key-line counts (sys|sel(|set_name|msg, no //) match the
Simplified source; byte length close to source (all CJK stay 2-byte).
"""
import os
import re
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="backslashreplace")

CN_TEXT = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_Steam_CN\Text"
MAP_SRC = os.path.join(CN_TEXT, "map", "Final_Size_Control")
WORK = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\text_work_TW"
PATCH = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\patch\map"
DICT = os.path.join(WORK, "Missing_Kanji_Dictionary_TW.txt")

CANON = re.compile(r"^MP_([0-9a-f]{4})\.scp$", re.IGNORECASE)
KEY = re.compile(r"sys|sel\(|set_name|msg", re.I)


def num_of(fn):
    m = re.search(r"MP_([0-9a-f]{4})\.scp$", fn, re.IGNORECASE)
    return m.group(1).lower() if m else None


def keylines(text):
    return [l for l in text.splitlines()
            if "//" not in l and KEY.search(l)]


def select_sources():
    """Return [(area, out_name, src_path)]."""
    sel = []
    for area in sorted(os.listdir(MAP_SRC)):
        ap = os.path.join(MAP_SRC, area)
        if not os.path.isdir(ap):
            continue
        by_num = {}
        for f in os.listdir(ap):
            n = num_of(f)
            if n:
                by_num.setdefault(n, []).append(f)
        for n, fs in sorted(by_num.items()):
            canon = [f for f in fs if CANON.match(f)]
            if len(canon) == 1 and len(fs) == 1:
                sel.append((area, canon[0], os.path.join(ap, canon[0])))
            elif n == "0699":
                # no canon: use larger "(3)" draft
                best = max(fs, key=lambda f: os.path.getsize(os.path.join(ap, f)))
                sel.append((area, "MP_0699.scp", os.path.join(ap, best)))
            elif canon:
                # canonical wins (verified largest/final); report if odd
                c = canon[0]
                sizes = {f: os.path.getsize(os.path.join(ap, f)) for f in fs}
                if sizes[c] != max(sizes.values()):
                    print("WARN %s/%s canonical not largest: %s" % (area, n, sizes))
                sel.append((area, c, os.path.join(ap, c)))
            else:
                print("SKIP %s/%s (no canonical): %s" % (area, n, fs))
    # extra fix -> area00
    extra = None
    for root, _, fs in os.walk(os.path.join(CN_TEXT, "map")):
        if os.path.abspath(root) == os.path.abspath(MAP_SRC):
            continue
        for f in fs:
            if num_of(f) == "0087":
                extra = os.path.join(root, f)
    if extra:
        sel.append(("area00", "MP_0087.scp", extra))
        print("extra fix: %s -> area00/MP_0087.scp" % extra)
    return sel


def main():
    dmap = {}
    for line in open(DICT, encoding="utf-8"):
        p = line.split()
        dmap[p[1]] = p[2]
    sel = select_sources()
    print("selected: %d" % len(sel))
    ok = warn = 0
    for area, out_name, src in sel:
        rel = os.path.relpath(src, CN_TEXT)
        wcopy = os.path.join(WORK, rel + ".utf8.txt")
        text = open(wcopy, encoding="utf-8").read()
        # normalize line endings: working copies may carry \r\r\n
        # (OpenCC emits \r\n, Windows text-mode write adds another \r)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        for k, v in dmap.items():
            if k in text:
                text = text.replace(k, v)
        try:
            blob = text.replace("\n", "\r\n").encode("cp932")
        except UnicodeEncodeError as e:
            print("ENCODE-FAIL %s/%s: %s" % (area, out_name, e))
            warn += 1
            continue
        outdir = os.path.join(PATCH, area)
        os.makedirs(outdir, exist_ok=True)
        open(os.path.join(outdir, out_name), "wb").write(blob)
        # validation vs Simplified source
        try:
            src_text = open(src, encoding="cp932").read()
        except Exception:
            src_text = open(src, encoding="gbk").read()
        ks, kt = len(keylines(src_text)), len(keylines(text))
        ds = len(open(src, "rb").read())
        flag = "" if ks == kt else " KEY-MISMATCH src=%d tw=%d" % (ks, kt)
        if flag:
            warn += 1
        else:
            ok += 1
        if flag or abs(len(blob) - ds) > max(64, ds // 20):
            print("%s/%s srcB=%d twB=%d keys=%d%s" %
                  (area, out_name, ds, len(blob), kt, flag))
    print("built ok=%d warnings=%d" % (ok, warn))


if __name__ == "__main__":
    sys.exit(main())
