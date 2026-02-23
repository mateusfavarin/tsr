# AXE File Format (TSR PS1)

Derived from `Axe_ParseHeader`, `Axe_InitChunkStream`, and `Render_AxeChunkStream` in `axe.c`, plus file observations.
All offsets below are file-relative (base = AXE header start).

## Top-Level Layout

| Offset | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x04` | `u32` | `skipFaceDataCount` |
| `0x04` | `0x04` | `u32` | `chunkCount` |
| `0x08` | `chunkCount * 0x2C` | `AxeChunk[]` | Chunk table |
| `...` | variable | mixed | Vertex/face blocks referenced by chunk offsets |
| `skipFaceDataCount` | `0x4` | `u32` | Size of skip face array |
| `skipFaceDataCount + 0x4` | `skipFaceDataCount` | `u8[]` | Skip face bool table |

## `AxeChunk` (size `0x2C`)

| Off | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x04` | `u32` | `offVertices` |
| `0x04` | `0x04` | `u32` | `offFaces` |
| `0x08` | `0x04` | `u32` | `offUnknown` (relocated, semantics unknown in these functions) |
| `0x0C` | `0x18` | `OcclusionQuad` | 4 points (`s16 x,y,z`) |
| `0x24` | `0x02` | `s16` | `colorSwapCount` |
| `0x26` | `0x02` | `s16` | `faceCount` |
| `0x28` | `0x04` | `u32` | `unk_0x28` |

## `AxeVertex` (size `0x0C`)

| Off | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x02` | `s16` | `x` |
| `0x02` | `0x02` | `s16` | `y` |
| `0x04` | `0x02` | `s16` | `z` |
| `0x06` | `0x02` | `u16` | `pad1` |
| `0x08` | `0x01` | `u8` | `r` |
| `0x09` | `0x01` | `u8` | `g` |
| `0x0A` | `0x01` | `u8` | `b` |
| `0x0B` | `0x01` | `u8` | `pad2` |

## `AxeFace` (size `0x0C`)

| Off | Size | Type | Meaning |
|---|---:|---|---|
| `0x00` | `0x02` | `u16` | `v0` |
| `0x02` | `0x02` | `u16` | `v1` |
| `0x04` | `0x02` | `u16` | `v2` |
| `0x06` | `0x02` | `u16` | `v3` |
| `0x08` | `0x04` | `u32` | `offSkipFace` (index into scratchpad; faces may share this) |

## Scratchpad Skip Face Table

| Location | Size | Type | Meaning |
|---|---:|---|---|
| `skipFaceDataCount + 0x4` | `skipFaceDataCount` | `u8[]` | Skip face bool bytes used by face offset links/dedup behavior |

Note: runtime currently clears scratchpad flag bytes every render pass; this tail table does not appear to be read by the game.

## Runtime Fixups Used By Renderer

| Stage | Operation |
|---|---|
| `Axe_ParseHeader` | Relocates `offVertices`, `offFaces`, `offUnknown` to absolute pointers using AXE base. |
| `Axe_ParseHeader` | Initializes runtime scratchpad flag count (`skipFaceDataCount`) used by AXE face dedup skip logic. |
| `Axe_InitChunkStream` | For first `colorSwapCount` vertices: swaps `r <-> b`, sets `pad2 = 0`. |
| `Axe_InitChunkStream` | Converts face vertex indices to byte offsets, with `v0 = abs(v0)` before scaling. |
| `Axe_InitChunkStream` | Converts face flag offsets to scratchpad pointers: `0x1F800020 + offSkipFace`. |
| `Render_AxeChunkStream` | Clears scratchpad face-drawn bytes from `0x1F800020` over `ceil(skipFaceDataCount / 8) * 8` bytes. |
| `Render_AxeChunkStream` | Uses per-face scratchpad flag byte to avoid drawing certain faces more than once; if multiple faces share `offBoolFaceDrawn`, only the first drawn face renders. |
