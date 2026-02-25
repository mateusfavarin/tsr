#pragma once

#include "types.h"
#include "prim.h"

typedef struct PointQuad
{
    Point p[4];
} PointQuad;

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

typedef union Mat3
{
    s16 m[3][3];
    SVec3 row[3];
} Mat3;

typedef struct Mat4
{
    Mat3 m;
    Vec3 t;
} Mat4;

static force_inline void Geom_SetMatrixByRow(Mat3 *matrix, const Vec3 rows[3])
{
    for (u32 i = 0; i < 3; i++)
    {
        for (u32 j = 0; j < 3; j++)
        {
            matrix->m[i][j] = (s16) rows[i].v[j];
        }
    }
}

static force_inline void Geom_SetMatrixByCol(Mat3 *matrix, const Vec3 cols[3])
{
    for (u32 i = 0; i < 3; i++)
    {
        for (u32 j = 0; j < 3; j++)
        {
            matrix->m[j][i] = (s16) cols[i].v[j];
        }
    }
}

void Geom_LoadMatrixAndVector(const Mat3 *matrix, const Vec3 *vector);
void Geom_ApplyVectorTransform_InPlace(const Vec3 *input, Vec3 *output);
void Geom_ApplyMatrixScaleTransform_InPlace(const SVec3 *scale, const Mat3 *source, Mat3 *destination);
void Geom_ApplyMatrixTransform_InPlace(const Mat3 *source, Mat3 *destination);
void Geom_ApplyMatrixTransform(const Mat3 *source, Mat3 *destination);
