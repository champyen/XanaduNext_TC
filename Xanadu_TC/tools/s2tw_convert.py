"""Phase 1 (v2): Simplified -> Taiwan Traditional working copies.

Per-type handling (fixes v1 which decoded everything as GBK):
  * UTF-8 refs (Object_CN.txt)            : utf-8 decode -> OpenCC s2twp
  * exe内文本_CN.txt                       : gbk decode -> OpenCC s2twp
  * game-ready ms932 files (.scp/.inf/_JIS*.txt/guardian.tbl):
      cp932 decode -> reverse-substitute (Missing_Kanji_Dictionary col3->col2,
      restoring intended Simplified chars) -> OpenCC s2twp
  * binary (.tbl EQUIP)                    : skipped, Phase 5

Writes UTF-8 working copies to text_work_TW/ mirroring the source tree.
"""
import os
import sys

SRC = r"C:\Users\champ\workspace\Xanadu_Steam_CN\Text"
DST = r"C:\Users\champ\workspace\Xanadu_TC\text_work_TW"
DICT = r"C:\Users\champ\workspace\Xanadu_Steam_CN\Tool\Missing_Kanji_Dictionary.txt"

# (Taiwan terms + JP-form normalization live in jpnorm.normalize,
# applied after OpenCC in main().)


def load_reverse_sub():
    """substitute char (col3, as stored in game files) -> intended Simplified (col2)."""
    rev = {}
    for line in open(DICT, encoding="utf-8"):
        parts = line.split()
        if len(parts) >= 3:
            rev[parts[2]] = parts[1]
    return rev


def main():
    from opencc import OpenCC

    cc = OpenCC("s2twp")
    rev = load_reverse_sub()
    print("reverse-sub entries: %d" % len(rev))
    log = []
    nfiles = nrev = 0
    for root, _dirs, files in os.walk(SRC):
        for fn in files:
            src = os.path.join(root, fn)
            rel = os.path.relpath(src, SRC)
            raw = open(src, "rb").read()
            try:
                text = raw.decode("utf-8")
                enc = "utf-8"
            except UnicodeDecodeError:
                if fn == "EQUIP.tbl":
                    log.append(rel + " BINARY-skip-Phase5")
                    continue
                if rel.endswith("_CN.txt"):
                    text = raw.decode("gbk")
                    enc = "gbk"
                else:
                    text = raw.decode("cp932")
                    enc = "cp932"
                    hits = sum(text.count(k) for k in rev)
                    for k, v in rev.items():
                        if k in text:
                            text = text.replace(k, v)
                    nrev += hits
            tw = cc.convert(text)
            # normalize: OpenCC may emit \r\n; force single \n before write
            tw = tw.replace("\r\n", "\n").replace("\r", "\n")
            from jpnorm import normalize as _normalize
            tw = _normalize(tw)
            dst = os.path.join(DST, rel + ".utf8.txt")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            # newline="\n": no platform translation, exactly single \n endings
            open(dst, "w", encoding="utf-8", newline="\n").write(tw)
            log.append(rel + " " + enc)
            nfiles += 1
    open(os.path.join(DST, "_encodings.log"), "w", encoding="utf-8").write(
        "\n".join(log) + "\n"
    )
    print("converted files: %d reverse-sub hits: %d" % (nfiles, nrev))


if __name__ == "__main__":
    sys.exit(main())
