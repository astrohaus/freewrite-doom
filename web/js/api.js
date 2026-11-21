// doomgeneric-web's interface for a page, appended to the Emscripten loader (build.sh passes it
// as --extern-post-js), so the one classic script defines one global:
//
//   <script src="doomgeneric.js"></script>
//   const doom = await doomgenericWeb.start({ wad, wasmUrl: "doomgeneric.wasm" });
//   // each animation frame:
//   if (doom.tick()) draw(doom.frame());   // frame(): { width, height, data: B,G,R,X bytes }
//   doom.key(true, doomgenericWeb.KEY.UP); doom.key(false, doomgenericWeb.KEY.UP);
//   doom.pause(true);                      // the game clock stops until pause(false)
//
// The wasm can come from any URL and server: it's compiled as it streams when served as
// application/wasm, and from its bytes otherwise (any other name or content type).
//
// Copyright (C) 2026 Astrohaus. GNU GPL, version 2 or later (see LICENSE).

(function () {
  // doomkeys.h. Letters and digits are their lowercase ASCII codes ("y".charCodeAt(0)).
  var KEY = {
    RIGHT: 0xae, LEFT: 0xac, UP: 0xad, DOWN: 0xaf,
    STRAFE_L: 0xa0, STRAFE_R: 0xa1, USE: 0xa2, FIRE: 0xa3,
    ESCAPE: 27, ENTER: 13, TAB: 9, BACKSPACE: 0x7f,
    RSHIFT: 0x80 + 0x36, RCTRL: 0x80 + 0x1d, RALT: 0x80 + 0x38,
    MINUS: 0x2d, EQUALS: 0x3d,
    F1: 0x80 + 0x3b, F2: 0x80 + 0x3c, F3: 0x80 + 0x3d, F4: 0x80 + 0x3e, F5: 0x80 + 0x3f,
    F6: 0x80 + 0x40, F7: 0x80 + 0x41, F8: 0x80 + 0x42, F9: 0x80 + 0x43, F10: 0x80 + 0x44,
    F11: 0x80 + 0x57,
  };

  // wad: the IWAD's bytes (ArrayBuffer or Uint8Array). wasmUrl: where doomgeneric.wasm is.
  // args: extra command-line arguments (e.g. ["-warp", "1", "1", "-skill", "3"]).
  // onExit(status, message): the engine quit or failed.
  async function start(opts) {
    var exited = false;
    var done = function (status, message) {
      if (exited) return;
      exited = true;
      if (opts.onExit) opts.onExit(status, message);
    };
    var wasm = fetch(opts.wasmUrl).then(function (r) {
      if (!r.ok) throw new Error(opts.wasmUrl + ": " + r.status);
      return r;
    });
    // Compiled while it downloads when it's served as application/wasm; from its bytes otherwise.
    var instantiate = function (r, imports) {
      var copy = r.clone();
      var fromBytes = function () {
        return copy.arrayBuffer().then(function (b) { return WebAssembly.instantiate(b, imports); });
      };
      if (!WebAssembly.instantiateStreaming) return fromBytes();
      return WebAssembly.instantiateStreaming(r, imports).catch(fromBytes);
    };
    var M = await createDoomgeneric({
      print: opts.print || function () {},
      printErr: opts.printErr || function () {},
      onExit: function (status) { done(status); },
      instantiateWasm: function (imports, ok) {
        wasm
          .then(function (r) { return instantiate(r, imports); })
          .then(function (r) { ok(r.instance, r.module); })
          .catch(function (e) { done(-1, String(e && e.message || e)); });
        return {};
      },
    });
    var wad = opts.wad instanceof Uint8Array ? opts.wad : new Uint8Array(opts.wad);
    M.FS.writeFile("/doom.wad", wad);
    try {
      M.callMain(["-iwad", "/doom.wad"].concat(opts.args || []));
    } catch (e) {
      done(e && e.status != null ? e.status : -1, String(e && e.message || e));
    }
    var width = M._dg_web_width();
    var height = M._dg_web_height();
    var fail = function (e) {
      done(e && e.status != null ? e.status : -1, String(e && e.message || e));
    };
    return {
      width: width,
      height: height,
      get exited() { return exited; },
      // Runs the game up to now; true when it drew a new frame.
      tick: function () {
        if (exited) return false;
        try {
          return M._dg_web_tick() === 1;
        } catch (e) {
          fail(e);
          return false;
        }
      },
      key: function (down, code) {
        if (!exited) M._dg_web_key(down ? 1 : 0, code);
      },
      pause: function (paused) {
        if (!exited) M._dg_web_pause(paused ? 1 : 0);
      },
      // The current frame, as a view into the engine's memory: copy it if you keep it.
      frame: function () {
        var p = M._dg_web_framebuffer();
        return { width: width, height: height, data: M.HEAPU8.subarray(p, p + width * height * 4) };
      },
    };
  }

  globalThis.doomgenericWeb = { KEY: KEY, start: start };
})();
