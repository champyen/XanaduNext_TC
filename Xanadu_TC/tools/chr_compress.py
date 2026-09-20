"""Falcom bit-stream (FUN_004e4260) compatible ENCODER.

Produces streams decodable by XANADU.exe's own decoder (see chr_decompress.py,
reverse-engineered from the exe). Any valid encoding works - it does not need
to match Falcom's original bitstream, only to decode to the same bytes.

Decoder refresher (_BitReader):
  * control word starts as the single byte right after the marker (8 bits),
    refills are u16LE words; bits consumed LSB-first.
  * literals / offset bytes / length bytes are read from the same cursor
    (single interleaved byte stream).
  * token: bit0 -> literal byte; bit1,bit0 -> short match (1 offset byte);
    bit1,bit1 -> 5 high bits + 1 low byte (13-bit offset; 0 = end, 1 = RLE);
    then unary length (1->2, 01->3, 001->4, 0001->5, 00001->bits3+6,
    00000->byte+14).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chr_decompress import decompress  # noqa: E402  (self-test only)


class Encoder:
    """Two-pass encoder matching decoder consumption order.

    Pass 1 records control bits and data bytes with the bit-position of
    each byte. Pass 2 groups bytes by governing unit (bits [0,8) -> unit 0
    (1 byte), [8,24)/[24,40)... -> units 1,2.. (2 bytes LE)) and emits
    unit bytes followed by their governed data bytes - exactly what the
    decoder's single cursor consumes.
    """

    def __init__(self):
        self.bits = []
        self.payload = []  # (bits_so_far, byte)

    def bit(self, b):
        self.bits.append(b & 1)

    def bits_msb(self, value, n):
        for i in range(n - 1, -1, -1):
            self.bit((value >> i) & 1)

    def byte(self, b):
        self.payload.append((len(self.bits), b & 0xFF))

    def unary(self, length):
        assert 2 <= length <= 269
        if length == 2:
            self.bit(1)
        elif length == 3:
            self.bit(0)
            self.bit(1)
        elif length == 4:
            self.bit(0)
            self.bit(0)
            self.bit(1)
        elif length == 5:
            self.bit(0)
            self.bit(0)
            self.bit(0)
            self.bit(1)
        elif length <= 13:
            for _ in range(4):
                self.bit(0)
            self.bit(1)
            self.bits_msb(length - 6, 3)
        else:
            for _ in range(5):
                self.bit(0)
            self.byte(length - 14)

    def match(self, offset, length):
        assert offset >= 1 and length >= 2
        if offset <= 255:
            self.bit(1)
            self.bit(0)
            self.byte(offset)
        else:
            assert offset <= 8191
            self.bit(1)
            self.bit(1)
            self.bits_msb((offset >> 8) & 0x1F, 5)
            self.byte(offset & 0xFF)
        self.unary(length)

    def literal(self, b):
        self.bit(0)
        self.byte(b)

    def end(self):
        # terminating 13-bit offset 0; pad final unit with zeros. The decoder
        # returns the moment it reads the offset-0 low byte, so the stream
        # ends right after it (decompress() breaks on stop_pos >= len).
        self.bit(1)
        self.bit(1)
        self.bits_msb(0, 5)
        self.byte(0)
        nbits = len(self.bits)
        # units: [0,8) [8,24) [24,40) ...
        bounds = [8]
        while bounds[-1] < nbits:
            bounds.append(bounds[-1] + 16)
        # attach payload bytes to governing units
        groups = [[] for _ in bounds]
        for bi, v in self.payload:
            if bi <= 8:
                groups[0].append(v)
            else:
                groups[1 + (bi - 9) // 16].append(v)
        out = bytearray()
        prev = 0
        for u, end in enumerate(bounds):
            word = 0
            for i in range(prev, min(end, nbits)):
                if self.bits[i]:
                    word |= 1 << (i - prev)
            out.append(word & 0xFF)
            if u > 0:
                out.append((word >> 8) & 0xFF)
            out.extend(groups[u])
            prev = end
        return bytes(out)


def compress_stream(raw):
    """Encode raw bytes to one bit-stream chunk payload (after marker byte)."""
    enc = Encoder()
    n = len(raw)
    # hash chains would be faster; font is 1.35MB with huge zero runs, so use
    # run fast-path + dict window for the rest.
    pos = 0
    window = {}
    WINDOW = 8191
    MAXLEN = 269
    data = bytes(raw)
    while pos < n:
        best_len, best_off = 0, 0
        # fast path: run of same byte
        run = 1
        while pos + run < n and data[pos + run] == data[pos] and run < MAXLEN:
            run += 1
        if run >= 2 and pos > 0:
            # backref to previous byte needs offset>=1 and base>=0; use
            # offset 1 (short) if data[pos-1] == data[pos]
            if data[pos - 1] == data[pos]:
                best_len, best_off = run, 1
        if best_len < 3:
            # general search via 3-byte hash
            if pos + 3 <= n:
                key = data[pos:pos + 3]
                cands = window.get(key, ())
                for cpos in reversed(cands):
                    off = pos - cpos
                    if off > WINDOW:
                        break
                    ln = 3
                    while ln < MAXLEN and pos + ln < n and data[cpos + ln] == data[pos + ln]:
                        ln += 1
                    if ln > best_len:
                        best_len, best_off = ln, off
                        if ln >= 32:
                            break
            if best_len >= 2 and pos - best_off < 0:
                best_len, best_off = 0, 0
        if best_len >= 2:
            enc.match(best_off, best_len)
            for k in range(best_len):
                if pos + k + 3 <= n:
                    key = data[pos + k:pos + k + 3]
                    lst = window.setdefault(key, [])
                    lst.append(pos + k)
                    if len(lst) > 64:
                        del lst[0]
            pos += best_len
        else:
            enc.literal(data[pos])
            if pos + 3 <= n:
                key = data[pos:pos + 3]
                lst = window.setdefault(key, [])
                lst.append(pos)
                if len(lst) > 64:
                    del lst[0]
            pos += 1
    return enc.end()


def compress_container(raw):
    """Single-chunk container (kept for tests only). NOTE: the game
    respects chunk framing - real font .dat files MUST use
    compress_container_multi() below. Single-chunk output decodes under
    Ell's size-ignoring model but breaks the game (size field overflow
    + premature chunk end). Kept only for the integer-overflow lesson."""
    stream = compress_stream(raw)
    chunk = b"\x00" + stream
    # chunk_size is ignored on the marker-0 decode path; store mod 64K
    return (len(chunk) & 0xFFFF).to_bytes(2, "little") + chunk


def compress_container_multi(raw, piece=65520):
    """Game-compatible multi-chunk container mirroring the stock fonts:
    ~21 chunks of ~65520 raw bytes (last smaller). Each chunk is
    [u16 size][0x00][bit-stream through its offset-0 terminator] with
    size == exact chunk length, followed by ONE flag byte: nonzero (0x01)
    between chunks (the dispatcher continues at stop_pos+1 iff the byte
    at stop_pos is nonzero), 0x00 trailer after the final chunk (stock
    files end with a zero byte the loop check consumes).
    Every non-final chunk must have a nonzero size low byte (it doubles
    as... no - the flag is separate; size low byte may be anything, but
    keep the nudge for safety); piece boundaries shift until constraints
    hold."""
    out = bytearray()
    pos = 0
    idx = 0
    while pos < len(raw):
        remaining = len(raw) - pos
        if remaining <= 65535:
            # last piece (stream will be well under 64K)
            stream = compress_stream(raw[pos:])
            size = 3 + len(stream)
            assert size < 65536, (idx, size)
            out += size.to_bytes(2, "little") + b"\x00" + stream
            out += b"\x00"  # stock-matching trailer
            break
        done = False
        for delta in (0, 512, -512, 1024, -1024, 2048, -2048):
            ln = piece + delta
            if ln <= 0 or pos + ln > len(raw):
                continue
            stream = compress_stream(raw[pos:pos + ln])
            size = 3 + len(stream)
            final = (pos + ln == len(raw))
            if size < 65536 and (final or size & 0xFF != 0):
                out += size.to_bytes(2, "little") + b"\x00" + stream
                out += b"\x01"  # inter-chunk flag (nudge keeps low byte sane)
                pos += ln
                idx += 1
                done = True
                break
        if not done:
            raise AssertionError("no viable split at chunk %d" % idx)
    return bytes(out)


def validate_container(blob, raw):
    """Game-dispatcher-strict validation: walk chunks by their size fields
    (like FUN_0044ab70): each marker-0 chunk's terminator must land exactly
    on its chunk end; a nonzero flag byte follows every non-final chunk
    (next header starts one past it); the file ends after the final chunk
    plus optional single zero trailer (stock layout). Total output == raw.
    """
    import struct as _st
    from chr_decompress import _decode_one_chunk
    pos = 0
    out = bytearray()
    n = 0
    while True:
        assert pos + 3 <= len(blob), (n, pos)
        size = _st.unpack("<H", blob[pos:pos + 2])[0]
        marker = blob[pos + 2]
        assert marker == 0, (n, marker)
        end = pos + size
        assert end <= len(blob), (n, pos, size, len(blob))
        stop = _decode_one_chunk(blob, pos + 2, out)
        assert stop == end, (n, stop, end)
        n += 1
        if end == len(blob):
            pos = end
            break
        if end == len(blob) - 1:
            assert blob[end] == 0, (n, "bad trailer")
            pos = len(blob)
            break
        assert blob[end] != 0, (n, "chain ends early")
        pos = end + 1
    assert pos == len(blob), (pos, len(blob))
    assert bytes(out) == bytes(raw), "output mismatch"
    return n


def self_test():
    for name in ("font_scn.dat", "font_sys.dat"):
        p = r"C:\Users\champ\workspace\XanaduNext_workspace\Xanadu_TC\sources\\" + name
        comp = open(p, "rb").read()
        raw = decompress(comp)
        rt = decompress(compress_container(raw))
        print(name, "raw", len(raw), "orig-comp", len(comp),
              "re-comp", len(compress_container(raw)),
              "roundtrip-ok:", rt == raw)


if __name__ == "__main__":
    self_test()
