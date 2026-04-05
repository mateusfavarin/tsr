#!/usr/bin/env python3
"""Extract TSR RAW chunks directly to flat PNG files."""

from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Pillow is required: pip install pillow") from exc


RAW_CHUNK_HEADER_SIZE = 0x0E
RAW_STREAM_END = 0xFFFFFFFF

# Character profile portrait table from game profile data.
# Each entry: (character_id, u, v, clut_offset)
CHARACTER_PROFILE_PORTRAITS: List[Tuple[int, int, int, int]] = [
    (0, 0x00, 0x00, 0x0),  # Buzz
    (1, 0x60, 0x00, 0x2),  # Alien
    (2, 0x90, 0x2B, 0x7),  # Hamm
    (3, 0x30, 0x00, 0x1),  # Woody
    (4, 0x90, 0x00, 0x4),  # RC
    (5, 0x60, 0x2B, 0x6),  # Pothead
    (6, 0x30, 0x56, 0x9),  # Slinky
    (7, 0x30, 0x2B, 0x5),  # Bopeep
    (8, 0x00, 0x2B, 0x2),  # Rex
    (9, 0x00, 0x56, 0x8),  # Rocky
    (10, 0x60, 0x56, 0x0),  # BabyFace
    (11, 0x90, 0x56, 0x4),  # Lenny
]

PROFILE_PORTRAIT_WIDTH = 0x28
PROFILE_PORTRAIT_HEIGHT = 0x28


class RawDecodeError(RuntimeError):
    """Raised when compressed RAW data cannot be decoded."""


@dataclass
class RawChunk:
    index: int
    command_id: int
    packet: bytes
    stream_offset: int
    stream_end: int
    expected_size: int
    compressed_payload_size: int
    compressed_size: int
    header_bytes: bytes


def read_be_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def read_le_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def read_le_s16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<h", data, offset)[0]


def read_le_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def signed_half_from_u16(value: int) -> int:
    signed = value & 0xFFFF
    if signed & 0x8000:
        signed -= 0x10000
    return (signed - (signed >> 31)) >> 1


def decode_4bpp_indices(packed: bytes, pixel_count: int) -> bytes:
    out = bytearray(pixel_count)
    out_pos = 0
    for byte_value in packed:
        if out_pos >= pixel_count:
            break
        out[out_pos] = byte_value & 0x0F
        out_pos += 1
        if out_pos >= pixel_count:
            break
        out[out_pos] = (byte_value >> 4) & 0x0F
        out_pos += 1
    return bytes(out)


def choose_index_mode(width: int, height: int, packed_len: int, tim_mode: int) -> Optional[int]:
    pixel_count = width * height
    if pixel_count <= 0:
        return None

    needed_4 = pixel_count // 2
    needed_8 = pixel_count
    valid: List[int] = []
    if packed_len >= needed_4:
        valid.append(0)
    if packed_len >= needed_8:
        valid.append(1)

    if tim_mode in valid:
        return tim_mode
    if len(valid) == 1:
        return valid[0]
    if len(valid) == 2:
        rem_4 = packed_len - needed_4
        rem_8 = packed_len - needed_8
        return 0 if rem_4 <= rem_8 else 1
    return None


def unswizzle_tim_pixel_data(data: bytearray, width: int, height: int, tim_mode: int) -> None:
    if width <= 0 or height <= 0:
        return

    if tim_mode == 0:
        i7 = 0
        p5 = 0
        p6 = 0
        while i7 < height:
            i4 = 0
            while i4 < width:
                if p5 + 1 >= len(data) or p6 >= len(data):
                    return
                b0 = data[p5]
                b1 = data[p5 + 1]
                p5 += 2
                i4 += 4
                data[p6] = ((b0 & 0x0F) + ((b1 & 0xFF) << 4)) & 0xFF
                p6 += 1
            p5 += width // 2
            p6 += width >> 2
            i7 += 2
    else:
        i7 = 0
        p5 = 0
        p6 = 0
        while i7 < height:
            i4 = 0
            while i4 < width:
                if p5 >= len(data) or p6 >= len(data):
                    return
                b0 = data[p5]
                p5 += 2
                i4 += 2
                data[p6] = b0
                p6 += 1
            p5 += width
            i7 += 2
            p6 += width // 2

    if tim_mode == 0:
        i7 = 0
        p5 = 0
        p1 = 0
        while i7 < height:
            i4 = 0
            while i4 < width:
                if p1 + 2 >= len(data) or p5 >= len(data):
                    return
                b0 = data[p1]
                b2 = data[p1 + 2]
                p1 += 4
                i4 += 8
                data[p5] = ((b0 & 0x0F) + ((b2 & 0xFF) << 4)) & 0xFF
                p5 += 1
            i4 = width * 3
            p5 += i4 >> 3
            p1 += i4 // 2
            i7 += 4
    else:
        i7 = 0
        p5 = 0
        p1 = 0
        row_skip = width * 3
        while i7 < height:
            i3 = 0
            while i3 < width:
                if p1 >= len(data) or p5 >= len(data):
                    return
                b0 = data[p1]
                p1 += 4
                i3 += 4
                data[p5] = b0
                p5 += 1
            p1 += row_skip
            p5 += row_skip >> 2
            i7 += 4


def _next_flag(src: bytes, src_pos: int, bitbuf: int) -> Tuple[int, int, int]:
    bit = ((bitbuf * 2) >> 8) & 1
    bitbuf = (bitbuf * 2) & 0xFF
    if bitbuf == 0:
        if src_pos >= len(src):
            raise RawDecodeError("Compressed stream ended while refilling bit buffer.")
        refill = src[src_pos]
        src_pos += 1
        bitbuf = refill * 2 + bit
        bit = (bitbuf >> 8) & 1
    return src_pos, bitbuf, bit


def decompress_raw_chunk(chunk: bytes) -> bytes:
    if len(chunk) < RAW_CHUNK_HEADER_SIZE + 1:
        raise RawDecodeError("Chunk too small for RAW header.")

    expected_size = read_be_u32(chunk, 0x00)
    src3 = 0x0F
    bitbuf = ((chunk[0x0E] * 2 + 1) * 2) & 0xFFFFFFFF
    out = bytearray()

    while True:
        while True:
            bit11 = ((bitbuf * 2) >> 8) & 1
            src4 = src3
            u6 = (bitbuf * 2) & 0xFFFFFFFF
            if bit11 != 0:
                break

            src4 = src3 + 1
            if src3 >= len(chunk):
                raise RawDecodeError("Literal copy read past compressed chunk.")
            out.append(chunk[src3])

            bitbuf = (bitbuf * 4) & 0xFFFFFFFF
            bit11 = (bitbuf >> 8) & 1
            u6 = bitbuf
            if bit11 != 0:
                break

            if src4 >= len(chunk):
                raise RawDecodeError("Literal copy read past compressed chunk.")
            src3 = src4 + 1
            out.append(chunk[src4])

        bitbuf = u6 & 0xFF
        if bitbuf == 0:
            if src4 >= len(chunk):
                raise RawDecodeError("Bit-buffer refill read past compressed chunk.")
            refill = chunk[src4]
            src4 += 1
            bitbuf = refill * 2 + bit11
            if ((bitbuf >> 8) & 1) == 0:
                if src4 >= len(chunk):
                    raise RawDecodeError("Literal copy read past compressed chunk.")
                src3 = src4 + 1
                out.append(chunk[src4])
                continue

        u6 = 2
        u11 = 0
        direct_backref = False

        src4, bitbuf, u12 = _next_flag(chunk, src4, bitbuf)

        if u12 == 0:
            src3 = src4
            src3, bitbuf, u12 = _next_flag(chunk, src3, bitbuf)
            u6 = u12 + 4
            src3, bitbuf, u10 = _next_flag(chunk, src3, bitbuf)
            if u10 != 0:
                src3, bitbuf, u6 = _next_flag(chunk, src3, bitbuf)
                u6 = (u12 + 3) * 2 + u6
                if u6 == 9:
                    for _ in range(4):
                        src3, bitbuf, u6 = _next_flag(chunk, src3, bitbuf)
                        u11 = u11 * 2 + u6
                    copy_dwords = u11 + 3
                    needed = copy_dwords * 4
                    if src3 + needed > len(chunk):
                        raise RawDecodeError("RLE block read past compressed chunk.")
                    out.extend(chunk[src3 : src3 + needed])
                    src3 += needed
                    if len(out) < expected_size:
                        continue
                    if len(out) == expected_size:
                        return bytes(out)
                    raise RawDecodeError("Decoded size exceeded expected size.")
                src4 = src3
        else:
            src4, bitbuf, u12 = _next_flag(chunk, src4, bitbuf)
            if u12 == 0:
                direct_backref = True
            else:
                u6 = 3
                src4, bitbuf, u12 = _next_flag(chunk, src4, bitbuf)
                src3 = src4
                if u12 != 0:
                    if src4 >= len(chunk):
                        raise RawDecodeError("Length extension read past compressed chunk.")
                    src3 = src4 + 1
                    u6 = chunk[src4] + 8
                    if chunk[src4] != 0:
                        src4 = src3
                    else:
                        src3, bitbuf, u6 = _next_flag(chunk, src3, bitbuf)
                        if u6 == 0:
                            if len(out) != expected_size:
                                raise RawDecodeError(
                                    f"Chunk ended with decoded size {len(out)}, expected {expected_size}."
                                )
                            return bytes(out)
                        continue

        if not direct_backref:
            src4, bitbuf, u12 = _next_flag(chunk, src3, bitbuf)
            if u12 != 0:
                src4, bitbuf, u11 = _next_flag(chunk, src4, bitbuf)
                src4, bitbuf, u12 = _next_flag(chunk, src4, bitbuf)
                if u12 == 0:
                    if u11 == 0:
                        u11 = 1
                        src4, bitbuf, u12 = _next_flag(chunk, src4, bitbuf)
                        u11 = u11 * 2 + u12
                else:
                    src4, bitbuf, u12 = _next_flag(chunk, src4, bitbuf)
                    u11 = (u11 * 2 + u12) | 4
                    src4, bitbuf, u12 = _next_flag(chunk, src4, bitbuf)
                    if u12 == 0:
                        src4, bitbuf, u12 = _next_flag(chunk, src4, bitbuf)
                        u11 = u11 * 2 + u12
                u11 <<= 8

        if src4 >= len(chunk):
            raise RawDecodeError("Back-reference distance read past compressed chunk.")

        distance_low = chunk[src4]
        src3 = src4 + 1
        distance = distance_low | u11

        copy_src = len(out) - distance
        src_word = copy_src - 1

        if copy_src < 0:
            raise RawDecodeError("Back-reference before start of output buffer.")

        if (u6 & 1) != 0:
            if copy_src - 1 < 0:
                raise RawDecodeError("Odd-length back-reference underflow.")
            out.append(out[copy_src - 1])
            src_word = copy_src

        repeats = (u6 >> 1) - 1
        if repeats < -1:
            raise RawDecodeError("Invalid repeat count in compressed stream.")

        if distance == 0:
            if src_word < 0:
                raise RawDecodeError("Zero-distance back-reference underflow.")
            repeated_byte = out[src_word]
            for _ in range(repeats + 1):
                out.append(repeated_byte)
                out.append(repeated_byte)
        else:
            for _ in range(repeats + 1):
                if src_word + 1 >= len(out):
                    raise RawDecodeError("Back-reference read beyond output buffer.")
                out.append(out[src_word])
                out.append(out[src_word + 1])
                src_word += 2

        if len(out) > expected_size:
            raise RawDecodeError(f"Decoded size exceeded expected size ({expected_size}).")


def iterate_chunks(raw_data: bytes) -> List[RawChunk]:
    chunks: List[RawChunk] = []
    offset = 0
    index = 0

    while offset + 4 <= len(raw_data):
        if read_be_u32(raw_data, offset) == RAW_STREAM_END:
            break

        if offset + RAW_CHUNK_HEADER_SIZE > len(raw_data):
            raise RawDecodeError(f"Chunk header at 0x{offset:X} is truncated.")

        decompressed_size = read_be_u32(raw_data, offset + 0x00)
        compressed_payload_size = read_be_u32(raw_data, offset + 0x04)
        compressed_size = compressed_payload_size + RAW_CHUNK_HEADER_SIZE
        chunk_end = offset + compressed_size
        if chunk_end > len(raw_data):
            raise RawDecodeError(f"Chunk {index} at 0x{offset:X} exceeds file size.")

        compressed_chunk = raw_data[offset:chunk_end]
        header_bytes = compressed_chunk[:RAW_CHUNK_HEADER_SIZE]
        packet = decompress_raw_chunk(compressed_chunk)
        if len(packet) != decompressed_size:
            raise RawDecodeError(
                f"Chunk {index}: decoded {len(packet)} bytes, expected {decompressed_size} bytes."
            )
        if len(packet) < 4:
            raise RawDecodeError(f"Chunk {index}: decoded packet too small for command ID.")
        command_id = read_le_u32(packet, 0x00)

        chunks.append(
            RawChunk(
                index=index,
                command_id=command_id,
                packet=packet,
                stream_offset=offset,
                stream_end=chunk_end,
                expected_size=decompressed_size,
                compressed_payload_size=compressed_payload_size,
                compressed_size=compressed_size,
                header_bytes=header_bytes,
            )
        )
        offset = chunk_end
        index += 1

    return chunks


def convert_clut_preview_palette(palette_rgb24: bytes) -> List[Tuple[int, int, int, int]]:
    out: List[Tuple[int, int, int, int]] = []
    for i in range(256):
        base = i * 3
        if base + 2 < len(palette_rgb24):
            r = palette_rgb24[base + 0]
            g = palette_rgb24[base + 1]
            b = palette_rgb24[base + 2]
        else:
            r = g = b = 0

        if (r == 0) and (g >= 0xFB) and (b == 0):
            out.append((0, 0, 0, 0))
            continue

        color = (r >> 3) + ((g >> 3) << 5) + ((b >> 3) << 10)
        if color == 0:
            color = 1
        color |= 0x8000

        r5 = color & 0x1F
        g5 = (color >> 5) & 0x1F
        b5 = (color >> 10) & 0x1F
        out.append((r5 * 255 // 31, g5 * 255 // 31, b5 * 255 // 31, 255))
    return out


def save_decoded_indexed_png(
    path: Path,
    width: int,
    height: int,
    indices: bytes,
    palette_rgba: List[Tuple[int, int, int, int]],
    mode: int,
    clut_slice: int = 0,
    clut_regions: Optional[List[Tuple[int, int, int, int, int]]] = None,
    fixed_clut_cell: Optional[int] = None,
) -> int:
    pixels: List[Tuple[int, int, int, int]] = []
    if mode == 0:
        for y in range(height):
            row = y * width
            for x in range(width):
                idx = indices[row + x] & 0x0F
                clut_cell = -1
                if fixed_clut_cell is not None:
                    clut_cell = fixed_clut_cell
                elif clut_regions is not None:
                    for region_x, region_y, region_w, region_h, region_clut in clut_regions:
                        if (
                            x >= region_x
                            and x < region_x + region_w
                            and y >= region_y
                            and y < region_y + region_h
                        ):
                            clut_cell = region_clut
                            break
                if clut_cell < 0:
                    clut_cell = (((y >> 6) & 0x03) << 2) + ((x >> 6) & 0x03)
                palette_index = (clut_cell << 4) + idx
                if palette_index >= len(palette_rgba):
                    palette_index = idx
                pixels.append(palette_rgba[palette_index])
    else:
        for idx in indices:
            pixels.append(palette_rgba[idx & 0xFF])

    image = Image.new("RGBA", (width, height))
    image.putdata(pixels)
    image.save(path)
    return clut_slice


def save_rgb555_png(path: Path, width: int, height: int, data_16bpp: bytes) -> None:
    pixels: List[Tuple[int, int, int, int]] = []
    for i in range(0, width * height * 2, 2):
        value = data_16bpp[i] | (data_16bpp[i + 1] << 8)
        r = (value & 0x1F) * 255 // 31
        g = ((value >> 5) & 0x1F) * 255 // 31
        b = ((value >> 10) & 0x1F) * 255 // 31
        a = 255 if (value & 0x8000) else 0
        pixels.append((r, g, b, a))
    image = Image.new("RGBA", (width, height))
    image.putdata(pixels)
    image.save(path)


def vlog(enabled: bool, message: str) -> None:
    if enabled:
        print(message)


def base_name(chunk: RawChunk) -> str:
    return f"{chunk.index:04d}_0x{chunk.command_id:04X}"


def extract_indexed_packet(
    packet: bytes,
    command_id: int,
    output_png: Path,
    header_size: int,
    width_off: int,
    height_off: int,
    palette_len_off: int,
    flags_off: int,
) -> Tuple[bool, str]:
    if len(packet) < header_size:
        return False, "packet too small"

    width = read_le_u16(packet, width_off)
    height = read_le_s16(packet, height_off)
    palette_len = read_le_u16(packet, palette_len_off)
    tim_flags = read_le_u16(packet, flags_off)
    if width <= 0 or height <= 0:
        return False, f"invalid dimensions {width}x{height}"

    palette_start = header_size
    palette_end = palette_start + palette_len
    if palette_end > len(packet):
        return False, "palette exceeds packet"

    pixel_offset = header_size + signed_half_from_u16(palette_len) * 2
    if pixel_offset < 0 or pixel_offset > len(packet):
        return False, "pixel offset out of range"

    packed_pixels = packet[pixel_offset:]
    tim_mode = tim_flags & 0x03
    selected_mode = choose_index_mode(width, height, len(packed_pixels), tim_mode)
    if selected_mode is None:
        return False, f"cannot infer mode (tim_mode={tim_mode}, packed={len(packed_pixels)})"

    source = bytearray(packed_pixels)
    if command_id < 4:
        unswizzle_tim_pixel_data(source, width, height, tim_flags)

    expected_pixels = width * height
    if selected_mode == 0:
        packed_needed = expected_pixels // 2
        indices = decode_4bpp_indices(bytes(source[:packed_needed]), expected_pixels)
    else:
        indices = bytes(source[:expected_pixels])
        if len(indices) < expected_pixels:
            indices += bytes(expected_pixels - len(indices))

    max_index = max(indices) if indices else 0

    runtime_palette = packet[palette_start : palette_start + 0x300]
    if len(runtime_palette) < 0x300:
        runtime_palette += bytes(0x300 - len(runtime_palette))
    preview_palette = convert_clut_preview_palette(runtime_palette)
    clut_slice = 0
    clut_regions: Optional[List[Tuple[int, int, int, int, int]]] = None
    clut_mode = "uv_xy"
    if selected_mode == 0 and command_id == 0x000A:
        clut_regions = []
        for _, u, v, clut in CHARACTER_PROFILE_PORTRAITS:
            clut_regions.append((u, v, PROFILE_PORTRAIT_WIDTH, PROFILE_PORTRAIT_HEIGHT, clut))
        clut_mode = "profile_table+uv_xy_fallback"
    save_decoded_indexed_png(
        output_png,
        width,
        height,
        indices,
        preview_palette,
        selected_mode,
        clut_slice=clut_slice,
        clut_regions=clut_regions,
    )
    bpp = 4 if selected_mode == 0 else 8
    clut_colors = 16 if selected_mode == 0 else 256
    summary = (
        f"indexed {width}x{height} tim_flags=0x{tim_flags:04X} "
        f"tim_mode={tim_mode} inferred_mode={selected_mode} max_index={max_index} "
        f"palette_bytes={palette_len} packed_bytes={len(packed_pixels)} "
        f"bpp={bpp} clut_colors={clut_colors}"
    )
    if command_id < 4:
        summary += " unswizzled=1"
    if selected_mode == 0:
        summary += f" clut_mode={clut_mode}"
    return True, summary


def extract_rgb555_packet(packet: bytes, output_png: Path) -> Tuple[bool, str]:
    if len(packet) < 0x10:
        return False, "packet too small"
    width = read_le_u16(packet, 0x04)
    height = read_le_u16(packet, 0x08)
    if width <= 0 or height <= 0:
        return False, f"invalid dimensions {width}x{height}"
    payload_len = width * height * 2
    payload_start = 0x10
    payload_end = payload_start + payload_len
    if payload_end > len(packet):
        return False, "pixel payload exceeds packet"
    save_rgb555_png(output_png, width, height, packet[payload_start:payload_end])
    return True, f"rgb555 {width}x{height} bpp=16 clut_colors=0"


def extract_framebank(
    packet: bytes,
    output_dir: Path,
    basename: str,
    is_4bpp: bool,
    palette_by_slot: dict[int, List[Tuple[int, int, int, int]]],
) -> Tuple[int, str]:
    if len(packet) < 0x0C:
        return 0, "packet too small"

    bank_id = read_le_u16(packet, 0x04)
    payload = packet[0x08:]
    if len(payload) < 4:
        return 0, "payload too small"

    width = read_le_u16(payload, 0x00)
    height = read_le_s16(payload, 0x02)
    if width <= 0 or height <= 0:
        return 0, f"invalid dimensions {width}x{height}"

    pixel_count = width * height
    extracted = 0

    if is_4bpp:
        frame_stride = pixel_count // 2
        if frame_stride <= 0:
            return 0, "invalid 4bpp frame stride"
        frame_data = payload[4:]
        frame_count = len(frame_data) // frame_stride
        palette_source = f"bank_id={bank_id}"
        palette_rgba = palette_by_slot.get(bank_id)
        if palette_rgba is None:
            debug_palette = []
            for i in range(16):
                debug_palette.extend([(i * 73) & 0xFF, (i * 151) & 0xFF, (i * 43) & 0xFF])
            debug_palette_rgba: List[Tuple[int, int, int, int]] = []
            for i in range(0, len(debug_palette), 3):
                debug_palette_rgba.append((debug_palette[i], debug_palette[i + 1], debug_palette[i + 2], 255))
            while len(debug_palette_rgba) < 256:
                debug_palette_rgba.append((0, 0, 0, 0))
            palette_rgba = debug_palette_rgba
            palette_source += "(synthetic)"
        else:
            palette_source += "(texture_slot_palette)"

        for frame_index in range(frame_count):
            start = frame_index * frame_stride
            packed = frame_data[start : start + frame_stride]
            indices = decode_4bpp_indices(packed, pixel_count)
            save_decoded_indexed_png(
                output_dir / f"{basename}_{frame_index:03d}.png",
                width,
                height,
                indices,
                palette_rgba,
                0,
                clut_slice=0,
                fixed_clut_cell=0,
            )
            extracted += 1
        return (
            extracted,
            f"framebank4 id={bank_id} {width}x{height} frames={frame_count} "
            f"bpp=4 clut_colors=16 clut_mode=fixed0 {palette_source}",
        )

    if len(payload) < 8:
        return 0, "payload too small for 8bpp framebank"
    palette_entry_count = read_le_s16(payload, 0x06)
    if palette_entry_count < 0:
        return 0, "negative palette entry count"
    palette_len = palette_entry_count * 3
    palette_start = 8
    palette_end = palette_start + palette_len
    if palette_end > len(payload):
        return 0, "palette exceeds payload"
    palette_preview = convert_clut_preview_palette(payload[palette_start:palette_end])
    frame_stride = pixel_count
    frame_data = payload[palette_end:]
    frame_count = len(frame_data) // frame_stride if frame_stride > 0 else 0
    for frame_index in range(frame_count):
        start = frame_index * frame_stride
        frame = frame_data[start : start + frame_stride]
        save_decoded_indexed_png(
            output_dir / f"{basename}_{frame_index:03d}.png",
            width,
            height,
            frame,
            palette_preview,
            1,
        )
        extracted += 1
    return (
        extracted,
        f"framebank8 id={bank_id} {width}x{height} frames={frame_count} "
        f"palette_entries={palette_entry_count} bpp=8 clut_colors=256",
    )


def extract_palette_preview(packet: bytes, header_size: int, palette_len_off: int) -> Optional[List[Tuple[int, int, int, int]]]:
    if len(packet) < header_size:
        return None
    palette_len = read_le_u16(packet, palette_len_off)
    palette_start = header_size
    palette_end = palette_start + palette_len
    if palette_end > len(packet):
        return None
    runtime_palette = packet[palette_start : palette_start + 0x300]
    if len(runtime_palette) < 0x300:
        runtime_palette += bytes(0x300 - len(runtime_palette))
    return convert_clut_preview_palette(runtime_palette)


def extract_raw_images(input_path: Path, output_dir: Path, verbose: bool) -> Tuple[int, int]:
    raw_data = input_path.read_bytes()
    chunks = iterate_chunks(raw_data)
    output_dir.mkdir(parents=True, exist_ok=True)

    images = 0
    skipped = 0
    palette_by_slot: dict[int, List[Tuple[int, int, int, int]]] = {}
    for chunk in chunks:
        packet = chunk.packet
        cmd = chunk.command_id
        name = base_name(chunk)
        out_png = output_dir / f"{name}.png"
        prefix = f"[{chunk.index:04d}] cmd=0x{cmd:04X}"

        ok = False
        detail = "unclassified"
        if cmd < 0x20:
            ok, detail = extract_indexed_packet(packet, cmd, out_png, 0x0C, 0x04, 0x06, 0x08, 0x0A)
            palette = extract_palette_preview(packet, 0x0C, 0x08)
            if palette is not None:
                palette_by_slot[cmd] = palette
        elif cmd == 0x24:
            ok, detail = extract_indexed_packet(packet, cmd, out_png, 0x10, 0x08, 0x0A, 0x0C, 0x0E)
        elif 0x58 <= cmd < 0x60:
            ok, detail = extract_indexed_packet(packet, cmd, out_png, 0x0C, 0x04, 0x06, 0x08, 0x0A)
        elif cmd in {0x20, 0x25} or 0x28 <= cmd < 0x30:
            ok, detail = extract_rgb555_packet(packet, out_png)
        elif cmd == 0x22:
            count, detail = extract_framebank(
                packet,
                output_dir,
                name,
                is_4bpp=True,
                palette_by_slot=palette_by_slot,
            )
            images += count
            ok = count > 0
        elif cmd == 0x26:
            count, detail = extract_framebank(
                packet,
                output_dir,
                name,
                is_4bpp=False,
                palette_by_slot=palette_by_slot,
            )
            images += count
            ok = count > 0

        if ok and cmd not in {0x22, 0x26}:
            images += 1
            vlog(verbose, f"{prefix} -> {out_png.name} | {detail}")
        elif ok:
            vlog(verbose, f"{prefix} -> frames | {detail}")
        if not ok:
            skipped += 1
            vlog(verbose, f"{prefix} -> skipped ({detail})")

    return images, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract TSR RAW to flat PNG files.")
    parser.add_argument("input_raw", type=Path, help="Path to input .RAW file")
    parser.add_argument(
        "output_dir",
        type=Path,
        nargs="?",
        help="Output folder (default: <input_stem>)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-chunk decoding/extraction information.",
    )
    args = parser.parse_args()

    input_path = args.input_raw
    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    output_dir = args.output_dir if args.output_dir else input_path.with_suffix("")
    images, skipped = extract_raw_images(input_path, output_dir, verbose=args.verbose)

    print(f"input : {input_path}")
    print(f"output: {output_dir}")
    print(f"images: {images}")
    print(f"skipped chunks: {skipped}")


if __name__ == "__main__":
    main()
