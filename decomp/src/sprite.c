#include <sprite.h>
#include <inline_gte.h>
#include <extern.h>
#include <graphics.h>
#include <math.h>

typedef enum SpriteConstants
{
    SPRITE_NEGATE_LOW_WORD = 0x0000FFFF,
    SPRITE_NEGATE_HIGH_WORD = 0xFFFF0000,
    SPRITE_NEGATE_BOTH_WORDS = 0xFFFFFFFF,
    SPRITE_APPEND_Y_RANGE_HALF = 10000,
    SPRITE_APPEND_Y_RANGE_FULL = 20000,
    SPRITE_APPEND_FLAG_WIDE_Y_RANGE = 0x0100,
} SpriteConstants;

typedef enum SpriteOrientFlags
{
    SPRITE_ORIENT_MASK = 0x000F,
    SPRITE_ORIENT_FLAG_POS_Y = 0x0001,
    SPRITE_ORIENT_FLAG_POS_X = 0x0002,
    SPRITE_ORIENT_FLAG_NEG_Y = 0x0004,
    SPRITE_ORIENT_FLAG_NEG_X = 0x0008,
} SpriteOrientFlags;

static force_inline SVec3 Sprite_PackedXYToVec(Point point)
{
    SVec3 out;
    out.x = point.x;
    out.y = point.y;
    out.z = 0;
    return out;
}

static force_inline bool Sprite_HasAnyVisibleScreenPointY(const PointQuad *screenPoints)
{
    if (screenPoints->p[0].y < GRAPHICS_SCREEN_HEIGHT) { return true; }
    if (screenPoints->p[1].y < GRAPHICS_SCREEN_HEIGHT) { return true; }
    if (screenPoints->p[2].y < GRAPHICS_SCREEN_HEIGHT) { return true; }
    return screenPoints->p[3].y < GRAPHICS_SCREEN_HEIGHT;
}

static force_inline bool Sprite_HasAnyVisibleScreenPointX(const PointQuad *screenPoints)
{
    if (screenPoints->p[0].x < GRAPHICS_SCREEN_WIDTH) { return true; }
    if (screenPoints->p[1].x < GRAPHICS_SCREEN_WIDTH) { return true; }
    if (screenPoints->p[2].x < GRAPHICS_SCREEN_WIDTH) { return true; }
    return screenPoints->p[3].x < GRAPHICS_SCREEN_WIDTH;
}

static void Sprite_BuildCorners(const Sprite *sprite, PointQuad *corners)
{
    const u32 orientFlags = sprite->orientFlags;
    const u32 packedSize = sprite->size.self;
    const u32 orientMode = orientFlags & SPRITE_ORIENT_MASK;
    Point *v0Rtpt = &corners->p[0];
    Point *v1Rtpt = &corners->p[1];
    Point *v2Rtpt = &corners->p[2];
    Point *v0Rtps = &corners->p[3];

    if (orientMode == 0)
    {
        v2Rtpt->self = packedSize ^ SPRITE_NEGATE_HIGH_WORD;
        v0Rtps->self = packedSize ^ SPRITE_NEGATE_LOW_WORD;
        v0Rtpt->self = packedSize ^ SPRITE_NEGATE_BOTH_WORDS;
        v1Rtpt->self = packedSize;
        return;
    }

    const u32 packedY = packedSize & SPRITE_NEGATE_HIGH_WORD;
    u32 xLeft;
    u32 xRight;

    if ((orientFlags & SPRITE_ORIENT_FLAG_POS_X) == 0)
    {
        if ((orientFlags & SPRITE_ORIENT_FLAG_NEG_X) == 0)
        {
            xRight = packedSize & SPRITE_NEGATE_LOW_WORD;
            xLeft = xRight ^ SPRITE_NEGATE_LOW_WORD;
        }
        else
        {
            xLeft = ((packedSize * 2U) & SPRITE_NEGATE_LOW_WORD) ^ SPRITE_NEGATE_LOW_WORD;
            xRight = 0;
        }
    }
    else
    {
        xRight = (packedSize * 2U) & SPRITE_NEGATE_LOW_WORD;
        xLeft = 0;
    }

    const u32 packedYDouble = packedY * 2U;

    if ((orientFlags & SPRITE_ORIENT_FLAG_POS_Y) == 0)
    {
        if ((orientFlags & SPRITE_ORIENT_FLAG_NEG_Y) == 0)
        {
            v0Rtpt->self = (packedY ^ SPRITE_NEGATE_HIGH_WORD) + xLeft;
            v0Rtps->self = packedY + xLeft;
            v1Rtpt->self = packedY + xRight;
            v2Rtpt->self = (packedY ^ SPRITE_NEGATE_HIGH_WORD) + xRight;
        }
        else
        {
            v0Rtpt->self = xLeft + (packedYDouble ^ SPRITE_NEGATE_HIGH_WORD);
            v2Rtpt->self = xRight + (packedYDouble ^ SPRITE_NEGATE_HIGH_WORD);
            v0Rtps->self = xLeft;
            v1Rtpt->self = xRight;
        }
    }
    else
    {
        v0Rtps->self = xLeft + packedYDouble;
        v0Rtpt->self = xLeft;
        v1Rtpt->self = packedYDouble + xRight;
        v2Rtpt->self = xRight;
    }
}

static void Sprite_BuildRotationMatrix(u16 angle, s32 spriteYScale, Mat3 *rotation)
{
    const u16 sinAngle = ANG_MODULO_TWO_PI(angle);
    const u16 cosAngle = ANG_MODULO_TWO_PI(angle + ANG_HALF_PI);

    if (angle == 0)
    {
        rotation->m[0][0] = FP(1.6f); rotation->m[0][1] = 0; rotation->m[0][2] = 0;
        rotation->m[1][0] = 0; rotation->m[1][1] = (s16) spriteYScale; rotation->m[1][2] = 0;
        rotation->m[2][0] = 0; rotation->m[2][1] = 0; rotation->m[2][2] = FP_ONE;
        return;
    }

    const s16 sinQuarter = g_sinTable[sinAngle] >> 2; const s16 cosQuarter = g_sinTable[cosAngle] >> 2;
    const s16 sinEighth = g_sinTable[sinAngle] >> 3; const s16 cosEighth = g_sinTable[cosAngle] >> 3;
    const s16 sinBlend = sinEighth + sinQuarter; const s16 cosBlend = cosEighth + cosQuarter;

    s32 scaledSinQuarter = sinQuarter;
    s32 scaledCosQuarter = cosQuarter;

    if (spriteYScale != FP_ONE)
    {
        scaledSinQuarter = FP_MULT(sinQuarter, spriteYScale);
        scaledCosQuarter = FP_MULT(cosQuarter, spriteYScale);
    }

    rotation->m[0][0] = cosBlend; rotation->m[0][1] = -sinBlend; rotation->m[0][2] = 0;
    rotation->m[1][0] = scaledSinQuarter; rotation->m[1][1] = scaledCosQuarter; rotation->m[1][2] = 0;
    rotation->m[2][0] = 0; rotation->m[2][1] = 0; rotation->m[2][2] = FP_ONE;
}

void Sprite_RenderQueue(const Sprite *sprites, s32 count)
{
    const s32 spriteYScale = (s32) g_spriteYScale;
    const s32 depthLimitBytes = g_otDepthLimit << 2;
    const u8 *const primLimit = g_primMemEnd - sizeof(PolyFT4);
    Mat3 rotation = { 0 };

    gte_SetColorMatrix((void *) &g_cameraMatrix);

    for (s32 i = 0; i < count; i++)
    {
        const Sprite *sprite = &sprites[i];
        PointQuad corners;
        PointQuad screenPoints;
        Vec3 transformedCenter;

        Sprite_BuildCorners(sprite, &corners);
        gte_loadSVec(&sprite->pos, GTE_VECTOR_0);
        gte_lcv0_b();
        transformedCenter = GTE_ReadMac();

        Sprite_BuildRotationMatrix(sprite->angle, spriteYScale, &rotation);
        gte_SetRotMatrix(&rotation);
        gte_ldtr(transformedCenter.x, transformedCenter.y, transformedCenter.z);

        const SVec3 corner0 = Sprite_PackedXYToVec(corners.p[0]);
        const SVec3 corner1 = Sprite_PackedXYToVec(corners.p[1]);
        const SVec3 corner2 = Sprite_PackedXYToVec(corners.p[2]);
        const SVec3 corner3 = Sprite_PackedXYToVec(corners.p[3]);

        gte_loadSVec(&corner0, GTE_VECTOR_0);
        gte_loadSVec(&corner1, GTE_VECTOR_1);
        gte_loadSVec(&corner2, GTE_VECTOR_2);
        gte_rtpt_b();

        GTE_ReadSxyVec(screenPoints.p);

        gte_loadSVec(&corner3, GTE_VECTOR_0);
        gte_rtps_b();

        screenPoints.p[3] = GTE_ReadSxy2();

        if (!Sprite_HasAnyVisibleScreenPointY(&screenPoints)) { continue; }

        gte_avsz4_b();
        const s32 otz = GTE_ReadOtz();

        if (otz <= GRAPHICS_MIN_OTZ_SPRITE) { continue; }
        if (!Sprite_HasAnyVisibleScreenPointX(&screenPoints)) { continue; }

        if ((u8 *) g_primMem > primLimit) { return; }

        s32 depthByteOffset = (otz + (s32) sprite->otDepthBias) * (s32) sizeof(u32);

        if (depthByteOffset < 0) { depthByteOffset = 0; }
        if (depthByteOffset >= depthLimitBytes) { continue; }

        const u16 otOffset = g_depthToOTDepthLUT[(u32) (depthByteOffset >> 2)];
        u32 *otTagPtr = (u32 *) (g_otPtr + otOffset);
        u32 otTag = *otTagPtr;
        PolyFT4 *prim = (PolyFT4 *) g_primMem;

        const u8 u0 = sprite->uv.u; const u8 v0 = sprite->uv.v;
        const u8 u1 = u0 + sprite->texWidth; const u8 v1 = v0;
        const u8 u2 = u0; const u8 v2 = v0 + sprite->texHeight;
        const u8 u3 = u1; const u8 v3 = v2;

        prim->v[0].pos = screenPoints.p[0]; prim->v[1].pos = screenPoints.p[2];
        prim->v[2].pos = screenPoints.p[3]; prim->v[3].pos = screenPoints.p[1];

        prim->colorCode = sprite->color;

        prim->v[0].texCoords.u = u0; prim->v[0].texCoords.v = v0;
        prim->v[1].texCoords.u = u1; prim->v[1].texCoords.v = v1;
        prim->v[2].texCoords.u = u2; prim->v[2].texCoords.v = v2;
        prim->v[3].texCoords.u = u3; prim->v[3].texCoords.v = v3;

        prim->v[0].clut.self = sprite->clut;
        prim->v[1].tpage.self = sprite->tpage;

        SetPrimTag(prim, otTag);
        *otTagPtr = otTag;
        g_primMem = prim + 1;
    }
}

void Sprite_AppendQueue(s32 x, s32 y, s32 z, s16 sizeX, s16 sizeY, u16 orientFlags, u16 angle, u8 u, u8 v,
                        u8 texWidth, u8 texHeight, u8 red, u8 green, u8 blue, s32 textureSlot,
                        u16 clutOffset, u32 flags, s16 otDepthBias)
{
    s32 relY = y - g_cameraPosCoarse.y;
    const s32 relZ = z - g_cameraPosCoarse.z;
    const s32 yRange = (flags & SPRITE_APPEND_FLAG_WIDE_Y_RANGE) ? (SPRITE_APPEND_Y_RANGE_FULL * 2) : (SPRITE_APPEND_Y_RANGE_HALF * 2);
    const s32 yRangeHalf = (flags & SPRITE_APPEND_FLAG_WIDE_Y_RANGE) ? SPRITE_APPEND_Y_RANGE_FULL : SPRITE_APPEND_Y_RANGE_HALF;

    if (relY + yRangeHalf > yRange) { return; }

    Sprite *sprite = &g_spriteQueue[g_spriteQueueSize];
    const TextureSlot *slot = &g_textureSlot[textureSlot];
    const u16 tpageTransparencyFlags = flags & TEXPAGE_TRANSPARENCY_BITS;
    const u16 tpage = slot->tpage + tpageTransparencyFlags;
    const u16 clut = slot->clut + clutOffset;

    sprite->pos.x = (s16) (x - g_cameraPosCoarse.x);
    sprite->pos.y = (s16) relY;
    sprite->pos.z = (s16) relZ;
    sprite->otDepthBias = otDepthBias;
    sprite->size.x = sizeX;
    sprite->size.y = sizeY;
    sprite->orientFlags = orientFlags;
    sprite->angle = angle;
    sprite->tpage = tpage;
    sprite->clut = clut;
    sprite->uv.u = u;
    sprite->uv.v = v;
    sprite->texWidth = texWidth;
    sprite->texHeight = texHeight;
    sprite->color.r = red;
    sprite->color.g = green;
    sprite->color.b = blue;
    Prim_SetPolyFT4(&sprite->color.code);
    if (tpageTransparencyFlags != TEXPAGE_TRANSPARENCY_OPAQUE) { sprite->color.code.poly.semiTransparency = 1; }

    g_spriteQueueSize++;

    if (g_spriteQueueSize >= SPRITE_QUEUE_SIZE)
    {
        Sprite_FlushQueue();
    }
}

void Sprite_ClearQueue()
{
    g_spriteQueueSize = 0u;
}

void Sprite_FlushQueue()
{
    Sprite_RenderQueue(g_spriteQueue, g_spriteQueueSize);
    g_spriteQueueSize = 0u;
}
