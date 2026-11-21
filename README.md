# doomgeneric-web

Doom compiled to WebAssembly for a web page that draws the frames itself: the page ticks the
engine, sends it keys and reads its 320x200 framebuffer. No SDL, no sound, no music.

It is [doomgeneric](https://github.com/ozkl/doomgeneric) (Chocolate Doom made easy to port,
itself from id Software's Doom source) with a small platform layer of our own and one patch.
The Freewrite product simulator uses it for a hidden extra (type `idkfa` in the editor), and a
build of it ships with "Dear Santa", the simulator's widget on getfreewrite.com
(`freewrite-santa-doom.js` and `freewrite-santa-doom.wasm` in its `dist/santa/` bundle, where its
power button now and then starts it). Nothing here knows about either: pages use it only through the
interface below. This repository is the complete corresponding source for those builds.

## Licence

GNU General Public License, version 2 or (at your option) any later version, as the Doom source
is. See [LICENSE](LICENSE). This covers the engine, our patch, `web/src/doomgeneric_web.c`,
`web/js/api.js` and the built `doomgeneric.js` / `doomgeneric.wasm` (and their copies in Dear Santa's
bundle, `freewrite-santa-doom.js` / `.wasm`).

The game data is not part of it. Use [Freedoom](https://freedoom.github.io) (BSD-style licence,
its own `COPYING.txt`); `web/fetch-freedoom.py` downloads it. No id Software WAD or art is used or
needed.

## Upstream

- doomgeneric: https://github.com/ozkl/doomgeneric at commit
  `e257a09527062bfb986b6e5e0780839b6cbd5b71` (2026-10-11). This repository is that commit's
  history, with `web/patches/` applied to `doomgeneric/` and our files in `web/` on top.
  doomgeneric's own README is `README-doomgeneric.md`.
- Freedoom 0.13.0: `freedoom-0.13.0.zip` from the project's GitHub release, sha256
  `3f9b264f3e3ce503b4fb7f6bdcb1f419d93c7b546f4df3e874dd878db9688f59`.

## What we changed

- `web/patches/0001-no-screen-wipe.patch`: the screen "melt" between game states is turned off.
  doomgeneric runs it as a loop of its own until it finishes, which on a web page freezes the
  tab for about a second.
- `web/src/doomgeneric_web.c` (new, replaces the SDL `doomgeneric_emscripten.c`): no window or event
  loop; the page calls the exported functions below. Its clock stops while the page is paused,
  so a hidden tab doesn't come back to a game that ran on without it. `DG_SleepMs` returns at
  once: `dg_web_tick` only runs the engine once a new tic (1/35 s) is due.
- The build leaves out the SDL, Allegro and other platform files, the sound and music back ends
  and `mus2mid.c`, and sets the framebuffer to Doom's own 320x200 (`DOOMGENERIC_RESX/RESY`).

## Interface

`doomgeneric.js` is one classic script (load it with `<script src>`, from any origin) that defines
one global, `doomgenericWeb` (`web/js/api.js`, appended to the Emscripten loader):

```js
const wad = await (await fetch("freedoom1-e1.wad")).arrayBuffer();
const doom = await doomgenericWeb.start({
  wad, wasmUrl: "doomgeneric.wasm", args: ["-warp", "1", "1", "-skill", "3"], onExit: (status, msg) => {},
});
function frame() {
  if (doom.tick()) draw(doom.frame()); // { width: 320, height: 200, data: bytes B, G, R, X per pixel }
  requestAnimationFrame(frame);
}
const { KEY } = doomgenericWeb;
doom.key(true, KEY.UP);   // press; doom.key(false, KEY.UP) to release. Letters: "y".charCodeAt(0)
doom.pause(true);         // stop the game clock (e.g. on visibilitychange)
```

The wasm can live anywhere, under any name: it's compiled as it downloads when served as
`application/wasm`, and from its bytes otherwise (Emscripten's `instantiateWasm` hook).

Underneath, the wasm exports `dg_web_tick()`, `dg_web_key(pressed, key)`, `dg_web_pause(paused)`,
`dg_web_framebuffer()`, `dg_web_width()` and `dg_web_height()`.

## Build

With Nix (Emscripten 6.0.9 was used):

```
nix shell nixpkgs#emscripten -c ./build.sh [OUT_DIR]     # default OUT_DIR: dist/
python3 fetch-freedoom.py OUT_DIR [--full]
```

`web/build.sh` writes `doomgeneric.js` and `doomgeneric.wasm` to `OUT_DIR`. The compile
line it runs, for reference:

```
emcc -O2 -w -DNORMALUNIX -DLINUX -D_DEFAULT_SOURCE -DDOOMGENERIC_RESX=320 -DDOOMGENERIC_RESY=200 \
  -Idoomgeneric <engine sources, see web/build.sh> web/src/doomgeneric_web.c \
  -sMODULARIZE=1 -sEXPORT_NAME=createDoomgeneric -sENVIRONMENT=web \
  -sINVOKE_RUN=0 -sEXIT_RUNTIME=0 -sALLOW_MEMORY_GROWTH=1 -sINITIAL_MEMORY=33554432 \
  -sFORCE_FILESYSTEM=1 \
  -sEXPORTED_FUNCTIONS=_main,_dg_web_tick,_dg_web_key,_dg_web_pause,_dg_web_framebuffer,_dg_web_width,_dg_web_height \
  -sEXPORTED_RUNTIME_METHODS=callMain,FS,HEAPU8 --extern-post-js js/api.js -o OUT_DIR/doomgeneric.js
```

`web/fetch-freedoom.py` downloads the pinned Freedoom release (checking its sha256, cached in
`.cache/`) and writes `freedoom1-e1.wad`: Phase 1 cut to its first episode, with the sound
effects and music emptied (their names stay, so the engine finds every lump it asks for), and
the wall textures episode 1 doesn't use taken out of TEXTURE1, with the patches only they used
(the switches, skies and animated walls the engine looks up by name stay). That takes it from
28.8 MB to 10.9 MB (4.1 MB gzipped). Every map it keeps, E1M1 to E1M9, loads and runs
(`web/test/e2e/doom-maps.mjs` in the simulator). The title loop's demos that were recorded on
other episodes are swapped for the episode 1 one. `--full` also writes the
untouched `freedoom1.wad`.

Sizes of the build: `doomgeneric.wasm` 377 KB (165 KB gzipped), `doomgeneric.js` 65 KB (18 KB
gzipped).
