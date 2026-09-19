"""Phase 5c: text-pipeline files - guardian.tbl + areaXX.inf.

Same transform as scp: working copy -> TW remap dict -> strict cp932 ->
CRLF. Output: patch/equip/guardian.tbl, patch/Map/areaXX.inf
(areaXX.inf goes back into areaXX.arc at repack).
"""
import io
import os
import sys

if (sys.stdout.encoding or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='backslashreplace')

CN_TEXT = r"C:\Users\champ\workspace\Xanadu_Steam_CN\Text"
WORK = r"C:\Users\champ\workspace\Xanadu_TC\text_work_TW"
PATCH = r"C:\Users\champ\workspace\Xanadu_TC\patch"
DICT = os.path.join(WORK, "Missing_Kanji_Dictionary_TW.txt")

JOBS = [("equip/guardian.tbl", "equip/guardian.tbl")]
for f in sorted(os.listdir(os.path.join(CN_TEXT, "Map_name"))):
    JOBS.append(("Map_name/" + f, "Map/" + f))


def main():
    dmap = {}
    for line in open(DICT, encoding="utf-8"):
        p = line.split()
        dmap[p[1]] = p[2]
    ok = warn = 0
    for src_rel, out_rel in JOBS:
        wcopy = os.path.join(WORK, src_rel + ".utf8.txt")
        if not os.path.exists(wcopy):
            print("NO-WORKING-COPY " + src_rel)
            warn += 1
            continue
        text = open(wcopy, encoding="utf-8").read()
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        for k, v in dmap.items():
            if k in text:
                text = text.replace(k, v)
        try:
            blob = text.replace("\n", "\r\n").encode("cp932")
        except UnicodeEncodeError as e:
            print("ENCODE-FAIL %s: %s" % (src_rel, e))
            warn += 1
            continue
        outp = os.path.join(PATCH, out_rel)
        os.makedirs(os.path.dirname(outp), exist_ok=True)
        open(outp, "wb").write(blob)
        print("built %s %dB" % (out_rel, len(blob)))
        ok += 1
    print("ok=%d warnings=%d" % (ok, warn))


if __name__ == "__main__":
    main()
