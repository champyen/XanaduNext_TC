"""Decompress Falcom's compressed .chr / .map archive payload.

Reverse-engineered from FUN_0044ab70 (the dispatcher) and FUN_004e4260
(the bit-stream decoder) in XANADU.exe.

Container layout
----------------

  while True:
      u16 chunk_size    (little-endian)        # ignored by the bit-stream
                                              # decoder; tracked by the
                                              # alternate FUN_004e3fe0
                                              # decoder (not used by .chr)
      u8  marker                                # 0 → bit-stream decoder
                                                # else → FUN_004e3fe0 path
      ... encoded payload ...

The decoder advances the input pointer past each chunk's payload.
After the bit-stream decoder returns, the byte at the input pointer is
the *next chunk's marker byte*.  If that byte is 0, the stream ends.
Otherwise another chunk follows: read another u16 size + marker, run
decoder again.

Per-chunk bit-stream decoder (FUN_004e4260)
-------------------------------------------

- Initial 8-bit control word from byte at (chunk_start + 1).
- Refills are 16-bit little-endian words from the input.
- Bits consumed LSB-first.  Variable-length integers (FUN_004e4200
  helper) accumulate MSB-first: ``v = (v << 1) | bit``.
- Per token:
    - bit ``0``  literal — copy 1 byte from input.
    - bit ``1``  back-reference:
        - bit ``0``  ``offset = next_byte()``                  (8-bit short)
        - bit ``1``  ``offset = (read_bits(5) << 8) | next_byte()``  (13-bit)
        - On the 13-bit path only:
            - ``offset == 0``  end of chunk
            - ``offset == 1``  long-RLE (4-bit or 12-bit length + 1-byte
                                value, emits length+0xe copies of value)
        - Otherwise length is a unary code:
              1            → 2
              01           → 3
              001          → 4
              0001         → 5
              00001        → ``read_bits(3) + 6``
              00000        → ``read_byte() + 14``
"""

from __future__ import annotations


class ChrDecompressError(Exception):
    pass


class _BitReader:
    __slots__ = ("buf", "pos", "word", "bits")

    def __init__(self, buf: bytes, start: int) -> None:
        self.buf = buf
        # FUN_004e4260 setup: control_word = byte at start+1 (8 bits),
        # then input pointer = start+2.
        self.word = buf[start + 1]
        self.bits = 8
        self.pos = start + 2

    def get_bit(self) -> int:
        if self.bits == 0:
            self.word = self.buf[self.pos] | (self.buf[self.pos + 1] << 8)
            self.pos += 2
            self.bits = 16
        b = self.word & 1
        self.word >>= 1
        self.bits -= 1
        return b

    def read_bits(self, n: int) -> int:
        v = 0
        for _ in range(n):
            v = (v << 1) | self.get_bit()
        return v

    def read_byte(self) -> int:
        b = self.buf[self.pos]
        self.pos += 1
        return b


def _decode_lz77_chunk(buf: bytes, chunk_start: int, chunk_size: int, out: bytearray) -> int:
    """FUN_004e3fe0 decoder: a chunked LZ77 variant used for continuation
    chunks of compressed .chr files (any chunk whose marker byte is
    non-zero).  Each chunk is exactly ``chunk_size`` bytes long
    *including* the 2-byte size header — the decoder loops until it has
    consumed exactly that many input bytes.

    Per token (from input):

      c >= 0x80  back-reference
                 offset = ((c & 0x1f) << 8) | next_byte()
                 length = ((c >> 5) & 3) + 4               (4..7)
                 # 0x60-prefixed extension bytes extend length:
                 while next_byte high-3-bits == 0x60:
                     length += that_byte & 0x1f

      0x40 <= c < 0x80  RLE
                 if (c & 0x10) == 0:
                     length = (c & 0x0f) + 4
                     value  = next_byte()
                     # 2 bytes total
                 else:
                     length = ((c & 0x0f) << 8) + next_byte() + 4
                     value  = next_byte()
                     # 3 bytes total

      else (c < 0x40)  literal block
                 if (c & 0x20) == 0:
                     length = c & 0x1f
                     # 1 + length bytes total
                 else:
                     length = ((c & 0x1f) << 8) | next_byte()
                     # 2 + length bytes total
                 copy `length` raw bytes from input
    """
    pos = chunk_start + 2  # skip u16 size header
    consumed = 2  # the 2-byte size counts toward chunk_size

    while consumed != chunk_size:
        c = buf[pos]
        pos += 1

        if c >= 0x80:
            # back-reference
            consumed += 2
            offset = ((c & 0x1F) << 8) | buf[pos]
            pos += 1
            length = ((c >> 5) & 3) + 4
            # Optional 0x60-prefixed extension bytes
            while consumed != chunk_size:
                ext = buf[pos]
                if (ext & 0xE0) != 0x60:
                    break
                pos += 1
                length += ext & 0x1F
                consumed += 1

            if offset == 0:
                raise ChrDecompressError(
                    f"backref offset 0 in lz77 chunk at {pos:#x}"
                )
            base = len(out) - offset
            for i in range(length):
                out.append(out[base + i])

        elif c >= 0x40:
            # RLE
            if (c & 0x10) == 0:
                length = (c & 0x0F) + 4
                value = buf[pos]
                pos += 1
                consumed += 2
            else:
                hi = c & 0x0F
                mid = buf[pos]
                value = buf[pos + 1]
                pos += 2
                length = (hi << 8) + mid + 4
                consumed += 3
            out.extend(bytes([value]) * length)

        else:
            # literal block
            if (c & 0x20) == 0:
                length = c & 0x1F
                consumed += 1 + length
            else:
                length = ((c & 0x1F) << 8) | buf[pos]
                pos += 1
                consumed += 2 + length
            out.extend(buf[pos : pos + length])
            pos += length

    return pos


def _decode_one_chunk(buf: bytes, chunk_start: int, out: bytearray) -> int:
    """Decode one bit-stream chunk into ``out`` (appending).  Returns the
    input position immediately after the chunk's terminating offset=0."""
    br = _BitReader(buf, chunk_start)

    while True:
        if br.get_bit() == 0:
            out.append(br.read_byte())
            continue

        # back-reference
        if br.get_bit() == 0:
            offset = br.read_byte()
        else:
            high = br.read_bits(5)
            low = br.read_byte()
            offset = (high << 8) | low

            if offset == 0:
                return br.pos

            if offset == 1:
                # long RLE
                if br.get_bit() == 0:
                    length = br.read_bits(4)
                else:
                    length = (br.read_bits(4) << 8) | br.read_byte()
                value = br.read_byte()
                out.extend(bytes([value]) * (length + 0xE))
                continue

        # length unary code
        if br.get_bit() == 1:
            length = 2
        elif br.get_bit() == 1:
            length = 3
        elif br.get_bit() == 1:
            length = 4
        elif br.get_bit() == 1:
            length = 5
        elif br.get_bit() == 1:
            length = br.read_bits(3) + 6
        else:
            length = br.read_byte() + 14

        base = len(out) - offset
        if base < 0:
            raise ChrDecompressError(
                f"backref before output start (offset={offset}, "
                f"len={len(out)})"
            )
        for i in range(length):
            out.append(out[base + i])


def decompress(payload: bytes) -> bytes:
    """Decompress one .chr/.map file payload.  Input is the entire archive
    entry as it appears on disk."""
    if len(payload) < 4:
        raise ChrDecompressError("payload too small")

    out = bytearray()
    chunk_start = 0  # pcVar4 in the dispatcher

    while True:
        if chunk_start + 3 > len(payload):
            raise ChrDecompressError(
                f"chunk header past end at {chunk_start}"
            )
        chunk_size = int.from_bytes(payload[chunk_start : chunk_start + 2], "little")
        marker_pos = chunk_start + 2
        marker = payload[marker_pos]

        if marker == 0:
            # Bit-stream decoder; terminates on its own offset=0.
            stop_pos = _decode_one_chunk(payload, marker_pos, out)
        else:
            stop_pos = _decode_lz77_chunk(payload, chunk_start, chunk_size, out)

        # Dispatcher loop check: the byte at ``local_350`` (= stop_pos)
        # decides whether another chunk follows.
        if stop_pos >= len(payload) or payload[stop_pos] == 0:
            break
        # Continue: next chunk starts at stop_pos + 1.
        chunk_start = stop_pos + 1

    return bytes(out)
