#!/usr/bin/env python3
"""Extract TSR DAT meshes to OBJ (and optional RAW textures to MTL)."""

from __future__ import annotations

import argparse
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import extract_raw as raw_extractor


OBJ_SCALE = 4096.0
LONG_QUAD_OPCODES = {0x00, 0x02, 0x04, 0x06, 0x08, 0x0A, 0x0C, 0x0E}
LONG_TRI_OPCODES = {0x01, 0x03, 0x05, 0x07, 0x09, 0x0B, 0x0D, 0x0F}
SHORT_QUAD_OPCODES = {0x10, 0x12, 0x14, 0x16}
SHORT_TRI_OPCODES = {0x11, 0x13, 0x15, 0x17}
TEXTURED_LONG_OPCODES = LONG_QUAD_OPCODES | LONG_TRI_OPCODES


@dataclass(frozen=True)
class DatGeometryHeader:
    offset: int
    x: int
    y: int
    z: int
    cull_radius: int
    type: int
    section_id: int
    geometry_offset: int


@dataclass(frozen=True)
class DatObjectRef:
    offset: int
    x: int
    y: int
    z: int
    cull_radius: int
    type: int
    flags: int
    transform_offset: int


@dataclass(frozen=True)
class DatObjectTransform:
    offset: int
    pos: Tuple[int, int, int]
    rot: Tuple[int, int, int]
    scale: Tuple[int, int, int]
    flags_0x18: int
    mesh_offset: int


@dataclass(frozen=True)
class MeshVertex:
    x: int
    y: int
    z: int
    color_555: int


@dataclass(frozen=True)
class MeshFace:
    indices: Tuple[int, ...]
    uv: Optional[Tuple[Tuple[int, int], ...]]
    texture_slot: Optional[int]


@dataclass(frozen=True)
class MeshData:
    offset: int
    vertices: List[MeshVertex]
    faces: List[MeshFace]


@dataclass(frozen=True)
class ObjPart:
    name: str
    vertices: List[Tuple[float, float, float, float, float, float]]
    faces: List[MeshFace]


@dataclass(frozen=True)
class RawTextureInfo:
    slot: int
    path: Path
    width: int
    height: int


@dataclass(frozen=True)
class DatFile:
    section_by_type: Dict[int, int]
    primary_geometry_headers: List[DatGeometryHeader]
    secondary_geometry_headers: List[DatGeometryHeader]
    object_refs: List[DatObjectRef]


@dataclass(frozen=True)
class ExtractionStats:
    first_geometry_header_meshes: int
    second_geometry_header_meshes: int
    object_meshes: int
    mesh_streams: int
    unsupported_mesh_streams: int


def read_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def read_s16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<h", data, offset)[0]


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def read_s32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def align_ok(data: bytes, offset: int, size: int = 1) -> bool:
    return 0 <= offset <= len(data) - size


def build_rotation_matrix(rot: Tuple[int, int, int]) -> List[List[float]]:
    x_angle, y_angle, z_angle = rot
    x = (x_angle & 0x0FFF) * (2.0 * 3.141592653589793 / 4096.0)
    y = (y_angle & 0x0FFF) * (2.0 * 3.141592653589793 / 4096.0)
    z = (z_angle & 0x0FFF) * (2.0 * 3.141592653589793 / 4096.0)

    sin_x = math.sin(x)
    cos_x = math.cos(x)
    sin_y = math.sin(y)
    cos_y = math.cos(y)
    sin_z = math.sin(z)
    cos_z = math.cos(z)

    sinx_siny = sin_x * sin_y
    cosx_siny = cos_x * sin_y

    return [
        [cos_z * cos_y, -sin_z * cos_y, sin_y],
        [cos_z * sinx_siny + cos_x * sin_z, cos_x * cos_z - sin_z * sinx_siny, -sin_x * cos_y],
        [sin_x * sin_z - cos_z * cosx_siny, sin_x * cos_z + sin_z * cosx_siny, cos_x * cos_y],
    ]


def apply_axis_scale(matrix: List[List[float]], scale: Tuple[int, int, int]) -> List[List[float]]:
    scale_x = scale[0] / 4096.0
    scale_y = scale[1] / 4096.0
    scale_z = scale[2] / 4096.0
    return [
        [matrix[0][0] * scale_x, matrix[0][1] * scale_y, matrix[0][2] * scale_z],
        [matrix[1][0] * scale_x, matrix[1][1] * scale_y, matrix[1][2] * scale_z],
        [matrix[2][0] * scale_x, matrix[2][1] * scale_y, matrix[2][2] * scale_z],
    ]


def psx_color_555_to_rgb(value: int) -> Tuple[float, float, float]:
    r5 = value & 0x1F
    g5 = (value >> 5) & 0x1F
    b5 = (value >> 10) & 0x1F
    return (r5 / 31.0, g5 / 31.0, b5 / 31.0)


def transform_vertices(
    local_vertices: Sequence[MeshVertex],
    pos: Tuple[int, int, int],
    rot: Tuple[int, int, int],
    scale: Tuple[int, int, int],
) -> List[Tuple[float, float, float, float, float, float]]:
    matrix = apply_axis_scale(build_rotation_matrix(rot), scale)
    out: List[Tuple[float, float, float, float, float, float]] = []

    for vertex in local_vertices:
        local_x, local_y, local_z = vertex.x, vertex.y, vertex.z
        world_x = pos[0] + matrix[0][0] * local_x + matrix[0][1] * local_y + matrix[0][2] * local_z
        world_y = pos[1] + matrix[1][0] * local_x + matrix[1][1] * local_y + matrix[1][2] * local_z
        world_z = pos[2] + matrix[2][0] * local_x + matrix[2][1] * local_y + matrix[2][2] * local_z
        r, g, b = psx_color_555_to_rgb(vertex.color_555)
        out.append((world_x / OBJ_SCALE, world_y / OBJ_SCALE, world_z / OBJ_SCALE, r, g, b))

    return out


def parse_sections(data: bytes) -> Tuple[Dict[int, int], int]:
    if len(data) < 4:
        raise ValueError("File is too small to contain a DAT header.")

    section_count = read_u32(data, 0x00)
    cursor = 0x04
    section_by_type: Dict[int, int] = {}
    next_upper_section_type = 0x41

    for _ in range(section_count):
        if not align_ok(data, cursor, 4):
            raise ValueError("DAT section header exceeds file size.")

        entry_count = read_u16(data, cursor)
        section_type = read_s16(data, cursor + 2)

        if section_type < 0:
            section_by_type[-section_type] = cursor
            size = (((entry_count * 3) + 1) // 2) * 4 + 0x10
        elif section_type == 0x40:
            section_by_type[0x40 + len([key for key in section_by_type if key >= 0x40])] = cursor
            size = entry_count * 0x0C + 0x04
        elif section_type < 0x41:
            section_by_type[section_type] = cursor
            size = entry_count * (0x10 if section_type == 0x3F else 0x0C) + 0x04
        else:
            section_by_type[next_upper_section_type] = cursor
            next_upper_section_type += 1
            size = entry_count * 0x0C + 0x04

        if not align_ok(data, cursor, size):
            raise ValueError(f"DAT section at 0x{cursor:X} exceeds file size.")

        cursor += size

    return section_by_type, cursor


def parse_geometry_headers(data: bytes, offset: int) -> Tuple[List[DatGeometryHeader], int]:
    headers: List[DatGeometryHeader] = []
    cursor = offset

    while True:
        if not align_ok(data, cursor, 0x14):
            raise ValueError("Entity header exceeds file size.")

        header = DatGeometryHeader(
            offset=cursor,
            x=read_s32(data, cursor + 0x00),
            y=read_s32(data, cursor + 0x04),
            z=read_s32(data, cursor + 0x08),
            cull_radius=read_u16(data, cursor + 0x0C),
            type=data[cursor + 0x0E],
            section_id=data[cursor + 0x0F],
            geometry_offset=read_u32(data, cursor + 0x10),
        )
        cursor += 0x14

        if header.type == 0:
            break

        headers.append(header)

    return headers, cursor


def parse_dat(path: Path) -> DatFile:
    data = path.read_bytes()
    section_by_type, cursor = parse_sections(data)

    if not align_ok(data, cursor, 4):
        raise ValueError("Routing table header exceeds file size.")

    routing_table_count = read_u32(data, cursor)
    cursor += 4
    routing_table_size = routing_table_count * 0x80
    if not align_ok(data, cursor, routing_table_size):
        raise ValueError("Routing table exceeds file size.")
    cursor += routing_table_size

    primary_geometry_headers, cursor = parse_geometry_headers(data, cursor)

    if not align_ok(data, cursor, 4):
        raise ValueError("Object table header exceeds file size.")

    object_count = read_s32(data, cursor)
    object_refs: List[DatObjectRef] = []
    object_table_offset = cursor

    if object_count >= 0:
        table_size = 4 + (object_count + 1) * 4
        if not align_ok(data, object_table_offset, table_size):
            raise ValueError("Object table exceeds file size.")

        for index in range(object_count + 1):
            object_offset = read_u32(data, object_table_offset + 4 + index * 4)
            if object_offset == 0:
                continue
            if not align_ok(data, object_offset, 0x14):
                continue

            object_refs.append(
                DatObjectRef(
                    offset=object_offset,
                    x=read_s32(data, object_offset + 0x00),
                    y=read_s32(data, object_offset + 0x04),
                    z=read_s32(data, object_offset + 0x08),
                    cull_radius=read_u16(data, object_offset + 0x0C),
                    type=data[object_offset + 0x0E],
                    flags=data[object_offset + 0x0F],
                    transform_offset=read_u32(data, object_offset + 0x10),
                )
            )

        cursor = object_table_offset + table_size
    else:
        cursor = object_table_offset + 4

    secondary_geometry_headers, _ = parse_geometry_headers(data, cursor)

    return DatFile(
        section_by_type=section_by_type,
        primary_geometry_headers=primary_geometry_headers,
        secondary_geometry_headers=secondary_geometry_headers,
        object_refs=object_refs,
    )


def parse_dat_object_transform(data: bytes, offset: int) -> Optional[DatObjectTransform]:
    if offset == 0 or not align_ok(data, offset, 0x20):
        return None

    return DatObjectTransform(
        offset=offset,
        pos=(read_s32(data, offset + 0x00), read_s32(data, offset + 0x04), read_s32(data, offset + 0x08)),
        rot=(read_s16(data, offset + 0x0C), read_s16(data, offset + 0x0E), read_s16(data, offset + 0x10)),
        scale=(read_s16(data, offset + 0x12), read_s16(data, offset + 0x14), read_s16(data, offset + 0x16)),
        flags_0x18=read_u32(data, offset + 0x18),
        mesh_offset=read_u32(data, offset + 0x1C),
    )


def parse_geometry_instance(data: bytes, header: DatGeometryHeader) -> Optional[Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], int]]:
    offset = header.geometry_offset
    if offset == 0 or not align_ok(data, offset, 0x18):
        return None

    pos = (read_s32(data, offset + 0x00), read_s32(data, offset + 0x04), read_s32(data, offset + 0x08))
    rot = (read_s16(data, offset + 0x0C), read_s16(data, offset + 0x0E), read_s16(data, offset + 0x10))

    if (header.type & 0x08) == 0:
        scale = (0x1000, 0x1000, 0x1000)
        mesh_offset = read_u32(data, offset + 0x14)
    else:
        if not align_ok(data, offset, 0x20):
            return None
        scale = (read_s16(data, offset + 0x12), read_s16(data, offset + 0x14), read_s16(data, offset + 0x16))
        mesh_offset = read_u32(data, offset + 0x1C)

    return pos, rot, scale, mesh_offset


def parse_mesh_stream(data: bytes, offset: int) -> Optional[MeshData]:
    if offset == 0 or not align_ok(data, offset, 4):
        return None

    vertex_count = read_s32(data, offset)
    if vertex_count <= 0:
        return None

    vertex_block_size = vertex_count * 8
    vertex_offset = offset + 4
    command_offset = vertex_offset + vertex_block_size
    if not align_ok(data, vertex_offset, vertex_block_size):
        return None

    vertices: List[MeshVertex] = []
    for vertex_index in range(vertex_count):
        local_offset = vertex_offset + vertex_index * 8
        vertices.append(
            MeshVertex(
                x=read_s16(data, local_offset + 0x00),
                y=read_s16(data, local_offset + 0x02),
                z=read_s16(data, local_offset + 0x04),
                color_555=read_u16(data, local_offset + 0x06),
            )
        )

    faces: List[MeshFace] = []
    cursor = command_offset
    saw_terminator = False
    current_texture_slot: Optional[int] = None

    while align_ok(data, cursor, 4):
        opcode = read_u16(data, cursor + 0x00)
        opcode_signed = read_s16(data, cursor + 0x00)
        command = read_u16(data, cursor + 0x02)

        if opcode == 0xFFFF:
            saw_terminator = True
            break

        primitive_count = command & 0x03FF
        command_mode = (command >> 12) & 0x03
        if primitive_count == 0x03FF and command_mode != 0:
            saw_terminator = True
            break

        family = opcode & 0x1F
        if family in LONG_QUAD_OPCODES:
            vertices_per_face = 4
            primitive_stride = 12
        elif family in LONG_TRI_OPCODES:
            vertices_per_face = 3
            primitive_stride = 12
        elif family in SHORT_QUAD_OPCODES:
            vertices_per_face = 4
            primitive_stride = 4
        elif family in SHORT_TRI_OPCODES:
            vertices_per_face = 3
            primitive_stride = 4
        else:
            return None

        payload_offset = cursor + 4
        payload_size = primitive_count * primitive_stride
        if not align_ok(data, payload_offset, payload_size):
            return None

        if opcode_signed >= 0:
            # Matches game decode: slot comes from opcode bits 8..12.
            current_texture_slot = (opcode >> 8) & 0x1F

        texture_slot = current_texture_slot if family in TEXTURED_LONG_OPCODES else None
        for primitive_index in range(primitive_count):
            primitive_base = payload_offset + primitive_index * primitive_stride
            packed = read_u32(data, primitive_base + 0x00)
            indices = (
                packed & 0xFF,
                (packed >> 8) & 0xFF,
                (packed >> 16) & 0xFF,
                (packed >> 24) & 0xFF,
            )
            face_indices = indices[:vertices_per_face]
            if any(index >= vertex_count for index in face_indices):
                return None

            face_uv: Optional[Tuple[Tuple[int, int], ...]] = None
            if family in TEXTURED_LONG_OPCODES:
                uv01 = read_u32(data, primitive_base + 0x04)
                uv23 = read_u32(data, primitive_base + 0x08)
                if vertices_per_face == 4:
                    uv4 = (
                        (uv01 & 0xFF, (uv01 >> 8) & 0xFF),
                        ((uv01 >> 16) & 0xFF, (uv01 >> 24) & 0xFF),
                        (uv23 & 0xFF, (uv23 >> 8) & 0xFF),
                        ((uv23 >> 16) & 0xFF, (uv23 >> 24) & 0xFF),
                    )
                    face_uv = uv4
                else:
                    # Matches game decode for long textured triangles:
                    # uv0 comes from uv01 high 16 bits, uv1/uv2 from uv23.
                    face_uv = (
                        ((uv01 >> 16) & 0xFF, (uv01 >> 24) & 0xFF),
                        (uv23 & 0xFF, (uv23 >> 8) & 0xFF),
                        ((uv23 >> 16) & 0xFF, (uv23 >> 24) & 0xFF),
                    )

            faces.append(
                MeshFace(
                    indices=face_indices,
                    uv=face_uv,
                    texture_slot=texture_slot,
                )
            )

        cursor = payload_offset + payload_size

    if not saw_terminator or not faces:
        return None

    return MeshData(offset=offset, vertices=vertices, faces=faces)


def extract_raw_textures(raw_path: Path, texture_dir: Path) -> Dict[int, RawTextureInfo]:
    raw_data = raw_path.read_bytes()
    chunks = raw_extractor.iterate_chunks(raw_data)
    texture_dir.mkdir(parents=True, exist_ok=True)

    textures: Dict[int, RawTextureInfo] = {}
    for chunk in chunks:
        cmd = chunk.command_id
        if cmd < 0 or cmd >= 0x20:
            continue

        output_png = texture_dir / f"tex_{cmd:02X}.png"
        ok, _ = raw_extractor.extract_indexed_packet(
            chunk.packet,
            cmd,
            output_png,
            0x0C,
            0x04,
            0x06,
            0x08,
            0x0A,
        )
        if not ok:
            continue

        width = raw_extractor.read_le_u16(chunk.packet, 0x04)
        height = abs(raw_extractor.read_le_s16(chunk.packet, 0x06))
        if width <= 0:
            width = 256
        if height <= 0:
            height = 256

        if cmd not in textures:
            textures[cmd] = RawTextureInfo(slot=cmd, path=output_png, width=width, height=height)

    return textures


def write_mtl(
    mtl_path: Path,
    texture_dir: Path,
    texture_info_by_slot: Dict[int, RawTextureInfo],
    used_texture_slots: Sequence[int],
) -> None:
    lines: List[str] = []
    for slot in used_texture_slots:
        material_name = f"tex_{slot:02X}"
        lines.append(f"newmtl {material_name}")
        lines.append("Kd 1.000000 1.000000 1.000000")
        info = texture_info_by_slot.get(slot)
        if info is not None:
            lines.append(f"map_Kd {texture_dir.name}/{info.path.name}")
        lines.append("")

    mtl_path.write_text("\n".join(lines).rstrip() + "\n", encoding="ascii")


def write_obj(
    parts: Sequence[ObjPart],
    output_path: Path,
    texture_info_by_slot: Optional[Dict[int, RawTextureInfo]] = None,
    mtl_path: Optional[Path] = None,
) -> List[int]:
    lines: List[str] = []
    used_texture_slots: set[int] = set()
    if mtl_path is not None:
        lines.append(f"mtllib {mtl_path.name}")
    next_vertex = 1
    next_texcoord = 1

    for part in parts:
        if not part.vertices or not part.faces:
            continue

        lines.append(f"o {part.name}")
        base_vertex = next_vertex

        for x, y, z, r, g, b in part.vertices:
            lines.append(f"v {x:.6f} {y:.6f} {z:.6f} {r:.6f} {g:.6f} {b:.6f}")
        next_vertex += len(part.vertices)

        current_material: Optional[str] = None
        for face in part.faces:
            obj_indices = [base_vertex + index for index in face.indices]
            if face.uv is not None and face.texture_slot is not None:
                material_name = f"tex_{face.texture_slot:02X}"
                used_texture_slots.add(face.texture_slot)
                if mtl_path is not None and material_name != current_material:
                    lines.append(f"usemtl {material_name}")
                    current_material = material_name

                width = 256
                height = 256
                if texture_info_by_slot is not None and face.texture_slot in texture_info_by_slot:
                    info = texture_info_by_slot[face.texture_slot]
                    width = max(1, info.width)
                    height = max(1, info.height)

                texcoord_indices: List[int] = []
                for u, v in face.uv:
                    u_norm = u / float(width)
                    v_norm = 1.0 - (v / float(height))
                    lines.append(f"vt {u_norm:.6f} {v_norm:.6f}")
                    texcoord_indices.append(next_texcoord)
                    next_texcoord += 1

                face_tokens = [
                    f"{obj_indices[i]}/{texcoord_indices[i]}" for i in range(len(obj_indices))
                ]
                lines.append(f"f {' '.join(face_tokens)}")
            else:
                lines.append(f"f {' '.join(str(index) for index in obj_indices)}")

    output_path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return sorted(used_texture_slots)


def extract_dat(path: Path) -> Tuple[List[ObjPart], ExtractionStats]:
    data = path.read_bytes()
    dat_file = parse_dat(path)
    mesh_cache: Dict[int, Optional[MeshData]] = {}
    parts: List[ObjPart] = []
    first_geometry_header_meshes = 0
    second_geometry_header_meshes = 0
    object_meshes = 0
    unsupported_mesh_streams = 0

    def get_mesh(offset: int) -> Optional[MeshData]:
        nonlocal unsupported_mesh_streams
        if offset not in mesh_cache:
            mesh_cache[offset] = parse_mesh_stream(data, offset)
            if mesh_cache[offset] is None:
                unsupported_mesh_streams += 1
        return mesh_cache[offset]

    for headers_name, headers in (
        ("primary", dat_file.primary_geometry_headers),
        ("secondary", dat_file.secondary_geometry_headers),
    ):
        for index, header in enumerate(headers):
            instance = parse_geometry_instance(data, header)
            if instance is None:
                continue

            pos, rot, scale, mesh_offset = instance
            mesh = get_mesh(mesh_offset)
            if mesh is None:
                continue

            vertices = transform_vertices(mesh.vertices, pos, rot, scale)
            part = ObjPart(
                name=f"{headers_name}_{index:03d}_type{header.type:02X}_mesh_{mesh_offset:08X}",
                vertices=vertices,
                faces=mesh.faces,
            )
            parts.append(part)
            if headers_name == "primary":
                first_geometry_header_meshes += 1
            else:
                second_geometry_header_meshes += 1

    for index, object_ref in enumerate(dat_file.object_refs):
        transform = parse_dat_object_transform(data, object_ref.transform_offset)
        if transform is None:
            continue

        mesh = get_mesh(transform.mesh_offset)
        if mesh is None:
            continue

        vertices = transform_vertices(mesh.vertices, transform.pos, transform.rot, transform.scale)
        parts.append(
            ObjPart(
                name=f"object_{index:03d}_type{object_ref.type:02X}_mesh_{transform.mesh_offset:08X}",
                vertices=vertices,
                faces=mesh.faces,
            )
        )
        object_meshes += 1

    mesh_streams = len([mesh for mesh in mesh_cache.values() if mesh is not None])
    stats = ExtractionStats(
        first_geometry_header_meshes=first_geometry_header_meshes,
        second_geometry_header_meshes=second_geometry_header_meshes,
        object_meshes=object_meshes,
        mesh_streams=mesh_streams,
        unsupported_mesh_streams=unsupported_mesh_streams,
    )
    return parts, stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract TSR DAT geometry to OBJ.")
    parser.add_argument("input_dat", type=Path, help="Path to the input .DAT file")
    parser.add_argument("output_obj", type=Path, nargs="?", help="Path to the output .OBJ file")
    parser.add_argument(
        "--raw",
        type=Path,
        help="Optional RAW path. When set, extract texture PNGs and emit MTL + UV-mapped OBJ faces.",
    )
    args = parser.parse_args()

    input_path = args.input_dat
    output_path = args.output_obj if args.output_obj else input_path.with_suffix(".obj")

    parts, stats = extract_dat(input_path)
    texture_info_by_slot: Optional[Dict[int, RawTextureInfo]] = None
    mtl_path: Optional[Path] = None
    texture_dir: Optional[Path] = None
    if args.raw is not None:
        texture_dir = output_path.parent / f"{output_path.stem}_textures"
        texture_info_by_slot = extract_raw_textures(args.raw, texture_dir)
        mtl_path = output_path.with_suffix(".mtl")

    used_texture_slots = write_obj(
        parts,
        output_path,
        texture_info_by_slot=texture_info_by_slot,
        mtl_path=mtl_path,
    )
    if mtl_path is not None and texture_dir is not None:
        write_mtl(
            mtl_path,
            texture_dir,
            texture_info_by_slot or {},
            used_texture_slots,
        )

    print(f"input: {input_path}")
    print(f"output: {output_path}")
    if args.raw is not None:
        print(f"raw: {args.raw}")
        if texture_dir is not None:
            print(f"textures: {texture_dir}")
        if mtl_path is not None:
            print(f"mtl: {mtl_path}")
        print(f"materials_used: {len(used_texture_slots)}")
    print(f"first_geometry_header_meshes: {stats.first_geometry_header_meshes}")
    print(f"second_geometry_header_meshes: {stats.second_geometry_header_meshes}")
    print(f"objects: {stats.object_meshes}")
    print(f"mesh_streams: {stats.mesh_streams}")
    print(f"unsupported_mesh_streams: {stats.unsupported_mesh_streams}")


if __name__ == "__main__":
    main()
