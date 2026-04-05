# DAT File Format (TSR PS1)

Derived from `ReadLevelDAT`, `Render_LevelChunk`, `RenderLevelChunkDispatch`, and the `RenderChunkTypeXX_Variant` helpers in `research/ghidra/exe.c`.
All offsets below are file-relative.

## Top-Level Layout

| Offset | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x04` | `u32` | `sectionCount` |
| `0x04` | variable | mixed | DAT section list |
| `...` | `0x04` | `u32` | `routingTableCount` |
| `...` | `routingTableCount * 0x80` | `u8[]` | routing / visibility table |
| `...` | variable | `DatGeometryHeader[]` | primary geometry headers, terminated by `type == 0` |
| `...` | `0x04` | `s32` | `objectCount` |
| `...` | `(objectCount + 1) * 0x04` or none | `u32[]` | object offset table, only when `objectCount >= 0` |
| `...` | variable | `DatGeometryHeader[]` | secondary geometry headers, terminated by `type == 0` |
| EOF | `0x04` | `s32` | chunk toggle footer offset or `-1` |

Note: `objectCount` is signed. `-1` means there is no object-offset table.

## DAT Section Header

| Off | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x02` | `u16` | `entryCount` |
| `0x02` | `0x02` | `s16` | `sectionType` |

## DAT Section Sizing

| `sectionType` | Size rule |
|---|---|
| `< 0` | `(((entryCount * 3) + 1) / 2) * 4 + 0x10` |
| `0x3F` | `entryCount * 0x10 + 0x04` |
| all other known types | `entryCount * 0x0C + 0x04` |

## Chunk and Upper Sections

| Section type | Meaning |
|---|---|
| `0x40` | chunk-section polygon / bounds points |
| `0x41+` | upper-section polygons; runtime divides these point coordinates by `4` |

Both section families store `entryCount` 3D points immediately after the 4-byte header.

## `DatGeometryHeader` (size `0x14`)

| Off | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x04` | `s32` | `x` |
| `0x04` | `0x04` | `s32` | `y` |
| `0x08` | `0x04` | `s32` | `z` |
| `0x0C` | `0x02` | `u16` | `cullRadius` |
| `0x0E` | `0x01` | `u8` | `type` |
| `0x0F` | `0x01` | `u8` | `sectionId` |
| `0x10` | `0x04` | `u32` | `offGeometryObject` |

Runtime halves the primary-header positions and cull radius after relocation.

Runtime note:
- In the DAT file, `offGeometryObject` points to one of the geometry-object layouts below.
- After `Dat_ParseMetadata`, that field is overwritten with a `MATRIX *` used by the renderer.

## `DatObjectRef` (size `0x14`)

The signed `objectCount` table is a second instance system in the DAT. These entries are not part of the primary or secondary chunk-header lists. Runtime code uses them through `DAT_SetObjectTransformScaled`, `DAT_SetObjectTransformWithMode`, `DAT_GetObjectWorldPosition`, `DAT_SetObjectWorldPosition`, and `RetargetDatObjectInstance`.

| Off | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x04` | `s32` | `posX` |
| `0x04` | `0x04` | `s32` | `posY` |
| `0x08` | `0x04` | `s32` | `posZ` |
| `0x0C` | `0x02` | `u16` | `cullRadius` |
| `0x0E` | `0x01` | `u8` | `type` |
| `0x0F` | `0x01` | `u8` | `flags` |
| `0x10` | `0x04` | `u32` | `offObjectTransformDef` |

Evidence:
- `CollectSectionObjectsVisibleDualBucket` and `CollectSectionObjectsVisibleSingleBucket` use this field exactly like the entity-header radius during visibility tests.
- `DAT_SetObjectWorldPosition` updates both the outer object position and the inner transform position, which confirms the outer object record participates in culling / placement state.

File vs runtime note:
- In the DAT file, `offObjectTransformDef` points to the `DatObjectTransformDef` block below.
- After runtime initialization, this field no longer points directly to the file block. It is replaced with a runtime object that overlays a `MATRIX`.
- That runtime object keeps a back-pointer to the original file transform block at its own `+0x14`.

## `DatObjectTransformDef` (size `0x20`)

For every nonzero object-table entry tested so far, `offObjectTransform + 0x1C` points to a valid mesh stream. This is the path used by object-table props such as scene anchors, collectibles, and other non-chunk instances.

| Off | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x04` | `s32` | `posX` |
| `0x04` | `0x04` | `s32` | `posY` |
| `0x08` | `0x04` | `s32` | `posZ` |
| `0x0C` | `0x02` | `s16` | `rotX` |
| `0x0E` | `0x02` | `s16` | `rotY` |
| `0x10` | `0x02` | `s16` | `rotZ` |
| `0x12` | `0x02` | `s16` | `scaleX` |
| `0x14` | `0x02` | `s16` | `scaleY` |
| `0x16` | `0x02` | `s16` | `scaleZ` |
| `0x18` | `0x04` | `u32` | field_0x18, exact meaning still under review |
| `0x1C` | `0x04` | `u32` | `offMeshStream` |

This block uses the same transform convention as chunk geometry: Euler rotation in PSX angle units and fixed-point scale where `0x1000 == 1.0`.

The object API treats the stored position as internal half-world units:
- `DAT_GetObjectWorldPosition` returns `pos << 1`
- `DAT_SetObjectWorldPosition` stores `worldPos >> 1`

That means these positions are not directly the same API-space coordinates used by gameplay code, even though they are the coordinates consumed by the internal renderer and culling code.

## `DatObjectRuntime` (runtime only, size `0x28`)

This is not the file layout. It is the runtime object reached through `DatObjectRef.transform` after `Dat_ParseMetadata`.

| Off | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x14` | matrix basis | `MATRIX.m` plus pad |
| `0x14` | `0x04` | pointer | `transformDef` back-pointer |
| `0x18` | `0x04` | `u32` | `scratchHandleList` |
| `0x1C` | `0x04` | `u32` | `field_0x1C` |
| `0x20` | `0x02` | `s16` | `renderObjectCount` |
| `0x22` | `0x02` | `s16` | unknown |
| `0x24` | `0x04` | `u32` | unknown |

Notes:
- `transformDef` is read by `DAT_GetObjectWorldPosition` and `DAT_SetObjectWorldPosition`.
- `scratchHandleList` is freed and replaced by `RetargetDatObjectInstance`.
- `renderObjectCount` is copied during retarget and used by the render-scratch allocation path. It is not the DAT file's top-level `objectCount`.

## Geometry Object Layouts

The entity header does not point directly to a mesh stream. It points to a small transform object that then points to the primitive stream.

The extractor does not rely on a fixed entity-type allowlist. It attempts to parse every relocated geometry object and keeps the ones whose payload resolves to a valid mesh stream.

### Unscaled geometry object (`type & 0x08 == 0`)

| Off | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x04` | `s32` | `posX` |
| `0x04` | `0x04` | `s32` | `posY` |
| `0x08` | `0x04` | `s32` | `posZ` |
| `0x0C` | `0x02` | `s16` | `rotX` |
| `0x0E` | `0x02` | `s16` | `rotY` |
| `0x10` | `0x02` | `s16` | `rotZ` |
| `0x12` | `0x01` | `u8` | packed material / color selector |
| `0x13` | `0x01` | `u8` | lighting preset / flags |
| `0x14` | `0x04` | `u32` | `offMeshStream` |

### Scaled geometry object (`type & 0x08 != 0`)

| Off | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x04` | `s32` | `posX` |
| `0x04` | `0x04` | `s32` | `posY` |
| `0x08` | `0x04` | `s32` | `posZ` |
| `0x0C` | `0x02` | `s16` | `rotX` |
| `0x0E` | `0x02` | `s16` | `rotY` |
| `0x10` | `0x02` | `s16` | `rotZ` |
| `0x12` | `0x02` | `s16` | `scaleX` |
| `0x14` | `0x02` | `s16` | `scaleY` |
| `0x16` | `0x02` | `s16` | `scaleZ` |
| `0x18` | `0x01` | `u8` | packed material / color selector |
| `0x19` | `0x01` | `u8` | lighting preset / flags |
| `0x1C` | `0x04` | `u32` | `offMeshStream` |

The loader builds the same rotation matrix the renderer uses, then scales its axes by `scaleX/Y/Z`.

## `DatChunkSectionHeader`

This is an inline file-layout header, not a pointer-based struct.

| Off | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x02` | `u16` | `pointCount` |
| `0x02` | `0x02` | `u16` | `sectionType` |
| `0x04` | variable | `Vec3[]` | inline point list |

The current Ghidra `Vec3 *points` field is a decompiler convenience, not the on-disk layout.

## Mesh Stream Layout

| Off | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x04` | `s32` | `vertexCount` |
| `0x04` | `vertexCount * 0x08` | `DatMeshVertex[]` | local-space vertices |
| `...` | variable | command stream | consumed by `RenderLevelChunkDispatch` |

Current evidence only covers the common positive `vertexCount` path. No negative-count mesh streams have been observed in level DATs yet.

## `DatMeshVertex` (size `0x08`)

| Off | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x02` | `s16` | `x` |
| `0x02` | `0x02` | `s16` | `y` |
| `0x04` | `0x02` | `s16` | `z` |
| `0x06` | `0x02` | `u16` | packed color / pad |

The renderer treats each entry as an `SVECTOR`; the final halfword is read separately for packed vertex color data.

## Primitive Command Header

Each command block starts with:

| Off | Size | Type | Meaning |
|---|---:|---|---|
| `+0x00` | `0x02` | `u16` | opcode / texture page selector |
| `+0x02` | `0x02` | `u16` | primitive count and depth mode bits |

The low 5 bits of the first halfword select the render family.
The low 10 bits of the second halfword are the primitive count.

Observed terminator rule:

| Condition | Meaning |
|---|---|
| `(count == 0x3FF) && (((cmd1 >> 12) & 3) != 0)` | end of mesh stream |

## Primitive Payload Families

Geometry extraction only needs the packed vertex indices. Texture coordinates, CLUT, and shading words can be skipped.

| Opcode family | Primitive size | Geometry |
|---|---:|---|
| `0x00,0x02,0x04,0x06,0x08,0x0A,0x0C,0x0E` | `3` words per primitive | quad |
| `0x01,0x03,0x05,0x07,0x09,0x0B,0x0D,0x0F` | `3` words per primitive | triangle |
| `0x10,0x12,0x14,0x16` | `1` word per primitive | quad |
| `0x11,0x13,0x15,0x17` | `1` word per primitive | triangle |

The lit variants (`0x08-0x0F`) may emit duplicate render packets for shading, but they still reference the same source geometry.

## Packed Vertex Index Word

The first payload word of every supported primitive packs up to 4 vertex indices as raw bytes:

| Bits | Meaning |
|---|---|
| `0..7` | `v0` |
| `8..15` | `v1` |
| `16..23` | `v2` |
| `24..31` | `v3` |

Triangle families use `v0,v1,v2`.

Quad families use the packed stream order:

| Source bytes | OBJ / rendered order |
|---|---|
| `v0,v1,v2,v3` | `v0,v1,v2,v3` |

Note: `RenderChunkType00_Variant`, `RenderChunkType02_Variant`, `RenderChunkType10` path, and `RenderChunkType12_Variant` swap the last two vertices while assembling the PSX quad packet. That is a renderer submission detail, not the source face order stored in the DAT mesh stream.

## Runtime Transform Used For Level Geometry

For each mesh instance:

| Stage | Operation |
|---|---|
| object transform | apply local `rotX/Y/Z` with `Geom_GetRotationMatrixFromEulerAngles` |
| scaled object only | scale matrix axes by `scaleX/Y/Z` |
| final placement | add object `posX/Y/Z` |

The extractor in `scripts/extract_dat.py` now follows that same transform path and writes the resulting world-space faces to OBJ.

The same transform path also applies to object-table meshes, using `DatObjectRef.offObjectTransformDef -> DatObjectTransformDef -> offMeshStream`.
