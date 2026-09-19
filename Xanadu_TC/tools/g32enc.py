"""G32 planar RLE encoder (mirrors g32.py decoder ops).

Body = 4 planes (R,G,B,A), each encoded with tokens:
  op0: n+1 literals (1+n), op1: long literals ((n<<8)|b1)+17
  op2/op3: memset value short/long, op4/op5: zeros, op6/op7: 0xFF.
Greedy run coder; sizes differ from Falcom's originals (handled by .dir).
"""
import struct


def _emit_run(out, short_op, long_op, bias, run):
    """Emit a memset run. Short form covers 1..16; long form needs
    size >= bias+1 (0x12 for op1/3, 0x22 for op5/7), so 17..32 uses
    two shorts."""
    while run > 0:
        if run <= 16:
            out.append(short_op | (run - 1))
            return
        if run <= 32:
            out.append(short_op | 15)
            run -= 16
            continue
        take = min(run, 0xFFF + bias)
        L = take - bias
        out += bytes((long_op | (L >> 8), L & 0xFF))
        run -= take


def _enc_plane(data):
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        # longest run at i (value v, capped 0xFFF+0x21)
        v = data[i]
        j = i + 1
        while j < n and data[j] == v and j - i < 0xFFF + 0x21:
            j += 1
        run = j - i
        if run >= 3 or (v in (0, 0xFF) and run >= 2):
            if v == 0:
                _emit_run(out, 0x40, 0x50, 0x21, run)
            elif v == 0xFF:
                _emit_run(out, 0x60, 0x70, 0x21, run)
            else:
                # value runs carry the value byte: chunk like long forms
                # but op2 short covers 1..16 directly
                r = run
                while r > 0:
                    if r <= 16:
                        out += bytes((0x20 | (r - 1), v))
                        r = 0
                    elif r <= 32:
                        out += bytes((0x2F, v))
                        r -= 16
                    else:
                        take = min(r, 0xFFF + 0x11)
                        L = take - 0x11
                        out += bytes((0x30 | (L >> 8), L & 0xFF, v))
                        r -= take
            i = j
            continue
        # literal run until next run of >=3 (or 0/FF >= 2), cap 0xFFF+0x11
        j = i
        while j < n:
            v2 = data[j]
            k = j + 1
            while k < n and data[k] == v2 and k - j < 0xFFF + 0x21:
                k += 1
            if (k - j) >= 3 or (v2 in (0, 0xFF) and (k - j) >= 2):
                break
            j += 1
            if j - i >= 0xFFF + 0x11:
                break
        size = min(j - i, 0xFFF + 0x11)
        if size <= 16:
            out.append(0x00 | (size - 1))
        else:
            L = size - 0x11
            out += bytes((0x10 | (L >> 8), L & 0xFF))
        out += data[i:i + size]
        i += size
    return bytes(out)


def encode_rgba(w, h, rgba):
    assert len(rgba) == w * h * 4
    px = w * h
    planes = (rgba[0:px * 4:4], rgba[1:px * 4:4], rgba[2:px * 4:4],
              rgba[3:px * 4:4])
    body = b"".join(_enc_plane(bytes(p)) for p in planes)
    return struct.pack("<IIII", w, h, 0x00010020, 0) + body
