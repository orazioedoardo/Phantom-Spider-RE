#!/usr/bin/env python3
"""The files the web build packs in the game's data, kept in the build folder: the JAR, and the SoundFont with only
what the music plays (soundfont.py). Run by web/CMakeLists.txt on every build.

    web/files.py JAR SOUNDFONT OUT

JAR and SOUNDFONT are the files given to the build; OUT gets Phantom_Spider_s40v2.jar and soundfont.sf2. They're
redone when the files given change, and kept when they're gone: once built, the JAR and the SoundFont can be removed
(until OUT is). A file is only rewritten when it changes, which is what relinks the game (see build.rs).
"""

import sys
from pathlib import Path

sys.dont_write_bytecode = True   # no __pycache__ in the source folder for soundfont.py
import soundfont   # noqa: E402

jar, sf2, out = (Path(a) for a in sys.argv[1:4])
out.mkdir(parents=True, exist_ok=True)
kept_jar, kept_sf2 = out / "Phantom_Spider_s40v2.jar", out / "soundfont.sf2"


def write_if_changed(path, data):
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


if jar.is_file():
    write_if_changed(kept_jar, jar.read_bytes())
elif not kept_jar.exists():
    sys.exit(f"Phantom_Spider_s40v2.jar isn't at {jar}: give it to the build (PHANTOM_SPIDER_JAR)")

# The SoundFont is redone when the one given, the JAR (its music) or soundfont.py is newer than when it was last made
# (a stamp: the SoundFont itself is only rewritten when it changes)
stamp = out / ".soundfont-made"
if sf2.is_file():
    sources = [sf2, kept_jar, Path(soundfont.__file__)]
    if not kept_sf2.exists() or not stamp.exists() or stamp.stat().st_mtime < max(p.stat().st_mtime for p in sources):
        data, presets, instruments, samples = soundfont.make(sf2, kept_jar)
        write_if_changed(kept_sf2, data)
        stamp.touch()
        print(f"{kept_sf2}: {presets} presets, {instruments} instruments, {samples} samples, "
              f"{len(data) / 1048576:.1f} MB (from {sf2.stat().st_size / 1048576:.1f} MB)")
elif not kept_sf2.exists():
    sys.exit(f"The SoundFont isn't at {sf2}: give one to the build (PHANTOM_SPIDER_SOUNDFONT)")
