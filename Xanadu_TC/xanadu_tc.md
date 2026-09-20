# Xanadu Next Traditional Chinese — Lessons Learned (Phase 0–3)

Project: `Xanadu_TC/`. Target: Taiwan Mandarin, converted from the
Simplified patch (`Xanadu_Steam_CN/`), GOG game copy (`XanaduNext/`).
Run `python3 Xanadu_TC/tools/verify_1_3.py` — 23 checks, must be ALL PASS.

## Phase 0 — Workspace & formats

- `XanaduNext/` vs `XanaduNext.bak/`: 616 files each. Never touch the backup.
- `.dir` = N × 108B records (`100B cp932 name + u32LE size + u32LE zero`)
  + trailing u32 count. `.arc` = plain concatenation in dir order
  (offsets implicit/cumulative; `sum(sizes) == arc len` — verified on every
  archive). Matches aluigi's `xanadu_next.bms`. Repack rule: only the size
  field needs updating when a file grows.
- `font_scn.dat` (offs 316899, 560037B) and `font_sys.dat` (offs 876936,
  526381B) live inside `DATA/SYSTEM/system.arc`.
- Tooling present: python3 + `opencc-python-reimplemented` + Pillow.
  No quickbms/TiledGlyph/CrystalTile2 — all replaced with Python.

## Phase 1 — Text conversion (`tools/s2tw_convert.py`)

- The repo mixes encodings: `Object_CN.txt` is UTF-8, `exe内文本_CN.txt`
  is GBK, game files (`.scp/.tbl/.inf/_JIS.txt`) are cp932/ms932.
- **Trap (cost a full redo):** decoding cp932 game text as GBK yields
  plausible-looking garbage (`莉絲洛特` → `浠鉔棇摿`). Detect per file,
  decode game files strictly as cp932.
- Order of operations per game file: cp932 decode → **reverse-substitute**
  (`Missing_Kanji_Dictionary.txt` col3 → col2, 4560 hits: restores intended
  Simplified chars from JIS stand-ins) → OpenCC `s2twp` → Taiwan term fixes
  (`滑鼠/軟體/記憶體/影片/網路/遊標/預設/存檔`) → UTF-8 working copies.
- `EQUIP.tbl` is binary — skip in text phase, handle in Phase 5.
- Output: 243 `.utf8.txt` + `_encodings.log` (244 lines). Inventory:
  2179 CJK chars, 116 miss cp932 (vs 156 Simplified — Traditional fits better).

## Phase 2 — Remap dictionary (`tools/build_tw_dict.py`, `tools/fontmap.py`)

- **Trap:** Python-cp932-encodable ≠ game-addressable. Leads `0xED/0xEE`
  (and `0xEA+`) decode in Python but have **no verified font slots** —
  64 first-draft substitutes were invalid. Restrict the pool to
  fontmap-verified ranges only (assert `idx_of_char(sub) is not None`).
- Reuse policy: TW miss char identical to a Simplified intended char reuses
  its slot **only if mapped** (49 kept, e.g. `你→祢`); otherwise assign fresh.
- Fresh slots: JIS Level-2 rare kanji first (cp932 lead `>= 0xE0`). Common
  kanji (`丁万与`) may linger in untranslated Japanese leftover lines and
  would misrender if their slots are redrawn.
- Keep the exact 3-column `{U+XXXX} TW sub` format — the Simplified
  `Missing_Kanji_Instead.py` works unchanged. Sort by in-game frequency.
- Validation that matters: all 243 files substituted must `encode('cp932')`
  strict with 0 failures.

## Phase 3 — Fonts (hardest; most traps)

- Decompression: `tools/chr_decompress.py` (from Ell/xanadu-next, RE'd from
  `XANADU.exe` FUN_0044ab70/004e4260). Both fonts → exactly 1351680B =
  10560 × 128B. aluigi's note ("falcom algorithm") is the same codec.
- Font `.dat` is **multi-chunk** (first bit-stream chunk = 65520B, then
  `FUN_004e3fe0` continuation chunks). A single-chunk re-encode still
  decodes via the same dispatcher — safe.
- Glyph order (verified 148/148 redrawn Simplified slots GOG-vs-CN differ):
  single byte `0x20–0x7E` → index `byte-0x20`; leads `0x88–0x9F` →
  `2012 + (lead-0x88)*220 + trailpos`; leads `0xE0–0xE8` →
  `2012 + (lead-0xE0+24)*220 + trailpos`;
  trailpos `0x40–0x7E`→0–62, `0x80–0xFC`→63–187 (188 used + 32 pad per lead).
  Ranges `0x81–0x87` (symbols/kana) and `0xE9+` are unmapped — do not use.
- **Bit-packing trap (user-caught): each row is a u32, bit31 = leftmost**
  (`byte[r*4 + (3-c//8)] >> (7-c%8)`). LSB-first packing mirrors glyphs.
  **Never validate layout with symmetric chars** — `A` looks right mirrored;
  always use asymmetric proofs (`B` stem-left, CJK like `你` 亻-left).
- QA sheets need gaps between cells, labels below (never over glyphs), and
  ≥4× scale — cramped sheets hid the mirror bug. For content checks pair a
  smooth TTF reference next to the 1-bit cell (`tools/qa_proof.py`).
  Blocky 1-bit cells are native (original font is identical in structure).
- **Weight matters** (measured, not eyeballed): GOG CJK median ink 337,
  Simplified 316, first TW draft (MingLiU 30) only 188 — washed out inline.
  Final recipe mirrors the Simplified author: Noto Serif TC SemiBold 40 /
  Noto Sans TC Regular 30 (vendored in `sources/fonts/`, OFL), thresholds
  chosen by sweep (scn 96 → med 326; sys 32). Sweep first: too low = blobs,
  too high = vanishing thin strokes. `—`/`·` drawn programmatically
  (full-width bar rows 15–16; 4×4 centered dot).
- Strategy: redraw **only the 116 substitute slots**, keep 10444 GOG bytes
  identical (minimal diff, recompresses within ~5% of original).
- Recompression (`tools/chr_compress.py`, custom encoder): the subtle rule
  is **governing-unit placement** — a data byte belongs after the control
  unit whose bits govern it (units: 8 bits, then 16-bit words, LSB-first).
- **Font container trap (caused global garbage text + name-entry crash):**
  test-only `decompress()` ignores chunk sizes on the marker-0 path, so
  single-chunk output roundtrips in tests — but the GAME respects framing.
  Stock fonts are ~21 chunks of exactly 65520 raw bytes, each bit-stream
  terminating precisely at its chunk end (`chunk_size` == exact length,
  header incl.), chained while the next byte is nonzero. Fix:
  `compress_container_multi` mirrors this (boundary nudged so no
  non-final chunk has a zero size-low-byte); `validate_container`
  enforces dispatcher-strict parsing. Never ship single-chunk font .dats.
  New sizes differ from stock — handled by standard `.dir` size update
  at repack (Phase 7).

## Phase 4 — Map scripts (`tools/build_scp.py`, 205 files, 7 areas)

- No EN-merge needed: the Simplified `Final_Size_Control/*.scp` files are
  already transplanted (structure + Chinese). TW build = char-level convert
  only (working copy → TW-dict substitution → strict cp932 → CRLF). GOG
  skeleton check (area00/MP_0040): 32 key lines both sides, same order.
- Source selection: canonical `MP_XXXX.scp` only. 25 prefixed files are
  older/smaller drafts — EXCEPT all same-number contents differ, so verify,
  don't assume. `area06/MP_0699` has no canonical → larger `(3)` draft.
  `额外修正/MP_0087.scp` (boss-rotation fix) is an addition: area00 has no
  MP_0087 → include as `area00/MP_0087.scp`.
- False alarm documented: `area00/MP_0095` canonical (849B) looked like a
  stub vs 6987B draft — but the draft is a different untranslated scene;
  canonical is the final inn script. Judge by content, not size.
- **Line-ending trap (would have shipped doubled lines):** OpenCC emits
  `\r\n`, Windows text-mode write adds another `\r` → working copies had
  `\r\r\n`, which universal-newline reads double. Fix: normalize to single
  `\n` right after convert, write with `newline="\n"`; build script
  re-normalizes on read and emits CRLF. Verified: output 326 lines = source
  326 lines, non-key skeleton byte-identical (MP_0040: 253/253).
- Validation per file: strict cp932 encode, line-count parity, key-line
  (`sys|sel(|set_name|msg`, no `//`) parity vs Simplified source.

## Phase 5 — tbl/inf/exe (`tools/tblpatch.py`, `patch_object/equip/exe/cfg_u16`)

- Universal method for fixed-field binaries: diff GOG vs Simplified-CN,
  convert per hunk-group from the CN bytes (decode with 1-2B edge extension
  for split multi-byte chars, e.g. M_0310 地獄 where CN trail `6E` equals
  GOG `n`). Merge hunks only across NONZERO gaps ≤ 2 (M_0310 case); zero
  gaps are C-string boundaries. Null-terminate iff CN had a null there,
  else exact-fit fixed-width (shared-suffix case: Lamia name + `(欠)`
  suffix identical in both). Never write past the group span (+capped
  zero-extension for null-style). Validate: sizes identical, anchors
  intact, every changed byte inside a CN-diff region.
- Object.tbl: 147 hunks / 143 groups, 130 patched (13 intentionally wiped
  subtitle fields skipped). Multi-hunk IDs (Scoltula Eye/Foot) convert
  per-field from CN bytes — never via the ID text list (one entry can't
  cover divergent fields).
- EQUIP.tbl (in equip.arc, 708608B, same-size swap): 668 groups. **Binary
  tbl files hide chars the text phase never saw** → `tools/extend_tw_dict.py`
  (append-only! never reassign built slots): +5 misses (妮蘑鑲麵 + U+9EC3),
  then re-render fonts + recompress + rebuild all patches + re-verify.
  Dict is now 121 entries; verifier counts dynamically.
- guardian.tbl (4735B, text like scp) and 7 areaXX.inf: same pipeline as
  scp. inf sizes match sources byte-exact; areaXX.inf lives inside
  areaXX.arc (repack in Phase 7).
- XANADU.exe: 447 string-table hunks, sizes must stay byte-identical.
  Verified the only 3 SHORT-FIXED by bytes (trailing `\r`/`\t` control
  bytes preserved from CN layout — benign).
- xanadu_cfg.exe is a different beast: 1637 tiny diffs = binary dialog
  resources, NOT flat strings. Naive hunk conversion corrupted 36 spots
  (flags/lengths zeroed). Rules learned: (1) strict text gate
  (`_printable_ok`: printable + CJK-or-long) with CN-bytes fallback —
  fallback is always safe since CN shipped working; (2) for UTF-16LE dialog
  strings use pure Unicode conversion (Windows fonts, no game-font remap!);
  (3) diff-driven: only touch strings overlapping GOG-vs-CN diffs, so
  binary lookalikes elsewhere can't be corrupted. Result: 79 runs, 66
  real UI strings (解析度/視窗/滑鼠/更新率…), 0 structural leakage.
- OpenCC expansions break fixed spans: 刷新率→重新整理率 didn't fit —
  map the OUTPUT (`重新整理率→更新率`), plus 影象→影像. Check the log for
  TOO-LONG lines; each needs a manual shorter term.
- Python trap: double-wrapping `sys.stdout` with TextIOWrapper closes the
  buffer (finalizer) — guard every wrap with an encoding check.

## Phase 6 — picture cards (`tools/g32enc.py`, `tools/build_cards.py`)

- Only 11/138 images in picture.arc are translated: AREANAME01-06 (area
  title cards) + BOSS01-05 (boss/glossary cards). Found by name-set + byte
  diff GOG vs CN arcs.
- G32 = u32 w/h + planar R,G,B,A with a tiny RLE (ops 0-7: literals, value
  fills, zero/0xFF fills, short ≤16 + long forms). Decoder from
  Ell/xanadu-next; wrote `g32enc.py` (roundtrips within 0.3% of Falcom
  sizes). Long-form minimums bite: zero/0xFF runs need ≥33 for long form
  (17-32 must be two shorts) — same class of bug as the font bit-stream.
- Card anatomy: black bg (pure 0, safe to erase to black), gold bar
  byte-identical across all 9 title cards (keep untouched), white KaiTi
  titles + flipped/faded/blurred reflections, glossary = serif EN +
  dividers (keep) + small Song subs (redraw only subs).
- Transcribe CN text from the images by eye, convert via OpenCC (kept
  faithful to CN incl. quirks: BOSS02 洛蕾莱 vs BOSS05 洛蕾亲 stay distinct).
  All title pairs are same char-count CN→TW (fullwidth widths preserved).
- **Measure, don't assume**: titles are ~1.7× wider than naive 標楷體
  renders (wide calligraphy) — scale TW ink to the measured CN ink box
  per line. Reflections need double-strike (sharp core alpha 235→50 +
  halo 140→25 blur 2.5) to reach CN brightness (max 248); single blurred
  pass dies on thin strokes (max 86). Verified by metric (title xspan
  22-230 vs 20-232; refl max/mean) + side-by-side QA.
- Fonts: 標楷體 (kaiu.ttf, ships with Windows) for titles, Noto Serif TC
  SemiBold for glossary subs. Alpha is 255 everywhere — output opaque.

## The glyph-index truth (disassembled, not derived)

- `XANADU.exe` 0x44D560/0x44D5E9 computes the index; 0x44D620 does
  `glyph = font_base + index*128`. Formula (u8 wraparound load-bearing):
  single byte: `^`→26, `_`→12, backtick→0, 0xA0→2, else byte-0x20;
  double byte: `cl = lead-0x80` (<0xC0) or `lead+0x40` (≥0xC0);
  `t = trail+0xE0` (trail<0x80) else `trail+0xDF`; `idx = cl*220 + t`
  (blocks have NO pads: slots [32..219] per lead; ASCII halfwidth kana
  0xA1-0xDF live at 129-191!). It even predicts the tail blocks
  (0xEA→9272, 0xED→9932, 0xEE→10152 with holes, 0xE9 full at 9052).
- Earlier formula (cp932-pair order from base 2012) was off by exactly one
  lead stride (-220): all substitute art landed one block early, so the
  game showed original art for every substitute (祢叺姶喟…). Natives were
  unaffected visibly, empty-fit/codec checks couldn't discriminate, and
  symmetric test chars ('A') hid the mirror-class bugs. Lessons: derive
  NOTHING by analogy when the binary is available — disassemble the index
  function first; validate placements with ASYMMETRIC known art, never
  symmetric glyphs or differ-rate statistics (the author redrew ~everything,
  so differ-rate is vacuous).
- Text patches never changed (bytes address codepoints); only fonts were
  re-rendered with corrected indices + system.arc repacked.

## Quality pass — JP remnants + .notdef + NEC rows (post-playtest)

- Playtest reports decoded one by one (always trace bytes → slot → art):
  你/吧 show correctly (substitute bytes + font art; 叺 merely resembles
  叭 small). 對→対 was 対 U+5BFE text (336x, JP remnant). 巖 came from
  reverse-sub restoring the author's variant (311x). 游濱 was 戱 U+6231
  (variant in 結束遊戱 main menu!) hitting a .notdef box.
- `.notdef` trap: switching scn/sys to TC fonts silently boxed chars TC
  lacks (戱 U+6231, 嘇 U+5607) — `missing=[]` doesn't catch it (tofu has a
  bbox!). Fix: per-char TC→SC fallback via fontTools cmap (`pick_font`).
  Coverage-audit every font change (`coverage.py` pattern).
- `tools/jpnorm.py` (shared by s2tw/tblpatch/cfg paths, applied post-OpenCC
  since OpenCC leaves JP forms): 霊剣徳発読亜竜売抜呪図姫厳栄気専駆仏対巖戱
  → TW standards + 弁当→便當 + IT terms + 刷新率/重新整理率→更新率,
  影象→影像. Verify each target's slot class: native (euc-jp roundtrip),
  new SUB (德姬驅 + 33 NEC-row stragglers like 點僅樽 found by extending
  the miss criterion to encodable-but-unmapped), or native-slot art swap
  (説/說 share cp932 bytes → redraw slot 90e0 with 說).
- Codec collisions to respect: 説==說 bytes (slot art decides — hence the
  swap); 对/說 are unencodable so can never appear in cp932 outputs
  (sightings of them = misreads or UTF-16 cfg paths).
- Round 3: comprehensive Joyo table (81 pairs in `jpnorm.py`; dropped risky
  ones: bare 弁 (弁当 covered as phrase), 余 (classical pronoun use),
  identity pairs). New SUBs auto-found by extension (幫鄉紫…). Cards:
  match measured bright-px (titles needed 1px dilation; glow tuned by
  max/mean/px profile vs CN). Ship `MainData.TW/` (23 files,
  hash-verified vs tested build) + Traditional section in CN README.
- CORRECTION (user right, assumption wrong): the under-title effect is a
  same-orientation blurred glow, NOT a mirror — proven by
  cross-correlation (same-orient 0.785 vs flipped 0.502). Rebuilt as
  faded+blurred same-orient copies. Never assume effect geometry; measure
  against the original (correlation + brightness profiles).
- After any dict/font change: re-render → recompress → rebuild ALL patches
  (scp/tbl/exe/inf) → repack → verify + build-verify. Dict is append-only;
  verifier counts dynamically (NDICT + SLOT_SPECIAL).
- Round 2 (user-reported): JP batch-2 (実経団変覚伝戦様黒声当歓乗恵増収歳
  廃滞拡写険顕殓拝録郷壷焼験蔵絶両幇凛戋→TW) + MANUAL corrections map for
  CN-source translation errors (軍説→軍隊). Classify each report first:
  substitute-bytes (by design, verify slot art), JP remnant in text
  (normalize), misread at 32px (唹/嚏, 叺/叭 shapes), or no-corpus-hit
  (ask for screen location — 熹潯燔汢遍濟傳承 had zero hits anywhere).
- Round 3: user-reported 系統菜單 turned out to be 系統菜単 in the exe
  (JP 単 — invisible to 菜單 greps; always decode suspect bytes, don't
  grep assumed spellings). Fixed via 単→單 + global 菜單→選單, audited
  safe (all 6 corpus hits are UI contexts, zero food uses).
- xanadu_cfg.exe has THREE text encodings: UTF-16LE dialog resources
  (diff-driven convert), GBK single-byte control strings (button/combo
  labels — hunk engine reads them as cp932 mojibake, so a dedicated GBK
  pass from the CN baseline with NUL-field context requirement), and
  cp932 hunks (identity-skip: equal text keeps ORIGINAL bytes, since
  re-encoding can swap equivalent forms like FB51/EDF2 for 炅 — a false
  "corruption" alarm that ate an hour). Verdict rule: reproduce each
  stage separately and decode suspect spans in EVERY candidate encoding
  before concluding corruption (my own diff tool misdecoded u16 regions
  as GBK and manufactured "junk").
- Round 4 (user: cfg worse than CN patch): tried rebuilding xanadu_cfg
  from the ENGLISH GOG binary (`tools/build_cfg_gog.py`, CN only as
  reference, offset-overlap pairing). ABANDONED for dialog sections:
  GOG and CN dialog layouts genuinely differ (same offsets hold
  different items — GOG 'Select Next Item (Up)' vs CN '技能切换(左)'
  at 126140; cumulative shifts through string tables), so 1:1 pairing
  mislabels controls. The GOG build also zeroed binary fields on
  bring-over writes and would not launch (fixed with safe rules, but
  the pairing flaw is fatal). REVERTED to CN-baseline
  (hunks+u16+GBK, text-only changes, layout byte-identical to shipped
  CN). Lesson: different game versions = different resources; never
  rebase across versions by offset pairing — translate in place.
  GOG-based pairing is valid ONLY where layouts provably align
  (ASCII control labels); even there the GBK pass already covers it.
- Round 5 (user: cfg text menus broken — combo garbage, 視窗模式 garbage,
  开啟V-Sync): bytes for combo/mode strings were already correct TW;
  the real bug was half-converted 开啟V-Sync. Cause: regex finditer lets
  a DISCARDED odd-start match consume bytes of an even run (odd junk
  ending at N-1 orphaned 开 at N-2). Fix: enforce even alignment DURING
  matching (search loop, re-scan from odd+1). Recovered 3 runs.
  Audit discipline: byte-counters hit binary WORDs equal to CJK units
  (dialog-template IDs/styles near class names) — always check diff
  membership AND run-membership before calling it a leftover (remaining
  42 开 are all non-diff binary, correctly skipped).
- Round 6 (user: cfg selections to English): full-file revert was WRONG
  (user meant menu SELECTIONS, not everything — my misread, owned).
  Correct scope: single-byte GBK CJK selections -> GOG English
  (`tools/revert_cfg_items.py`: every TW GBK-CJK run overlapping a GOG
  ASCII slot restored to GOG field bytes); UTF-16 dialog text stays TW
  (locale-independent rendering, never complained about). Verified:
  all control regions byte-identical to GOG English, u16 TW terms all
  present, pefile valid (134 imports), every TW-vs-CN diff byte
  accounted (u16 converts + GBK reverts). Lesson: revert/convert by
  ENCODING LAYER (GBK vs UTF-16), not by guessed control roles — the
  encoding IS the render path.
- Round 6b (user: Windowed Mode NOT to English): KEEP_TW exclusions in
  revert_cfg_items (display-mode pair stays 視窗模式/無邊框視窗模式).
  Perf traps fixed in that script: per-byte list scans -> bisect, and
  a `continue` that skipped the index advance = infinite loop (0-byte
  log + timeout is the signature — check loop-variable progress first,
  not speed).
- Round 12 (user: Steam exes + split GOG.exe/Steam.exe dirs): no pristine
  Steam English base exists, so `tools/port_steam_exe.py` ports GOG-flow
  conversions by CN-byte search (same translation => same bytes) with
  fit gates. Lessons, each proven by a real corruption:
  * collect ALL writes first, claim biggest-first — short strings
    (窗口模式) otherwise clobber longer ones they sit inside (无边框…).
  * exact spans need a CJK text-likeness gate — 1-2 byte version drift
    otherwise rewrites thousands of binary spots (killed 5 imports:
    GetDeviceCaps/FreeLibrary/IsDebuggerPresent/LoadLibraryA/
    VirtualAlloc/EnableWindow via single 0x62->0xDB inside the names).
  * refuse writes below the first section AND inside import structures
    (descriptors, ILT/IAT, hint/name ranges via pefile) AND inside
    executable sections — a 2-byte span matched e_lfanew and killed
    the binary outright.
  * verify imports per-DLL (134/134) not just parseability; audit terms
    with readable contexts (残鉄転続 hits were binary soup, not text).
  Steam TW exes validate (5/202, 4/134), sizes byte-identical.
- Round 7 (user: 視窗模式 shows ?敦耀宅 on their machine; 手柄->手把):
  GBK(視窗模式) decoded as Big5 == reported garbage, PROVING their
  system codepage is 950 — so KEEP_TW selections are now encoded BIG5
  (same byte sizes as GBK, all fits carry over; `revert_cfg_items.py`).
  手柄->手把 added to TERMS (puts 手把 in MP_1003 + cfg u16; 把 is
  native cp932, no new slot). Ops lesson: repack.py rmtree fails on a
  LOCKED exe (program running) and leaves the build half-deleted —
  always confirm the game is closed first; recovery = rerun repack
  (rebuilds from base+patch deterministically).
- Round 9 (user: 總 shown as 総; Droid Sans for glyphs?): added 総->總
  (native cp932 slot). No Droid fonts on the system — user approved the
  vendored Noto Sans TC instead: dialogue font re-rendered NotoSansTC
  Regular 44/th96 (was Serif SemiBold 40), matching the original gothic
  look; UI font was already Sans. All 165 slots re-rendered, verifiers
  green. Note: static NotoSansTC.ttf has no SemiBold variation (VF file
  does) — Regular 44 at th96 calibrates closest (meanabs ~37).
- Round 10 (user: 惱 shown as 悩): added 悩->惱 (native cp932, no font
  work). No new SUBs; text-only rebuild.
- Round 11 (user: "can't you scan all dialogues for Shift-JIS?"): YES —
  built `tools/audit_shipped.py` + `tools/jpscan.py`. Findings:
  * patch_object.py NEVER applied jpnorm (only OpenCC) — every translated
    Object.tbl name kept JP forms. Fixed; added the whole-file jpscan
    pass there and in patch_equip (untranslated CN regions also kept JP,
    e.g. 図両亜絵転 in encyclopedia entries).
  * Scanner pitfalls that produced phantom hits: (a) SUB-slot chars must
    be translated to their TW meaning before scanning (else 濛 looks like
    a stray JP char); (b) scan canonical shipped files only — editor
    backups with mojibake names (0093(OLD) 等) poison counts; (c) never
    count chars in raw binary (亀x1425 was binary coincidence).
  * jpscan re-sync bug: a stray binary lead byte (0xED) swallowed the
    real run start 0x93 0xAC ('闘用'), because `i=max(j,i+1)` skipped it
    — on short runs advance ONE byte, not past the run.
  * ~120 new JPNORM pairs (249 total) from a curated Joyo/hyogaiji
    sweep; new SUBs auto-assigned (步巢仿毎緣) + add_binary_subs.py for
    targets that exist ONLY in binary paths (雞醬 — invisible to the
    working-copy scan).
  * Audit result: 0 JP suspects left in shipped text (was 98).
    Valid-TW chars explicitly excluded from the scan (為余弁芸徊減豫着
   閑汎箇) so they can't be "fixed" wrongly.
- Round 8 (user: 8 JP pairs in game + sweep more): found my "comprehensive"
  Joyo batch NEVER APPLIED (two failed edits I didn't notice — always
  verify edit effects, not just success messages!). Added 48 + 48 pairs
  (now 180; deliberately excluded 為->爲 which corrupts correct 為, and
  global 制->製 which corrupts 強制/控制/制度/制限 — audited: zero
  material-suffix 制 exists in corpus). New SUBs auto-found (步->並,
  巢->京, 仿->个, 每->丿, 緣->丰). Verification discipline: scan
  CLASSIFIED sources (working copies = 0/181 JP sources left), never raw
  binary decodes (binary-coincidence CJK like 亀x1425 poisons naive
  counts). Non-shipped duplicates (JP-reference files with mojibake
  names in source tree) excluded from conclusions — build uses the 205
  canonical scripts only. Left as-is deliberately: 説-slot (renders 說),
  峠 (kokuji, no twin), 柵 (same in TW), 戻す (comment-only, no twin),
  余/弁/芸 (context-dependent).
- Stdout discipline: repo tools wrap stdout unconditionally — importing
  one from a wrapped script orphans/closes the buffer ("I/O operation on
  closed file"). All repo tools now guard the wrap; debug scripts print
  ASCII-escaped or write files.
- Cards: match measured bright-px, not just bbox — titles needed 1px
  dilation (1188→2650px) and reflections a sharp-core + wide-halo
  double strike to reach CN presence. Static cards verified upright;
  "upside-down" reports need a screenshot (reflection is mirrored
  by design).
- repack.py writes BUILD_INFO.txt (date + dict count + script count) so
  testers can confirm they run the fresh build — stale-copy confusion
  wastes entire debug cycles.

## Phase 7 — repack + verify (`tools/repack.py`, `tools/verify_build.py`)

- Build = fresh copy `XanaduNext/` → `Xanadu_TW/` + drop-ins (Object.tbl,
  both exes) + 10 arc rebuilds. Replacer matches .dir names EXACTLY
  (dev leftovers like `0093(OLD)\*.scp` untouched); missing names would
  append (none needed — GOG arcs already contain MP_0087/MP_0699 slots).
- .dir rewritten GOG-style (same order, updated sizes, 4-byte count).
  Ignore the CN equip.dir's 20 extra bytes (QuickBMS reimport padding).
- Scope = Simplified parity: areas 00,05-10 (+equip/picture/system);
  areas 01-04/12/14/20/51/52/60 stay as-is, same as the CN patch.
- `verify_build.py`: every replaced entry re-extracts byte-identical
  (228 total), every untouched entry identical to GOG (4000+), all dir
  sizes/counts consistent. Packaged fonts decode to the TW raws.
- Automated limits: the game can't launch headless here. Manual checklist:
  1. Config tool opens, Traditional labels, settings save.
  2. New game: opening dialogue renders (font check), no tofu.
  3. Area cards show on map transitions (Traditional titles).
  4. Talk/battle/shop UI, item names + descriptions (EQUIP.tbl).
  5. Monsters/bosses named (Object.tbl), boss cards, ending.
  6. Known CN-patch issues:      0087 boss rotation, settlement page,
     死者異界, 60fps jump (refresh mode 粗糙 workaround).
- **`.dir` flag trap (the actual crash cause):** bytes [104:108] are NOT
  reserved-zero — a 0/1 flag on most entries (156/565 area00, 140/262
  equip, even 4/57 system; likely compressed-or-not). Phase-0 claim came
  from system.arc only. My writer zeroed them → game misread payloads →
  global garbage + name-entry Runtime Error (all builds incl. T1/T2).
  Found via single-variable builds (stock✓ T0a✓ T0b✗) + pure-roundtrip
  .dir byte diff. Fix: preserve flag bytes verbatim; `verify_build.py`
  checks flags on every arc.
  CONFIRMED by playtest: with flags preserved, name entry works.
  Follow-up fix (noisy TW glyphs with game running): the multi-chunk files
  were still missing the 1-byte inter-chunk flag — the dispatcher continues
  at stop_pos+1 iff the byte at stop_pos is nonzero, so each non-final
  chunk needs [size][0x00][stream][0x01-flag], final chunk + 0x00 trailer
  (stock layout; Ell's size-ignoring decoder masked this too).
  `validate_container` models flags strictly.
  Debugging method that paid off: Simplified-from-scratch T1 (repack-only)
  + T2 (full-CN) builds, then single-variable T0a/T0b split — each build
  reuses `repack.rebuild_arc` so fixes propagate to all of them.

## Environment gotchas (Windows PowerShell 5.1, cp950 console)

- No `&&` (use `;`), no `head`/`pip` bare words; `>` redirect writes UTF-16.
- Python stdout with CJK: wrap with
  `io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
  errors='backslashreplace')` or print `unicode_escape`.
- Filenames with CJK break console listing — enumerate via Python `os.listdir`.
