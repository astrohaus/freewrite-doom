#!/usr/bin/env python3
"""Fetch Freedoom Phase 1 (pinned release, checked by sha256) and write a trimmed copy.

    python3 fetch-freedoom.py OUT_DIR [--full]

Writes OUT_DIR/freedoom1-e1.wad: Freedoom Phase 1 cut down to its first episode, with no sound
effects or music (they are kept as empty lumps, so the engine still finds every name it looks
up), and without the wall textures and patches episode 1 doesn't use. With --full, also writes the untouched OUT_DIR/freedoom1.wad.

Freedoom is free software under a BSD-style licence (COPYING.txt in the release, copied next to
the WADs as FREEDOOM-COPYING.txt). See https://freedoom.github.io.
"""

import hashlib
import io
import os
import re
import struct
import sys
import urllib.request
import zipfile

VERSION = "0.13.0"
URL = f"https://github.com/freedoom/freedoom/releases/download/v{VERSION}/freedoom-{VERSION}.zip"
SHA256 = "3f9b264f3e3ce503b4fb7f6bdcb1f419d93c7b546f4df3e874dd878db9688f59"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", f"freedoom-{VERSION}.zip")

# The ten lumps that follow a map's marker (THINGS ... BLOCKMAP).
MAP_LUMPS = 10


def fetch():
    if os.path.exists(CACHE):
        data = open(CACHE, "rb").read()
        if hashlib.sha256(data).hexdigest() == SHA256:
            return data
    print(f"downloading {URL}", file=sys.stderr)
    with urllib.request.urlopen(URL) as r:
        data = r.read()
    got = hashlib.sha256(data).hexdigest()
    if got != SHA256:
        sys.exit(f"sha256 mismatch for {URL}: {got}, expected {SHA256}")
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    open(CACHE, "wb").write(data)
    return data


def read_wad(data):
    ident, n, off = struct.unpack("<4sii", data[:12])
    lumps = []
    for i in range(n):
        pos, size, name = struct.unpack("<ii8s", data[off + 16 * i : off + 16 * i + 16])
        lumps.append((name.rstrip(b"\0").decode("ascii"), data[pos : pos + size]))
    return ident, lumps


def write_wad(ident, lumps):
    out = io.BytesIO()
    out.write(b"\0" * 12)
    dirents = []
    for name, body in lumps:
        dirents.append((out.tell() if body else 0, len(body), name))
        out.write(body)
    diroff = out.tell()
    for pos, size, name in dirents:
        out.write(struct.pack("<ii8s", pos, size, name.encode("ascii")))
    out.seek(0)
    out.write(struct.pack("<4sii", ident, len(lumps), diroff))
    return out.getvalue()


def trim(ident, lumps):
    """Episode 1 only, silent."""
    out = []
    skip = 0
    demos = {}
    for name, body in lumps:
        if skip:
            skip -= 1
            continue
        m = re.fullmatch(r"E(\d)M\d", name)
        if m and m.group(1) != "1":
            skip = MAP_LUMPS
            continue
        if name.startswith(("DS", "DP", "D_")) or name in ("GENMIDI", "DMXGUS", "DMXGUSC"):
            body = b""  # sounds and music: keep the name, drop the data
        if re.fullmatch(r"DEMO\d", name):
            demos[name] = body
        out.append([name, body])
    # The title loop plays DEMO1-3 (DEMO4 isn't played without episode 4). They're recorded on
    # other episodes' maps; play the episode 1 one instead (its header: version, skill, episode, map).
    e1 = next((b for n, b in sorted(demos.items()) if len(b) > 3 and b[2] == 1), None)
    for lump in out:
        if lump[0] in demos and lump[1] and lump[1][2] != 1:
            lump[1] = e1 or b""
    return write_wad(ident, drop_unused_textures(out))


# Textures the engine looks up by name besides the maps' walls: the episode 1 switches
# (p_switch.c, both states), the skies (g_game.c), and the animated walls (p_spec.c), which run
# through every texture between their first and last in TEXTURE1's order.
SWITCHES = "BRCOM BRN1 BRN2 BRNGN BROWN COMM COMP DIRT EXIT GRAY GRAY1 METAL PIPE SLAD STARG STON1 STON2 STONE STRTN".split()
SKIES = ["SKY1", "SKY2", "SKY3", "SKY4"]
ANIMS = [("BLODGR1", "BLODGR4"), ("SLADRIP1", "SLADRIP3"), ("BLODRIP1", "BLODRIP4"), ("FIREWALA", "FIREWALL"),
         ("GSTFONT1", "GSTFONT3"), ("FIRELAV3", "FIRELAVA"), ("FIREMAG1", "FIREMAG3"), ("FIREBLU1", "FIREBLU2"),
         ("ROCKRED1", "ROCKRED3"), ("BFALL1", "BFALL4"), ("SFALL1", "SFALL4"), ("WFALL1", "WFALL4"), ("DBRAIN1", "DBRAIN4")]


def lump_name(b):
    return b.rstrip(b"\0").decode("ascii").upper()


def drop_unused_textures(lumps):
    """Keep only the wall textures the kept maps (and the engine) use, and the patches those are
    made of. The engine finds textures by name, so the rest can go; it finds patches by their
    index in PNAMES, which stays whole (a missing patch is only an error if a kept texture uses it)."""
    used = set(SKIES)
    for sw in SWITCHES:
        used |= {"SW1" + sw, "SW2" + sw}
    for name, body in lumps:
        if name == "SIDEDEFS":
            for o in range(0, len(body), 30):
                for a in (4, 12, 20):
                    used.add(lump_name(body[o + a : o + a + 8]))
    pn = next(b for n, b in lumps if n == "PNAMES")
    pnames = [lump_name(pn[4 + 8 * i : 12 + 8 * i]) for i in range(struct.unpack("<i", pn[:4])[0])]
    keep_patches = set()
    for lump in lumps:
        if lump[0] not in ("TEXTURE1", "TEXTURE2"):
            continue
        body = lump[1]
        n = struct.unpack("<i", body[:4])[0]
        texs = []
        for o in struct.unpack(f"<{n}i", body[4 : 4 + 4 * n]):
            npatch = struct.unpack("<h", body[o + 20 : o + 22])[0]
            texs.append((lump_name(body[o : o + 8]), body[o : o + 22 + 10 * npatch]))
        order = [t for t, _ in texs]
        keep = set(used)
        for a, b in ANIMS:
            if a in order and b in order:
                keep |= set(order[order.index(a) : order.index(b) + 1])
        texs = [(t, raw) for t, raw in texs if t in keep]
        for _, raw in texs:
            for k in range(struct.unpack("<h", raw[20:22])[0]):
                keep_patches.add(pnames[struct.unpack("<h", raw[26 + 10 * k : 28 + 10 * k])[0]])
        offs, at, data = [], 4 + 4 * len(texs), b""
        for _, raw in texs:
            offs.append(at + len(data))
            data += raw
        lump[1] = struct.pack("<i", len(texs)) + struct.pack(f"<{len(texs)}i", *offs) + data
    out, in_patches = [], False
    for name, body in lumps:
        if name == "P_START":
            in_patches = True
        elif name == "P_END":
            in_patches = False
        elif in_patches and not name.endswith(("_START", "_END")) and name.upper() not in keep_patches:
            continue
        out.append((name, body))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    out_dir = args[0]
    os.makedirs(out_dir, exist_ok=True)
    z = zipfile.ZipFile(io.BytesIO(fetch()))
    wad = z.read(f"freedoom-{VERSION}/freedoom1.wad")
    open(os.path.join(out_dir, "FREEDOOM-COPYING.txt"), "wb").write(z.read(f"freedoom-{VERSION}/COPYING.txt"))
    if "--full" in sys.argv:
        open(os.path.join(out_dir, "freedoom1.wad"), "wb").write(wad)
    ident, lumps = read_wad(wad)
    small = trim(ident, lumps)
    open(os.path.join(out_dir, "freedoom1-e1.wad"), "wb").write(small)
    print(f"freedoom1.wad {len(wad)} bytes -> freedoom1-e1.wad {len(small)} bytes", file=sys.stderr)


if __name__ == "__main__":
    main()
