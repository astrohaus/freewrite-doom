// doomgeneric platform layer for a web page, without SDL.
//
// The page drives the engine: it calls dg_web_tick() from requestAnimationFrame, feeds keys in
// with dg_web_key(), and reads the 32-bit framebuffer (DOOMGENERIC_RESX x DOOMGENERIC_RESY,
// bytes B, G, R, X per pixel) after a tick that drew a frame. There is no sound.
//
// Copyright (C) 2026 Astrohaus. Licensed under the GNU GPL, version 2 or later, like the rest of
// the engine (see LICENSE).

#include <stdint.h>
#include <emscripten.h>

#include "doomgeneric.h"
#include "i_timer.h"

#define KEYQUEUE_SIZE 64

static unsigned short key_queue[KEYQUEUE_SIZE];
static unsigned int key_write = 0;
static unsigned int key_read = 0;

static int frame_ready = 0;
static int last_tic = -1;

// The clock stops while the page is paused (a hidden tab), so the game doesn't race through
// the missed time when it comes back.
static double paused_total = 0;
static double paused_at = -1;

static double now_ms(void)
{
    return emscripten_get_now();
}

void DG_Init(void)
{
}

void DG_DrawFrame(void)
{
    frame_ready = 1;
}

// The engine only sleeps while it waits for the next tic. A page can't block, and the page only
// calls dg_web_tick() once a tic is due, so this returns at once.
void DG_SleepMs(uint32_t ms)
{
    (void)ms;
}

uint32_t DG_GetTicksMs(void)
{
    double paused = paused_total + (paused_at >= 0 ? now_ms() - paused_at : 0);
    return (uint32_t)(now_ms() - paused);
}

int DG_GetKey(int *pressed, unsigned char *key)
{
    if (key_read == key_write)
        return 0;
    unsigned short data = key_queue[key_read];
    key_read = (key_read + 1) % KEYQUEUE_SIZE;
    *pressed = data >> 8;
    *key = data & 0xff;
    return 1;
}

void DG_SetWindowTitle(const char *title)
{
    (void)title;
}

// ---- the page's interface ----

int main(int argc, char **argv)
{
    doomgeneric_Create(argc, argv);
    return 0;
}

// Run the game up to now. Returns 1 if a new frame was drawn.
EMSCRIPTEN_KEEPALIVE
int dg_web_tick(void)
{
    if (paused_at >= 0)
        return 0;
    int tic = I_GetTime();
    if (tic == last_tic)
        return 0;
    last_tic = tic;
    frame_ready = 0;
    doomgeneric_Tick();
    return frame_ready;
}

// A key press (pressed = 1) or release (0), as a doomkeys.h code.
EMSCRIPTEN_KEEPALIVE
void dg_web_key(int pressed, int key)
{
    unsigned int next = (key_write + 1) % KEYQUEUE_SIZE;
    if (next == key_read)
        return; // full: drop it
    key_queue[key_write] = (unsigned short)(((pressed ? 1 : 0) << 8) | (key & 0xff));
    key_write = next;
}

EMSCRIPTEN_KEEPALIVE
void dg_web_pause(int paused)
{
    if (paused && paused_at < 0)
        paused_at = now_ms();
    else if (!paused && paused_at >= 0)
    {
        paused_total += now_ms() - paused_at;
        paused_at = -1;
    }
}

EMSCRIPTEN_KEEPALIVE
pixel_t *dg_web_framebuffer(void)
{
    return DG_ScreenBuffer;
}

EMSCRIPTEN_KEEPALIVE
int dg_web_width(void)
{
    return DOOMGENERIC_RESX;
}

EMSCRIPTEN_KEEPALIVE
int dg_web_height(void)
{
    return DOOMGENERIC_RESY;
}
