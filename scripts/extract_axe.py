#!/usr/bin/env python3
"""Extract TSR AXE geometry to OBJ with vertex colors."""

from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


def s16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


@dataclass
class AxeVertex:
    x: int
    y: int
    z: int
    r: int
    g: int
    b: int


@dataclass
class AxeFace:
    v0_raw: int
    v1_raw: int
    v2_raw: int
    v3_raw: int

    def runtime_indices(self) -> Tuple[int, int, int, int]:
        return (
            abs(s16(self.v0_raw)),
            self.v1_raw,
            self.v2_raw,
            self.v3_raw,
        )


@dataclass
class AxeChunk:
    index: int
    cull_quad: Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]
    vertices: List[AxeVertex]
    faces: List[AxeFace]


@dataclass
class AxeFile:
    chunks: List[AxeChunk]


def read_u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def parse_axe(path: Path) -> AxeFile:
    data = path.read_bytes()
    if len(data) < 8:
        raise ValueError("File is too small to contain AXE header.")

    off_scratchpad_data_count = read_u32(data, 0x00)
    chunk_count = read_u32(data, 0x04) & 0xFFFF

    chunk_table_off = 0x08
    chunk_size = 0x2C
    if chunk_table_off + chunk_count * chunk_size > len(data):
        raise ValueError("Chunk table exceeds file size.")

    raw_chunks = []
    for i in range(chunk_count):
        off = chunk_table_off + i * chunk_size
        (
            off_vertices,
            off_faces,
            off_unknown,
            p0x,
            p0y,
            p0z,
            p1x,
            p1y,
            p1z,
            p2x,
            p2y,
            p2z,
            p3x,
            p3y,
            p3z,
            color_swap_count,
            face_count,
            _unk_28,
        ) = struct.unpack_from("<III12h2hI", data, off)

        raw_chunks.append(
            {
                "index": i,
                "off_vertices": off_vertices,
                "off_faces": off_faces,
                "off_unknown": off_unknown,
                "cull_quad": ((p0x, p0y, p0z), (p1x, p1y, p1z), (p2x, p2y, p2z), (p3x, p3y, p3z)),
                "color_swap_count": max(color_swap_count, 0),
                "face_count": max(face_count, 0),
            }
        )

    all_offsets: List[int] = [len(data), off_scratchpad_data_count]
    for chunk in raw_chunks:
        all_offsets.extend([chunk["off_vertices"], chunk["off_faces"], chunk["off_unknown"]])

    chunks: List[AxeChunk] = []
    for chunk in raw_chunks:
        off_faces = chunk["off_faces"]
        face_count = chunk["face_count"]

        if off_faces + face_count * 0x0C > len(data):
            raise ValueError(f"Chunk {chunk['index']}: face block out of range.")

        faces: List[AxeFace] = []
        max_face_index = -1
        for face_idx in range(face_count):
            face_off = off_faces + face_idx * 0x0C
            v0, v1, v2, v3, _flag_offset = struct.unpack_from("<4HI", data, face_off)
            face = AxeFace(v0, v1, v2, v3)
            faces.append(face)
            i0, i1, i2, i3 = face.runtime_indices()
            max_face_index = max(max_face_index, i0, i1, i2, i3)

        inferred_vertex_count = max(max_face_index + 1, chunk["color_swap_count"])

        off_vertices = chunk["off_vertices"]
        next_offsets = [off for off in all_offsets if off > off_vertices]
        region_end = min(next_offsets) if next_offsets else len(data)
        max_possible_vertices = max((region_end - off_vertices) // 0x0C, 0)
        inferred_vertex_count = min(inferred_vertex_count, max_possible_vertices)

        vertices: List[AxeVertex] = []
        for vertex_idx in range(inferred_vertex_count):
            vertex_off = off_vertices + vertex_idx * 0x0C
            x, y, z, _pad1, r, g, b, _pad2 = struct.unpack_from("<hhhHBBBB", data, vertex_off)
            vertices.append(AxeVertex(x, y, z, r, g, b))

        for vertex_idx in range(min(chunk["color_swap_count"], len(vertices))):
            vertex = vertices[vertex_idx]
            vertex.r, vertex.b = vertex.b, vertex.r

        chunks.append(
            AxeChunk(
                index=chunk["index"],
                cull_quad=chunk["cull_quad"],
                vertices=vertices,
                faces=faces,
            )
        )

    return AxeFile(chunks=chunks)


def write_obj(axe: AxeFile, out_path: Path) -> None:
    out_lines: List[str] = []
    next_obj_index = 1

    for chunk in axe.chunks:
        out_lines.append(f"o chunk{chunk.index}")
        chunk_base = next_obj_index

        for vertex in chunk.vertices:
            out_lines.append(
                f"v {vertex.x} {vertex.y} {vertex.z} {vertex.r / 255.0:.6f} {vertex.g / 255.0:.6f} {vertex.b / 255.0:.6f}"
            )
        next_obj_index += len(chunk.vertices)

        for face in chunk.faces:
            i0, i1, i2, i3 = face.runtime_indices()
            if (
                i0 < 0
                or i1 < 0
                or i2 < 0
                or i3 < 0
                or i0 >= len(chunk.vertices)
                or i1 >= len(chunk.vertices)
                or i2 >= len(chunk.vertices)
                or i3 >= len(chunk.vertices)
            ):
                continue
            out_lines.append(f"f {chunk_base + i0} {chunk_base + i1} {chunk_base + i2} {chunk_base + i3}")

        out_lines.append(f"o quad{chunk.index}")
        quad_base = next_obj_index
        for x, y, z in chunk.cull_quad:
            out_lines.append(f"v {x} {y} {z} 1.000000 1.000000 1.000000")
        next_obj_index += 4
        out_lines.append(f"f {quad_base} {quad_base + 1} {quad_base + 2} {quad_base + 3}")

    out_path.write_text("\n".join(out_lines) + "\n", encoding="ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract TSR AXE to OBJ with vertex colors.")
    parser.add_argument("input_axe", type=Path, help="Path to input .AXE file")
    parser.add_argument(
        "output_obj",
        type=Path,
        nargs="?",
        help="Path to output .OBJ file (default: input name with .obj)",
    )
    args = parser.parse_args()

    input_path = args.input_axe
    output_path = args.output_obj if args.output_obj else input_path.with_suffix(".obj")

    axe = parse_axe(input_path)
    write_obj(axe, output_path)

    print(f"input: {input_path}")
    print(f"output: {output_path}")


if __name__ == "__main__":
    main()
