#pragma once

#define ANG_RANGE 0x1000         // 0-360
#define ANG_TWO_PI 0x1000        // 360
#define ANG_PI (ANG_TWO_PI / 2)  // 180
#define ANG_HALF_PI (ANG_PI / 2) // 90

#define ANG_MODULO_TWO_PI(x) ((x) & (ANG_TWO_PI - 1))   // ang % 360
#define ANG_MODULO_PI(x) ((x) & (ANG_PI - 1))           // ang % 180
#define ANG_MODULO_HALF_PI(x) ((x) & (ANG_HALF_PI - 1)) // ang % 90

#define ANG(x) ANG_MODULO_TWO_PI(((short)((((float) x) * ANG_TWO_PI) / 360))) // works for any float, pos or neg

#define IS_ANG_FIRST_OR_THIRD_QUADRANT(x) (((x) & ANG_HALF_PI) == 0) // [0, 90[ \/ [180, 270[
#define IS_ANG_THIRD_OR_FOURTH_QUADRANT(x) ((x) & ANG_PI)            // [180, 360[

#define FRACTIONAL_BITS 12
#define FP_ONE (1 << FRACTIONAL_BITS)
#define FP_INT(x) ((x) >> FRACTIONAL_BITS)
#define FP_MULT(x, y) (((x) * (y)) >> FRACTIONAL_BITS)
#define FP_DIV(x, y) (((x) << FRACTIONAL_BITS) / (y))
#define FP(x) ((int)(((float)(x)) * FP_ONE))