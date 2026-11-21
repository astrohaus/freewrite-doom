#!/usr/bin/env bash
# Build doomgeneric-web: compile this repository's doomgeneric (web/patches already applied) with
# our platform layer (web/src, web/js) to WebAssembly.
#
#   ./build.sh [OUT_DIR]        # default OUT_DIR: ./dist
#
# Needs Emscripten's emcc on PATH (with Nix: nix shell nixpkgs#emscripten -c ./build.sh).
# Writes OUT_DIR/doomgeneric.js (a classic script: the Emscripten loader with js/api.js, the small
# interface pages use, appended) and OUT_DIR/doomgeneric.wasm.
set -euo pipefail


here=$(cd "$(dirname "$0")" && pwd)
out=$(mkdir -p "${1:-$here/dist}" && cd "${1:-$here/dist}" && pwd)

# The engine's source is this repository's doomgeneric/ folder, with web/patches already applied.

# 2. compile: the engine without its SDL, sound or other platform files, plus src/doomgeneric_web.c
src="$here/../doomgeneric"
files="dummy am_map doomdef doomstat dstrings d_event d_items d_iwad d_loop d_main d_mode d_net
  f_finale f_wipe g_game hu_lib hu_stuff info i_cdmus i_endoom i_joystick i_scale i_sound i_system
  i_timer memio m_argv m_bbox m_cheat m_config m_controls m_fixed m_menu m_misc m_random p_ceilng
  p_doors p_enemy p_floor p_inter p_lights p_map p_maputl p_mobj p_plats p_pspr p_saveg p_setup
  p_sight p_spec p_switch p_telept p_tick p_user r_bsp r_data r_draw r_main r_plane r_segs r_sky
  r_things sha1 sounds statdump st_lib st_stuff s_sound tables v_video wi_stuff w_checksum w_file
  w_main w_wad z_zone w_file_stdc i_input i_video doomgeneric"
sources=()
for f in $files; do sources+=("$src/$f.c"); done
sources+=("$here/src/doomgeneric_web.c")

emcc -O2 -w \
  -DNORMALUNIX -DLINUX -D_DEFAULT_SOURCE \
  -DDOOMGENERIC_RESX=320 -DDOOMGENERIC_RESY=200 \
  -I"$src" \
  -ffile-prefix-map="$src"=doomgeneric -ffile-prefix-map="$here"=. \
  "${sources[@]}" \
  -sMODULARIZE=1 -sEXPORT_NAME=createDoomgeneric \
  -sENVIRONMENT=web -sINVOKE_RUN=0 -sEXIT_RUNTIME=0 \
  -sALLOW_MEMORY_GROWTH=1 -sINITIAL_MEMORY=33554432 -sFORCE_FILESYSTEM=1 \
  -sEXPORTED_FUNCTIONS=_main,_dg_web_tick,_dg_web_key,_dg_web_pause,_dg_web_framebuffer,_dg_web_width,_dg_web_height \
  -sEXPORTED_RUNTIME_METHODS=callMain,FS,HEAPU8 \
  --extern-post-js "$here/js/api.js" \
  -o "$out/doomgeneric.js"
ls -l "$out"
