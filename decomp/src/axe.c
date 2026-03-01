#include <axe.h>
#include <inline_gte.h>
#include <graphics.h>
#include <prim.h>
#include <extern.h>

static bool Axe_QuadPassesAxisClip(s32 v0, s32 v1, s32 v2, s32 v3, s32 clipMin, s32 clipMax)
{
    if (v0 - clipMin < 0) { return (v1 - clipMin >= 0) || (v2 - clipMin >= 0) || (v3 - clipMin >= 0); }

    return (v0 - clipMax < 0) || (v1 - clipMax < 0) || (v2 - clipMax < 0) || (v3 - clipMax < 0);
}

static bool Axe_QuadPassesClip(const PointQuad *screenPoints, s32 clipMinX, s32 clipMinY, s32 clipMaxX, s32 clipMaxY)
{
    return Axe_QuadPassesAxisClip((s32) screenPoints->p[0].self, (s32) screenPoints->p[1].self, (s32) screenPoints->p[2].self, (s32) screenPoints->p[3].self, clipMinY, clipMaxY) &&
            Axe_QuadPassesAxisClip((s32) (screenPoints->p[0].self << 16), (s32) (screenPoints->p[1].self << 16), (s32) (screenPoints->p[2].self << 16), (s32) (screenPoints->p[3].self << 16), clipMinX, clipMaxX);
}

static bool Axe_ProjectAndClipQuad(const SVec3 *v0, const SVec3 *v1, const SVec3 *v2, const SVec3 *v3, s32 minOtz, PointQuad *screenPointsOut)
{
    const s32 clipMinX = (s32) ((u32) (u16) g_activeViewport_ClipMinX << 16);
    const s32 clipMinY = (s32) ((u32) (u16) g_activeViewport_ClipMinY << 16);
    const s32 clipMaxX = (s32) ((u32) (u16) g_activeViewport_ClipMaxX << 16);
    const s32 clipMaxY = (s32) ((u32) (u16) g_activeViewport_ClipMaxY << 16);

    const SVec3 v1_ = *v1; // gte instruction fix: align 4 bytes
    const SVec3 v3_ = *v3; // gte instruction fix: align 4 bytes
    gte_loadSVec(v0, GTE_VECTOR_0);
    gte_rtps_b();
    gte_loadSVec(&v1_, GTE_VECTOR_0);
    gte_loadSVec(v2, GTE_VECTOR_1);
    gte_loadSVec(&v3_, GTE_VECTOR_2);

    PointQuad screenPoints;
    screenPoints.p[0] = GTE_ReadSxy2();

    gte_rtpt_b();
    gte_avsz4();

    const s32 otz = GTE_ReadOtz();

    if (otz <= minOtz) { return false; }

    GTE_ReadSxyVec(&screenPoints.p[1]);

    if (!Axe_QuadPassesClip(&screenPoints, clipMinX, clipMinY, clipMaxX, clipMaxY)) { return false; }

    *screenPointsOut = screenPoints;
    return true;
}

void Axe_RenderChunkStream(AxeChunk *axeChunks, s32 chunkCount, s32 scratchDataCount)
{
    const u8 *const primLimit = g_primMemEnd - sizeof(PolyG4);
    u32 clearCount = ((u32) scratchDataCount + 7U) >> 3;
    u32 *scratch = (u32 *) g_axeScratchpadDataBeg;
    u32 otTag = *(u32 *) (g_otPtr + GRAPHICS_OT_OFFSET_SKYBOX);
    PolyG4 *prim = (PolyG4 *) g_primMem;

    while (clearCount > 0)
    {
        scratch[0] = 0;
        scratch[1] = 0;
        scratch += 2;
        clearCount--;
    }

    for (s32 chunkIndex = 0; chunkIndex < chunkCount; chunkIndex++)
    {
        AxeChunk *chunk = &axeChunks[chunkIndex];
        PointQuad clipScreenPoints;
        if (!Axe_ProjectAndClipQuad(&chunk->cull.p[0], &chunk->cull.p[1], &chunk->cull.p[2], &chunk->cull.p[3], 0, &clipScreenPoints)) { continue; }

        AxeFace *face = chunk->pFace;
        u8 *const vertexBase = (u8 *) &chunk->pVertices->pos.x;

        for (s32 faceIndex = 0; faceIndex < chunk->faceCount; faceIndex++, face++)
        {
            if (*face->pSkipFaceFlag != 0) { continue; }

            *face->pSkipFaceFlag = 1;

            AxeVertex *v0 = (AxeVertex *) (vertexBase + face->v[0]);
            AxeVertex *v1 = (AxeVertex *) (vertexBase + face->v[1]);
            AxeVertex *v2 = (AxeVertex *) (vertexBase + face->v[2]);
            AxeVertex *v3 = (AxeVertex *) (vertexBase + face->v[3]);
            PointQuad screenPoints;
            if (!Axe_ProjectAndClipQuad(&v0->pos, &v1->pos, &v2->pos, &v3->pos, GRAPHICS_MIN_OTZ_SKYBOX, &screenPoints)) { continue; }

            if ((u8 *) prim > primLimit)
            {
                g_primMem = prim;
                *(u32 *) (g_otPtr + GRAPHICS_OT_OFFSET_SKYBOX) = otTag;
                return;
            }

            prim->v[1].pos = screenPoints.p[0]; prim->v[0].pos = screenPoints.p[1];
            prim->v[2].pos = screenPoints.p[2]; prim->v[3].pos = screenPoints.p[3];

            prim->v[1].color = v0->color; prim->v[0].color = v1->color;
            prim->v[2].color = v2->color; prim->v[3].color = v3->color;
            Prim_SetPolyG4(&prim->v[0].color.code);

            SetPrimTag(prim, otTag);
            prim++;
        }
    }

    g_primMem = prim;
    *(u32 *) (g_otPtr + GRAPHICS_OT_OFFSET_SKYBOX) = otTag;
}

static void Axe_InitChunkStream()
{
    if (g_axeChunkCount <= 0) { return; }

    for (s32 chunkIndex = 0; chunkIndex < g_axeChunkCount; chunkIndex++)
    {
        AxeChunk *chunk = &g_axeChunkStream[chunkIndex];

        for (s32 vertexIndex = 0; vertexIndex < chunk->colorSwapCount; vertexIndex++)
        {
            AxeVertex *vertex = &chunk->pVertices[vertexIndex];
            const u8 blue = vertex->color.b;
            vertex->color.code.code = 0;
            vertex->color.b = vertex->color.r;
            vertex->color.r = blue;
        }

        for (s32 faceIndex = 0; faceIndex < chunk->faceCount; faceIndex++)
        {
            AxeFace *face = &chunk->pFace[faceIndex];

            if (face->v[0] < 0) { face->v[0] = (s16) -face->v[0]; }

            face->v[0] = face->v[0] * sizeof(AxeVertex); face->v[1] = face->v[1] * sizeof(AxeVertex);
            face->v[2] = face->v[2] * sizeof(AxeVertex); face->v[3] = face->v[3] * sizeof(AxeVertex);
            face->pSkipFaceFlag = (u8 *) ((uintptr_t) face->pSkipFaceFlag + (uintptr_t) &g_axeScratchpadDataBeg);
        }
    }
}

void Axe_ParseHeader()
{
    u8 *const axeBase = (u8 *) &g_ptrAxe->offSkipFaceList;
    AxeChunk *chunk = (AxeChunk *) (g_ptrAxe + 1);

    g_axePtrSkipFaceSize = (u32 *) (axeBase + g_ptrAxe->offSkipFaceList);
    g_axeChunkCount = (s16) g_ptrAxe->chunkCount;
    g_axeSkipFaceSize = (u16) *g_axePtrSkipFaceSize;
    g_axeChunkStream = chunk;

    for (s32 chunkIndex = 0; chunkIndex < g_axeChunkCount; chunkIndex++, chunk++)
    {
        chunk->pVertices = (AxeVertex *) (axeBase + (uintptr_t) chunk->pVertices);
        chunk->pFace = (AxeFace *) (axeBase + (uintptr_t) chunk->pFace);
    }

    Axe_InitChunkStream();
}
