#!/usr/bin/env python3
"""A SoundFont with only what the game's music plays: the presets its MIDI files use, the zones (instruments, then
samples) for the notes they play, and those samples. Everything kept is copied unchanged, so the music sounds the same,
from a file a fraction of the size (a General MIDI SoundFont has every instrument).

    web/soundfont.py <soundfont.sf2> <Phantom_Spider_s40v2.jar> <out.sf2>

The MIDI files are the JAR's. A preset is looked up as rustysynth does: by bank and program, the bank being 128 (plus
bank select) on the percussion channel, 10.
"""

import struct
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

# ------------------------------------------------------------------------------------------------- the music


def read_vlq(data, i):
    value = 0
    while True:
        byte = data[i]
        i += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, i


def notes_by_preset(midi, used):
    """Adds to used[(bank, program)] the keys the MIDI file plays with each preset."""
    if midi[:4] != b"MThd":
        raise ValueError("not a MIDI file")
    tracks = int.from_bytes(midi[10:12], "big")
    i = 8 + int.from_bytes(midi[4:8], "big")
    events = []   # (time, order, channel, status, data): merged across tracks, in time order
    for _ in range(tracks):
        if midi[i:i + 4] != b"MTrk":
            raise ValueError("damaged MIDI file")
        end = i + 8 + int.from_bytes(midi[i + 4:i + 8], "big")
        i += 8
        time, status = 0, None
        while i < end:
            delta, i = read_vlq(midi, i)
            time += delta
            if midi[i] == 0xFF:   # meta event
                length, i = read_vlq(midi, i + 2)
                i += length
                status = None
                continue
            if midi[i] in (0xF0, 0xF7):   # system exclusive
                length, i = read_vlq(midi, i + 1)
                i += length
                status = None
                continue
            if midi[i] & 0x80:
                status = midi[i]
                i += 1
            size = 1 if status & 0xF0 in (0xC0, 0xD0) else 2
            events.append((time, len(events), status & 0x0F, status & 0xF0, midi[i:i + size]))
            i += size
        i = end
    program = defaultdict(int)
    bank = defaultdict(int)
    for _, _, channel, kind, data in sorted(events):
        if kind == 0xC0:
            program[channel] = data[0]
        elif kind == 0xB0 and data[0] == 0:   # bank select
            bank[channel] = data[1]
        elif kind == 0x90 and data[1] > 0:
            percussion = 128 if channel == 9 else 0
            used[(bank[channel] + percussion, program[channel])].add(data[0])


# ------------------------------------------------------------------------------------------------- SoundFonts

def chunks(data):
    """The RIFF chunks in data: {id: bytes}, and the LISTs as {"LIST:<type>": bytes}."""
    out, i = {}, 0
    while i + 8 <= len(data):
        cid, size = data[i:i + 4].decode("latin-1"), struct.unpack_from("<I", data, i + 4)[0]
        body = data[i + 8:i + 8 + size]
        if cid == "LIST":
            out["LIST:" + body[:4].decode("latin-1")] = body[4:]
        else:
            out[cid] = body
        i += 8 + size + (size & 1)
    return out


def chunk(cid, body):
    return cid.encode("latin-1") + struct.pack("<I", len(body)) + body + (b"\0" if len(body) & 1 else b"")


def records(body, size):
    return [body[i:i + size] for i in range(0, len(body) - size + 1, size)]


GEN_KEY_RANGE, GEN_INSTRUMENT, GEN_SAMPLE_ID = 43, 41, 53


def zones(bags, gens, mods, first, last):
    """The zones of a preset or instrument, bags[first:last]: (generators, modulators) each, as raw records."""
    out = []
    for b in range(first, last):
        g0, m0 = struct.unpack_from("<HH", bags[b])
        g1, m1 = struct.unpack_from("<HH", bags[b + 1])
        out.append((gens[g0:g1], mods[m0:m1]))
    return out


def generator(gens, oper):
    for g in gens:
        if struct.unpack_from("<H", g)[0] == oper:
            return g[2:4]
    return None


def key_range(gens):
    amount = generator(gens, GEN_KEY_RANGE)
    return (0, 127) if amount is None else (amount[0], amount[1])


def link(gens, oper):
    """The index a zone refers to (an instrument or a sample), or None for a global zone."""
    amount = generator(gens, oper)
    return None if amount is None else struct.unpack("<H", amount)[0]


def relink(gens, oper, index):
    return [g[:2] + struct.pack("<H", index) if struct.unpack_from("<H", g)[0] == oper else g for g in gens]


def subset(sf2, used):
    riff = chunks(sf2[12:])
    sdta, pdta = chunks(riff["LIST:sdta"]), chunks(riff["LIST:pdta"])
    smpl, sm24 = sdta["smpl"], sdta.get("sm24")
    phdr, pbag, pmod, pgen = records(pdta["phdr"], 38), records(pdta["pbag"], 4), records(pdta["pmod"], 10), records(pdta["pgen"], 4)
    inst, ibag, imod, igen = records(pdta["inst"], 22), records(pdta["ibag"], 4), records(pdta["imod"], 10), records(pdta["igen"], 4)
    shdr = records(pdta["shdr"], 46)

    def keep_zones(all_zones, oper, notes):
        """The zones that play some of notes (with the global zone, if any), and the indexes they refer to with the
        notes they play"""
        kept, refs = [], defaultdict(set)
        for z, (gens, mods) in enumerate(all_zones):
            target = link(gens, oper)
            if target is None:
                if z == 0:
                    kept.append((gens, mods))   # global zone
                continue
            lo, hi = key_range(gens)
            played = {n for n in notes if lo <= n <= hi}
            if played:
                kept.append((gens, mods))
                refs[target] |= played
        return kept, refs

    # Presets
    presets, instrument_notes = [], defaultdict(set)
    for p in range(len(phdr) - 1):
        program, bank = struct.unpack_from("<HH", phdr[p], 20)
        notes = used.get((bank, program))
        if not notes:
            continue
        first, last = struct.unpack_from("<H", phdr[p], 24)[0], struct.unpack_from("<H", phdr[p + 1], 24)[0]
        kept, refs = keep_zones(zones(pbag, pgen, pmod, first, last), GEN_INSTRUMENT, notes)
        presets.append((phdr[p], kept))
        for i, n in refs.items():
            instrument_notes[i] |= n
    missing = set(used) - {struct.unpack_from("<HH", h, 20)[::-1] for h, _ in presets}
    if missing:
        sys.exit(f"The SoundFont has no presets for (bank, program) {sorted(missing)}")

    # Instruments
    instruments, sample_ids = {}, set()
    for i in sorted(instrument_notes):
        first, last = struct.unpack_from("<H", inst[i], 20)[0], struct.unpack_from("<H", inst[i + 1], 20)[0]
        kept, refs = keep_zones(zones(ibag, igen, imod, first, last), GEN_SAMPLE_ID, instrument_notes[i])
        instruments[i] = kept
        sample_ids |= set(refs)
    # with the other half of stereo samples
    for s in list(sample_ids):
        link_index, sample_type = struct.unpack_from("<HH", shdr[s], 42)
        if sample_type & 0x0E and link_index < len(shdr) - 1:
            sample_ids.add(link_index)

    # Samples: each one's data, followed by 46 zero points (as the specification asks)
    new_sample = {s: n for n, s in enumerate(sorted(sample_ids))}
    new_smpl, new_sm24, new_shdr = bytearray(), bytearray(), []
    for s in sorted(sample_ids):
        name = shdr[s][:20]
        start, end, loop_start, loop_end = struct.unpack_from("<IIII", shdr[s], 20)
        rest = shdr[s][36:42]
        link_index, sample_type = struct.unpack_from("<HH", shdr[s], 42)
        offset = len(new_smpl) // 2
        new_smpl += smpl[start * 2:end * 2] + bytes(46 * 2)
        if sm24 is not None:
            new_sm24 += sm24[start:end] + bytes(46)
        moved = lambda point: point - start + offset
        link_index = new_sample.get(link_index, 0)
        new_shdr.append(name + struct.pack("<IIII", moved(start), moved(end), moved(loop_start), moved(loop_end))
                        + rest + struct.pack("<HH", link_index, sample_type))
    new_shdr.append(shdr[-1][:20] + bytes(26))   # EOS

    # The lists of zones, rebuilt with the new indexes
    def write_zones(entries, oper, new_index, bags, gens, mods):
        for gens_in, mods_in in entries:
            bags.append(struct.pack("<HH", len(gens), len(mods)))
            target = link(gens_in, oper)
            gens += gens_in if target is None else relink(gens_in, oper, new_index[target])
            mods += mods_in

    new_instrument = {i: n for n, i in enumerate(sorted(instruments))}
    new_inst, new_ibag, new_igen, new_imod = [], [], [], []
    for i in sorted(instruments):
        new_inst.append(inst[i][:20] + struct.pack("<H", len(new_ibag)))
        write_zones(instruments[i], GEN_SAMPLE_ID, new_sample, new_ibag, new_igen, new_imod)
    new_inst.append(inst[-1][:20] + struct.pack("<H", len(new_ibag)))   # EOI
    new_phdr, new_pbag, new_pgen, new_pmod = [], [], [], []
    for header, kept in presets:
        new_phdr.append(header[:24] + struct.pack("<H", len(new_pbag)) + header[26:])
        write_zones(kept, GEN_INSTRUMENT, new_instrument, new_pbag, new_pgen, new_pmod)
    new_phdr.append(phdr[-1][:24] + struct.pack("<H", len(new_pbag)) + phdr[-1][26:])   # EOP
    # the terminal records
    new_pbag.append(struct.pack("<HH", len(new_pgen), len(new_pmod)))
    new_ibag.append(struct.pack("<HH", len(new_igen), len(new_imod)))
    new_pgen.append(bytes(4))
    new_igen.append(bytes(4))
    new_pmod.append(bytes(10))
    new_imod.append(bytes(10))

    pdta_out = b"pdta" + b"".join(chunk(cid, b"".join(body)) for cid, body in (
        ("phdr", new_phdr), ("pbag", new_pbag), ("pmod", new_pmod), ("pgen", new_pgen),
        ("inst", new_inst), ("ibag", new_ibag), ("imod", new_imod), ("igen", new_igen), ("shdr", new_shdr)))
    sdta_out = b"sdta" + chunk("smpl", bytes(new_smpl)) + (chunk("sm24", bytes(new_sm24)) if sm24 is not None else b"")
    body = b"sfbk" + chunk("LIST", b"INFO" + riff["LIST:INFO"]) + chunk("LIST", sdta_out) + chunk("LIST", pdta_out)
    return b"RIFF" + struct.pack("<I", len(body)) + body, len(presets), len(instruments), len(sample_ids)


def make(soundfont, jar):
    """The SoundFont for the JAR's music: (data, presets, instruments, samples) kept"""
    used = defaultdict(set)
    with zipfile.ZipFile(jar) as z:
        for name in z.namelist():
            if name.lower().endswith(".mid"):
                notes_by_preset(z.read(name), used)
    with open(soundfont, "rb") as f:
        sf2 = f.read()
    if sf2[:4] != b"RIFF" or sf2[8:12] != b"sfbk":
        sys.exit(f"{soundfont} isn't a SoundFont")
    return subset(sf2, used)


def main():
    soundfont, jar, out = sys.argv[1:4]
    data, presets, instruments, samples = make(soundfont, jar)
    with open(out, "wb") as f:
        f.write(data)
    print(f"{out}: {presets} presets, {instruments} instruments, {samples} samples, "
          f"{len(data) / 1048576:.1f} MB (from {Path(soundfont).stat().st_size / 1048576:.1f} MB)")


if __name__ == "__main__":
    main()
