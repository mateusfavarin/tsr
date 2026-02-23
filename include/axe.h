#pragma once

#include "types.h"
#include "math.h"
#include "prim.h"

typedef struct AxeOcclusionQuad
{
    SVec3 p[4];
} AxeOcclusionQuad;

typedef struct AxeFace
{
    s16 v[4];
    u8 *pSkipFaceFlag;
} AxeFace;

typedef struct AxeVertex
{
    SVec3 pos;
    u16 pad1;
    ColorCode color;
} AxeVertex;

typedef struct AxeChunk
{
    AxeVertex *pVertices;
    AxeFace *pFace;
    u32 field_0x08;
    AxeOcclusionQuad cull;
    s16 colorSwapCount;
    s16 faceCount;
    u32 field_0x28;
} AxeChunk;

typedef struct AxeHeader
{
    u32 offSkipFaceList;
    u32 chunkCount;
} AxeHeader;

void Axe_ParseHeader();
void Axe_RenderChunkStream(AxeChunk *axeChunks, s32 chunkCount, s32 scratchDataCount);
