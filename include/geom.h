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

typedef union SVEC3
{
    struct
    {
        s16 x;
        s16 y;
        s16 z;
        s16 pad;
    };
    s16 v[4];
} SVEC3;

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

typedef struct Mat3
{
    s16 m[3][3];
} Mat3;

typedef struct Mat4
{
    Mat3 m;
    Vec3 t;
} Mat4;