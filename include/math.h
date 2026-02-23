#pragma once

#include "types.h"

typedef union SVec3
{
    struct
    {
        s16 x;
        s16 y;
        s16 z;
    };
    s16 v[3];
} SVec3;

typedef union Vec3
{
    struct
    {
        s32 x;
        s32 y;
        s32 z;
    };
    s32 v[3];
} Vec3;