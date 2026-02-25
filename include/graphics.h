#pragma once

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
