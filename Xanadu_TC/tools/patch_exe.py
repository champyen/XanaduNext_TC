"""Phase 5d: patch exe string tables (Simplified -> Traditional).

XANADU.exe hunks all sit in string-table regions - no code changes.
Same hunk engine as tbl (CN bytes -> TW). HARD constraint: exe size
must stay byte-identical (code/data offsets), so any OVERFLOW is fatal
for that string (reported, kept as CN).
Output: patch/XANADU.exe, patch/xanadu_cfg.exe (CN baseline for cfg;
combo-box items are reverted to English by a later step, see
tools/revert_cfg_items.py and xanadu_tc.md round 6).
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tblpatch import _printable_ok, patch_buffer  # noqa: E402

if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="backslashreplace")

GOG_DIR = r"C:\Users\champ\workspace\XanaduNext"
CN_GOG = r"C:\Users\champ\workspace\Xanadu_Steam_CN\GOG"
PATCH = r"C:\Users\champ\workspace\Xanadu_TC\patch"

JOBS = [("XANADU.exe", "GOG_XANADU.exe", "XANADU.exe", None),
        # xanadu_cfg: the hunk stage only establishes the CN baseline
        # here (0 conversions proven — identity-skip keeps every byte);
        # real cfg conversion lives in patch_cfg_u16 (u16+GBK passes).
        ("xanadu_cfg.exe", "GOG_xanadu_cfg.exe", "xanadu_cfg.exe",
         _printable_ok)]


def main():
    for local, cn_name, out_name, accept in JOBS:
        gog = open(os.path.join(GOG_DIR, local), "rb").read()
        cn = open(os.path.join(CN_GOG, cn_name), "rb").read()
        assert len(gog) == len(cn), (local, len(gog), len(cn))
        out, (ok, skip, warn) = patch_buffer(gog, cn, tag=local,
                                             accept=accept)
        assert len(out) == len(gog)
        open(os.path.join(PATCH, out_name), "wb").write(out)
        print("%s patched=%d skipped=%d warnings=%d size=%d" %
              (out_name, ok, skip, warn, len(out)))


if __name__ == "__main__":
    main()
