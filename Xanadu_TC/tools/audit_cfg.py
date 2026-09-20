import io
import os
import re
import struct
import sys

if (sys.stdout.encoding or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='backslashreplace')
sys.path.insert(0, r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\tools")
from jpnorm import normalize  # noqa: E402
from opencc import OpenCC  # noqa: E402

PATCH = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\patch\xanadu_cfg.exe"
GOGP = r"C:\Users\champ\workspace\XanaduNext_workspace\XanaduNext\xanadu_cfg.exe"
CNP = (r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_Steam_CN\GOG\GOG_xanadu_cfg.exe")

blob = open(PATCH, "rb").read()
gog = open(GOGP, "rb").read()
cn0 = open(CNP, "rb").read()
diff = set(i for i, (x, y) in enumerate(zip(gog, cn0)) if x != y)

cc = OpenCC("s2twp")


def convert(s):
    t = cc.convert(s)
    return normalize(t)


# 1) cp932 runs: lead bytes 0x81-0x9F,E0-FC + trail, len>=2 chars
strings = []  # (kind, off, text)
i, n = 0, len(blob)
while i < n:
    b = blob[i]
    if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
        j = i
        units = 0
        ok = True
        while j + 1 < n:
            lb, tb = blob[j], blob[j + 1]
            if not ((0x81 <= lb <= 0x9F or 0xE0 <= lb <= 0xFC)
                    and (0x40 <= tb <= 0xFC and tb != 0x7F)):
                break
            j += 2
            units += 1
        if units >= 2:
            try:
                t = blob[i:j].decode("cp932")
                if any("\u4e00" <= c <= "\u9fff" for c in t):
                    strings.append(("cp932", i, t))
            except Exception:
                pass
            i = j
            continue
    i += 1

# 2) UTF-16LE runs with CJK
for m in re.finditer(
        b"((?:[\\x20-\\x7e]\\x00|[\\x00-\\xff][\\x30\\x34-\\x4d\\x4e-\\x9f\\xf9-\\xfa\\xff]){2,})\\x00\\x00",
        bytes(blob)):
    if m.start() % 2 == 1:
        continue
    try:
        t = m.group(1).decode("utf-16-le")
    except Exception:
        continue
    if any("\u4e00" <= c <= "\u9fff" for c in t):
        strings.append(("u16", m.start(), t))

print("CJK strings found:", len(strings))
left = []
for kind, off, t in strings:
    tw = convert(t)
    if tw != t:
        in_diff = any(k in diff for k in range(off, off + 60))
        left.append((kind, off, t, tw, in_diff))
print("strings still convertible (leftovers):", len(left))
for kind, off, t, tw, in_diff in left[:60]:
    print("[%s@%d diff=%s] %r -> %r" % (kind, off, in_diff, t[:44], tw[:44]))
open(r"C:\Users\champ\AppData\Local\Temp\opencode\cfgleft.txt", "w",
     encoding="utf-8").write("\n".join(
         "[%s@%d] %r -> %r" % (k, o, a, b) for k, o, a, b, _ in left))
