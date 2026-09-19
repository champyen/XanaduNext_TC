"""G32 image decoder.

Reverse-engineered from XANADU.exe @ 0x004e4880 (G32_DecompressBody) and
0x004e13b0 (G32_LoadImage). The on-disk layout is:

    offset 0x00  u32  width
    offset 0x04  u32  height
    offset 0x08  u32  unknown_a    (always 0x00010020 in shipped assets)
    offset 0x0c  u32  unknown_b    (always 0)
    offset 0x10  ...  compressed planar body

The body decompresses to width*height*4 bytes, laid out as four contiguous
planes in R, G, B, A order; the loader interleaves them into RGBA pixels.

Decompression is a token stream. Each token's first byte holds the opcode in
the high nibble and a count `n` in the low nibble:

    op 0   copy n+1 literal bytes  (consumes 1+size)
    op 1   copy ((n<<8)|b1)+17 literal bytes  (consumes 2+size)
    op 2   memset n+1   bytes with b1  (consumes 2)
    op 3   memset ((n<<8)|b1)+17 bytes with b2  (consumes 3)
    op 4   memset n+1   zeros          (consumes 1)
    op 5   memset ((n<<8)|b1)+33 zeros (consumes 2)
    op 6   memset n+1   0xFFs          (consumes 1)
    op 7   memset ((n<<8)|b1)+33 0xFFs (consumes 2)
    op 8-15  invalid
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


class G32Error(Exception):
    pass


@dataclass(frozen=True, slots=True)
class G32Header:
    width: int
    height: int
    unknown_a: int
    unknown_b: int

    @classmethod
    def parse(cls, blob: bytes) -> "G32Header":
        if len(blob) < 16:
            raise G32Error(f"file too small ({len(blob)} bytes)")
        w, h, a, b = struct.unpack_from("<IIII", blob, 0)
        if w == 0 or h == 0 or w > 8192 or h > 8192:
            raise G32Error(f"implausible dimensions {w}x{h}")
        return cls(w, h, a, b)


def decompress(body: bytes, expected_out: int) -> bytearray:
    """Inflate the planar body. Mirrors G32_DecompressBody at 0x004e4880."""
    out = bytearray(expected_out)
    o = 0
    i = 0
    n_in = len(body)
    while o < expected_out:
        if i >= n_in:
            raise G32Error(f"input exhausted at out={o}/{expected_out}")
        b0 = body[i]
        op = b0 >> 4
        n = b0 & 0x0F

        if op == 0:
            size = n + 1
            if i + 1 + size > n_in:
                raise G32Error("op0 overruns input")
            out[o : o + size] = body[i + 1 : i + 1 + size]
            i += 1 + size
        elif op == 1:
            if i + 2 > n_in:
                raise G32Error("op1 truncated header")
            b1 = body[i + 1]
            size = (n << 8 | b1) + 0x11
            if i + 2 + size > n_in:
                raise G32Error("op1 overruns input")
            out[o : o + size] = body[i + 2 : i + 2 + size]
            i += 2 + size
        elif op == 2:
            if i + 2 > n_in:
                raise G32Error("op2 truncated")
            size = n + 1
            value = body[i + 1]
            for k in range(size):
                out[o + k] = value
            i += 2
        elif op == 3:
            if i + 3 > n_in:
                raise G32Error("op3 truncated")
            b1 = body[i + 1]
            size = (n << 8 | b1) + 0x11
            value = body[i + 2]
            for k in range(size):
                out[o + k] = value
            i += 3
        elif op == 4:
            size = n + 1
            i += 1
        elif op == 5:
            if i + 2 > n_in:
                raise G32Error("op5 truncated")
            b1 = body[i + 1]
            size = (n << 8 | b1) + 0x21
            i += 2
        elif op == 6:
            size = n + 1
            for k in range(size):
                out[o + k] = 0xFF
            i += 1
        elif op == 7:
            if i + 2 > n_in:
                raise G32Error("op7 truncated")
            b1 = body[i + 1]
            size = (n << 8 | b1) + 0x21
            for k in range(size):
                out[o + k] = 0xFF
            i += 2
        else:
            raise G32Error(f"invalid opcode {op:#x} at offset {i}")

        if o + size > expected_out:
            raise G32Error(
                f"output overrun: would write {o + size}, expected {expected_out}"
            )
        o += size

    if o != expected_out:
        raise G32Error(f"size mismatch: wrote {o}, expected {expected_out}")
    if i != n_in:
        # Match the loader's strict check (param_2 == 0 && param_4 == 0).
        raise G32Error(f"input not fully consumed: read {i}, had {n_in}")
    return out


def decode_to_rgba(blob: bytes) -> tuple[int, int, bytes]:
    """Decode a complete G32 file → (width, height, RGBA pixel bytes)."""
    header = G32Header.parse(blob)
    body = blob[16:]
    plane_size = header.width * header.height
    planes = decompress(body, plane_size * 4)

    # Planes are laid out [R...|G...|B...|A...]. Interleave into RGBA.
    pixels = bytearray(plane_size * 4)
    r_plane = 0
    g_plane = plane_size
    b_plane = plane_size * 2
    a_plane = plane_size * 3
    for px in range(plane_size):
        o = px * 4
        pixels[o] = planes[r_plane + px]
        pixels[o + 1] = planes[g_plane + px]
        pixels[o + 2] = planes[b_plane + px]
        pixels[o + 3] = planes[a_plane + px]
    return header.width, header.height, bytes(pixels)
