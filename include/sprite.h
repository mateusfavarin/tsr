#pragma once

#include "types.h"
#include "geom.h"
#include "prim.h"

#define SPRITE_QUEUE_SIZE 64

typedef struct Sprite
{
    SVec3 pos;
    s16 otDepthBias;
    Point size;
    u16 orientFlags;
    u16 angle;
    u16 tpage;
    u16 clut;
    UV uv;
    u8 texWidth;
    u8 texHeight;
    ColorCode color;
} Sprite;

void Sprite_RenderQueue(const Sprite *sprites, s32 count);
void Sprite_AppendQueue(s32 x, s32 y, s32 z, s16 sizeX, s16 sizeY, u16 orientFlags, u16 angle, u8 u, u8 v,
                        u8 texWidth, u8 texHeight, u8 red, u8 green, u8 blue, s32 textureSlot,
                        u16 clutOffset, u32 flags, s16 otDepthBias);
void Sprite_ClearQueue();
void Sprite_FlushQueue();
