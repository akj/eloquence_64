#include <stdint.h>
#include <math.h>

/*
 * Eloquence DSP Pipeline (22.05 kHz)
 *
 * 11.025 kHz input -> 2x interpolated output
 * Adaptive slew smoothing
 * SVF-based presence shaping
 * Dual notch suppression (~7.5 / ~9 kHz)
 * Deterministic dither + hard limiting
 */

#define FS            22050.0f
#define PI            3.14159265358979323846f
#define TWO_PI        (2.0f * PI)

#define INT16_NORM    32768.0f
#define CLIP_LEVEL    32760.0f

#define HIST_SIZE     8
#define HIST_MASK     (HIST_SIZE - 1)

#define UINT32_SCALE  (1.0f / 4294967296.0f)

static float hist[HIST_SIZE];
static int hist_idx;

static float slew_state;
static float svf_state[2];

static float notch1[2];
static float notch2[2];

static uint32_t rng = 0x12345678;

__declspec(dllexport)
void process(int16_t * restrict in,
             int n_samples,
             int16_t * restrict out)
{
    const float hf_gain = 3.5f;
    const float out_gain = 0.80f;

    /* SVF (~6.6 kHz speech presence region) */
    const float g = tanf(PI * 6600.0f / FS);
    const float a1 = 1.0f / (1.0f + g * (g + 1.0f / 3.0f));
    const float a2 = g * a1;

    /* notch #1 (~7.5 kHz) */
    const float c1 = cosf(TWO_PI * 7500.0f / FS);
    const float k1 = 1.0f / (1.0f + sinf(TWO_PI * 7500.0f / FS));

    const float b01 = k1;
    const float b11 = -2.0f * c1 * k1;
    const float b21 = k1;

    const float a11 = -2.0f * c1 * k1;
    const float a21 = (1.0f - sinf(TWO_PI * 7500.0f / FS)) * k1;

    /* notch #2 (~9 kHz) */
    const float c2 = cosf(TWO_PI * 9000.0f / FS);
    const float k2 = 1.0f / (1.0f + sinf(TWO_PI * 9000.0f / FS));

    const float b02 = k2;
    const float b12 = -2.0f * c2 * k2;
    const float b22 = k2;

    const float a12 = -2.0f * c2 * k2;
    const float a22 = (1.0f - sinf(TWO_PI * 9000.0f / FS)) * k2;

    for (int i = 0; i < n_samples; i++) {

        hist[hist_idx] = (float)in[i];

        float h0 = hist[(hist_idx - 7) & HIST_MASK];
        float h1 = hist[(hist_idx - 6) & HIST_MASK];
        float h2 = hist[(hist_idx - 5) & HIST_MASK];
        float h3 = hist[(hist_idx - 4) & HIST_MASK];
        float h4 = hist[(hist_idx - 3) & HIST_MASK];
        float h5 = hist[(hist_idx - 2) & HIST_MASK];
        float h6 = hist[(hist_idx - 1) & HIST_MASK];
        float h7 = hist[hist_idx];

        hist_idx = (hist_idx + 1) & HIST_MASK;

        float s0 = h3;

        float s1 =
            h0 * -0.015f +
            h1 *  0.055f +
            h2 * -0.155f +
            h3 *  0.615f +
            h4 *  0.615f +
            h5 * -0.155f +
            h6 *  0.055f +
            h7 * -0.015f;

        for (int j = 0; j < 2; j++) {

            float x = (j == 0) ? s0 : s1;

            float diff = x - slew_state;

            float thr =
                150.0f *
                (0.2f + 0.8f * (fabsf(x) / INT16_NORM));

            float ratio = fabsf(diff) / (thr + 1e-6f);
            if (ratio > 1.0f) ratio = 1.0f;

            x = slew_state + diff * (0.4f + 0.6f * ratio);
            slew_state = x;

            /* SVF presence shaping */
            float v1 = a1 * svf_state[0] + a2 * (x - svf_state[1]);
            float v2 = svf_state[1] + g * v1;

            svf_state[0] = 2.0f * v1 - svf_state[0];
            svf_state[1] = 2.0f * v2 - svf_state[1];

            float y = x + v1 * hf_gain;

            /* notch #1 */
            float y1 = b01 * y + notch1[0];

            notch1[0] = b11 * y - a11 * y1 + notch1[1];
            notch1[1] = b21 * y - a21 * y1;

            /* notch #2 */
            float y2 = b02 * y1 + notch2[0];

            notch2[0] = b12 * y1 - a12 * y2 + notch2[1];
            notch2[1] = b22 * y1 - a22 * y2;

            rng = 1664525u * rng + 1013904223u;

            float final =
                (y2 + ((float)rng * UINT32_SCALE) * 0.5f)
                * out_gain;

            if (final > CLIP_LEVEL) final = CLIP_LEVEL;
            else if (final < -CLIP_LEVEL) final = -CLIP_LEVEL;

            out[i * 2 + j] =
                (int16_t)(final + (final > 0 ? 0.5f : -0.5f));
        }
    }
}

__declspec(dllexport)
void reset(void)
{
    for (int i = 0; i < HIST_SIZE; i++) {
        hist[i] = 0.0f;
    }

    hist_idx = 0;

    slew_state = 0.0f;

    svf_state[0] = 0.0f;
    svf_state[1] = 0.0f;

    notch1[0] = 0.0f;
    notch1[1] = 0.0f;

    notch2[0] = 0.0f;
    notch2[1] = 0.0f;
}