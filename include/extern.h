#pragma once

#include "heap.h"
#include "axe.h"
#include "graphics.h"
#include "math.h"
#include "sprite.h"

int printf(char *fmt, ...);
void *memset(void* dst, unsigned char ch, int count);
void *memcpy(void* dst, const void* src, int n);

extern HeapBlock g_heapStart;

extern s16 g_axeChunkCount;
extern AxeChunk *g_axeChunkStream;
extern u16 g_axeSkipFaceSize;
extern u32 *g_axePtrSkipFaceSize;
extern AxeHeader *g_ptrAxe;
extern u8 g_axeScratchpadDataBeg[];

extern s16 g_activeViewport_ClipMinX;
extern s16 g_activeViewport_ClipMinY;
extern s16 g_activeViewport_ClipMaxX;
extern s16 g_activeViewport_ClipMaxY;

extern s16 g_sinTable[ANG_RANGE];

extern Mat4 g_cameraMatrix;
extern Vec3 g_cameraPosCoarse;

extern s16 *g_depthToOTDepthLUT;
extern s32 g_otDepthLimit;
extern void *g_primMem;
extern u8 *g_otPtr;
extern u8 *g_primMemEnd;
extern TextureSlot g_textureSlot[];

extern u16 g_spriteYScale;
extern Sprite g_spriteQueue[SPRITE_QUEUE_SIZE];
extern u32 g_spriteQueueSize;
