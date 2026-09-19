"""Xanadu Next font glyph-index map — REVERSE-ENGINEERED FROM XANADU.exe.

The index function lives at 0x44D560 (dispatcher) + 0x44D5E9 (double-byte
core); the renderer at 0x44D620 does ``glyph = font_base + index*128``
(shl ecx,7), proving 128-byte glyphs. DO NOT "derive" this from JIS
tables — an earlier formula (cp932-pair order from a base of 2012) was
off by exactly one lead stride (220) and produced working-looking but
in-game-wrong fonts. The disassembly is ground truth:

  single byte b (<0x80, or 0xA0-0xDF):
      b == 0x60 -> 0;  b == 0x5F -> 12;  b == 0xA0 -> 2;  b == 0x5E -> 26
      else idx = b - 0x20
  double byte (lead, trail), leads 0x81-0x9F and 0xE0-0xFF:
      cl = (lead - 0x80) & 0xFF          if lead < 0xC0
         = (lead + 0x40) & 0xFF          if lead >= 0xC0   (wraps mod 256)
      t  = (trail + 0xE0) & 0xFF         if trail < 0x80
         = (trail + 0xDF) & 0xFF         otherwise         (wraps mod 256)
      idx = cl * 220 + t
  (u8 wraparound is load-bearing: e.g. lead 0xE0 -> cl 0x20, and trail
  0xFC -> t 0xDB. Trail 0x7F never occurs in valid Shift-JIS.)

Consequences: double-byte blocks are 220-stride starting at cl*220 with
trail slots [32..219] (NOT base+0..187 with 32 pads). The old formula
coincided for nothing load-bearing; every substitute slot moves by -220
(plus trail remap). Text patches are unaffected (bytes address
codepoints, not indices) — only font rendering changes.
"""

FONT_BASE_DOUBLE = None  # no single base; see formula above


def idx_of_char(ch):
    """Font glyph index for a character, or None if unaddressable."""
    try:
        b = ch.encode("cp932")
    except Exception:
        return None
    if len(b) == 1:
        v = b[0]
        if v == 0x60:
            return 0
        if v == 0x5F:
            return 12
        if v == 0xA0:
            return 2
        if v == 0x5E:
            return 26
        if 0x20 <= v <= 0x7E:
            return v - 0x20
        return None
    lead, trail = b
    if not ((0x81 <= lead <= 0x9F) or (0xE0 <= lead <= 0xFF)):
        return None
    cl = (lead - 0x80) & 0xFF if lead < 0xC0 else (lead + 0x40) & 0xFF
    t = (trail + 0xE0) & 0xFF if trail < 0x80 else (trail + 0xDF) & 0xFF
    return cl * 220 + t


def is_mapped(ch):
    return idx_of_char(ch) is not None
