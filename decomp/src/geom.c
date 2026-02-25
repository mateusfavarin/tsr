#include <geom.h>
#include <inline_gte.h>

void Geom_LoadMatrixAndVector(const Mat3 *matrix, const Vec3 *vector)
{
    gte_SetLightMatrix(matrix);
    gte_ldbkdir(vector->x, vector->y, vector->z);
}

void Geom_ApplyVectorTransform_InPlace(const Vec3 *input, Vec3 *output)
{
    gte_loadVec(input, GTE_VECTOR_IR);
    gte_llirbk();

    *output = GTE_ReadMac();
    gte_ldtr(output->x, output->y, output->z);
}

void Geom_ApplyMatrixScaleTransform_InPlace(const SVec3 *scale, const Mat3 *source, Mat3 *destination)
{
    Vec3 transformedRows[3];
    const Mat3 scaleMatrix =
    {
        .m =
        {
            { scale->x, 0,        0        },
            { 0,        scale->y, 0        },
            { 0,        0,        scale->z },
        },
    };

    gte_SetColorMatrix(&scaleMatrix);

    gte_loadSVec(&source->row[0], GTE_VECTOR_IR);
    gte_lcv0();

    gte_loadSVec(&source->row[1], GTE_VECTOR_IR);
    transformedRows[0] = GTE_ReadMac();
    gte_lcv0_b();

    gte_loadSVec(&source->row[2], GTE_VECTOR_IR);
    transformedRows[1] = GTE_ReadMac();
    gte_lcir_b();

    transformedRows[2] = GTE_ReadMac();
    Geom_SetMatrixByRow(destination, transformedRows);
    gte_SetRotMatrix(destination);
}

void Geom_ApplyMatrixTransform_InPlace(const Mat3 *source, Mat3 *destination)
{
    Vec3 transformedColumns[3];
    SVec3 sourceColumn;

    sourceColumn.x = source->m[0][0];
    sourceColumn.y = source->m[1][0];
    sourceColumn.z = source->m[2][0];
    gte_loadSVec(&sourceColumn, GTE_VECTOR_IR);
    gte_llir();

    sourceColumn.x = source->m[0][1];
    sourceColumn.y = source->m[1][1];
    sourceColumn.z = source->m[2][1];
    gte_loadSVec(&sourceColumn, GTE_VECTOR_IR);
    transformedColumns[0] = GTE_ReadMac();
    gte_llir_b();

    sourceColumn.x = source->m[0][2];
    sourceColumn.y = source->m[1][2];
    sourceColumn.z = source->m[2][2];
    gte_loadSVec(&sourceColumn, GTE_VECTOR_IR);
    transformedColumns[1] = GTE_ReadMac();
    gte_llir_b();

    transformedColumns[2] = GTE_ReadMac();
    Geom_SetMatrixByCol(destination, transformedColumns);
    gte_SetRotMatrix(destination);
}

void Geom_ApplyMatrixTransform(const Mat3 *source, Mat3 *destination)
{
    Vec3 transformedColumns[3];
    SVec3 sourceColumn;

    sourceColumn.x = source->m[0][0];
    sourceColumn.y = source->m[1][0];
    sourceColumn.z = source->m[2][0];
    gte_loadSVec(&sourceColumn, GTE_VECTOR_IR);
    gte_llir();

    sourceColumn.x = source->m[0][1];
    sourceColumn.y = source->m[1][1];
    sourceColumn.z = source->m[2][1];
    gte_loadSVec(&sourceColumn, GTE_VECTOR_IR);
    transformedColumns[0] = GTE_ReadMac();
    gte_llir_b();

    sourceColumn.x = source->m[0][2];
    sourceColumn.y = source->m[1][2];
    sourceColumn.z = source->m[2][2];
    gte_loadSVec(&sourceColumn, GTE_VECTOR_IR);
    transformedColumns[1] = GTE_ReadMac();
    gte_llir_b();

    transformedColumns[2] = GTE_ReadMac();
    Geom_SetMatrixByCol(destination, transformedColumns);
}
