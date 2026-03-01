#pragma once

#include "types.h"

typedef enum TexPage
{
    TEXPAGE_TRANSPARENCY_BITS = 0x60,
    TEXPAGE_TRANSPARENCY_OPAQUE = 0x60,
} TexPage;

typedef enum GraphicsOtOffset
{
    GRAPHICS_OT_OFFSET_SKYBOX = 0x1038,
} GraphicsOtOffset;

typedef enum GraphicsScreenDimension
{
    GRAPHICS_SCREEN_HEIGHT = 0xF0,
    GRAPHICS_SCREEN_WIDTH = 0x200,
} GraphicsScreenDimension;

typedef enum GraphicsMinOtz
{
    GRAPHICS_MIN_OTZ_SKYBOX = 0x24,
    GRAPHICS_MIN_OTZ_SPRITE = 0x27,
} GraphicsMinOtz;

typedef struct TextureSlot
{
    u16 tpage;
    u16 clut;
    u16 vramX;
    u16 vramY;
    u16 texMode;
    u8 field_0x0A;
    u8 field_0x0B;
    u8 field_0x0C;
    u8 field_0x0D;
    u8 field_0x0E;
    u8 field_0x0F;
} TextureSlot;
