# RAW File Format (TSR PS1)

Derived from `File_LoadRAW`, `DecompressRAW`, and the callsites that consume decoded packets in `research/ghidra/exe.c`.

## Stream layout

RAW is a stream of compressed chunks followed by a `0xFFFFFFFF` sentinel.

| Offset (chunk-local) | Size | Endian | Meaning |
|---|---:|---|---|
| `+0x00` | `0x04` | big | decoded packet size |
| `+0x04` | `0x04` | big | compressed payload size (without `0x0E` chunk header) |
| `+0x08` | `0x06` | raw | codec header bytes |
| `+0x0E` | variable | raw | compressed payload bitstream |

For each chunk:
- `chunk_size = be32(+0x04) + 0x0E`
- decoded packet starts with LE `u32 commandId`
- next chunk starts at `chunk_base + chunk_size`

Stream end:
- if first 4 bytes at current stream cursor are `0xFFFFFFFF`, stop.

## Packet classes used by `File_LoadRAW`

| Command ID | Meaning in loader |
|---:|---|
| `< 0x20` | texture packet (indexed palette + pixel payload) |
| `0x20` | scrolling background packet (16bpp) |
| `0x21` | atlas/UV metadata packet |
| `0x22` | framebank A packet (runtime 4bpp update source) |
| `0x24` | scrolling background packet (indexed) |
| `0x25` | second scrolling background packet (16bpp) |
| `0x26` | framebank B packet (runtime 8bpp update source) |
| `0x28..0x2F` | pointer-table packet range A |
| `0x30..0x57` | pointer-table packet range C |
| `0x58..0x5F` | pointer-table packet range B (indexed background-compatible path) |
| `0x101` | animation cache packet |
| `0x102` | model cache packet |
| `0x103` | misc pointer packet |

## Extractor Output (`scripts/extract_raw.py`)

Naming:
- single image chunk: `index_command.png` (example: `0009_0x0009.png`)
- framebank chunk: `index_command_frame.png` (example: `0012_0x0026_003.png`)

CLI:
- `python scripts/extract_raw.py <input.raw> [output_dir]`
- `--verbose` prints per-chunk details (command, inferred mode/bpp path, dimensions, skip reason)

## CLUT and UV source map (game behavior)

This section documents where CLUT and UV come from in the original game code.

### Core rule

- Primitive builders ultimately use:
  - `finalClut = g_textureSlot[texSet].clut + clutOffset`
  - `finalTpage = g_textureSlot[texSet].tpage + tpageMode`

### Per-command source of UV/CLUT

| Command(s) | UV source | CLUT source |
|---|---|---|
| `< 0x20` indexed textures (general mesh/UI use) | primitive UV bytes in render data | `g_textureSlot[slot].clut + clutOffset` where `clutOffset` is derived by caller (often from high bits of UV) |
| `0x0A` (HUD portraits) | `g_characterProfile[charId].u` and `.v` | `g_characterProfile[charId].clut` passed as `clutOffset`; |
| `0x22` framebank A | frame copy destination UV tile comes from metadata table entry | rendering CLUT is not in frame payload; computed from metadata/slot: for 4bpp path `descriptor.clut = slot.clut + ((tileY & 0xC0) >> 4) + (tileX >> 6)` |
| `0x26` framebank B | same metadata table path as `0x22` | 8bpp path uses `descriptor.clut = slot.clut` (no 4x4 CLUT-cell) |
