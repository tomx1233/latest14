"""Audacity 2.3.3's Bass and Treble, reproduced exactly.

Coefficient formulas transcribed from `src/effects/BassTreble.cpp`
(Audacity-2.3.3): a low shelf at 250 Hz and a high shelf at 4 kHz, both with
slope 0.4, run in series, then a linear makeup `Gain`. The clue that sent us
here is in the reference itself -- the fitted pre-emphasis (3.2 kHz) and
de-emphasis (5.3 kHz) corners both bracket 4 kHz, which is where this effect's
treble shelf lives.

Bass and Treble is a *linear* filter. On its own it cannot make anything
static. What makes it static is what happens next: boost 30 dB of treble into a
file that is already at full scale and the next stage that limits or normalises
turns that boost into clipping, and clipping a dense mix generates the
inharmonic hash that reads as "static". Cutting the treble afterwards restores
the balance but not the tonal structure, so the file ends up balanced AND
static -- neither thing alone explains the reference.

Used for measurement and for the ffmpeg fallback's exact `biquad` stages.
"""
import numpy as np

HZ_BASS = 250.0
HZ_TREBLE = 4000.0
SLOPE = 0.4
MAX_DB = 30.0


def coeffs(hz, gain_db, sr=44100, kind="treble", slope=SLOPE):
    """(b0, b1, b2, a0, a1, a2) exactly as Audacity computes them."""
    w = 2 * np.pi * hz / sr
    a = np.exp(np.log(10.0) * gain_db / 40.0)
    b = np.sqrt((a * a + 1) / slope - (a - 1) ** 2)
    cw, sw = np.cos(w), np.sin(w)
    if kind == "bass":
        b0 = a * ((a + 1) - (a - 1) * cw + b * sw)
        b1 = 2 * a * ((a - 1) - (a + 1) * cw)
        b2 = a * ((a + 1) - (a - 1) * cw - b * sw)
        a0 = (a + 1) + (a - 1) * cw + b * sw
        a1 = -2 * ((a - 1) + (a + 1) * cw)
        a2 = (a + 1) + (a - 1) * cw - b * sw
    else:
        b0 = a * ((a + 1) + (a - 1) * cw + b * sw)
        b1 = -2 * a * ((a - 1) + (a + 1) * cw)
        b2 = a * ((a + 1) + (a - 1) * cw - b * sw)
        a0 = (a + 1) - (a - 1) * cw + b * sw
        a1 = 2 * ((a - 1) - (a + 1) * cw)
        a2 = (a + 1) - (a - 1) * cw - b * sw
    return b0, b1, b2, a0, a1, a2


def apply(x, bass_db=0.0, treble_db=0.0, gain_db=0.0, sr=44100):
    """Run Audacity's effect over an (n, ch) array: bass shelf, treble shelf, gain."""
    from scipy.signal import lfilter

    y = np.asarray(x, dtype=np.float64)
    for db, kind in ((bass_db, "bass"), (treble_db, "treble")):
        if db == 0.0:
            continue
        b0, b1, b2, a0, a1, a2 = coeffs(HZ_BASS if kind == "bass" else HZ_TREBLE,
                                        db, sr, kind)
        y = lfilter([b0 / a0, b1 / a0, b2 / a0], [1.0, a1 / a0, a2 / a0], y, axis=0)
    if gain_db:
        y = y * (10.0 ** (gain_db / 20.0))
    return y


def ffmpeg_stages(bass_db=0.0, treble_db=0.0, sr=44100):
    """The same two biquads as ffmpeg filter strings (exact, not an approximation)."""
    out = []
    for db, kind in ((bass_db, "bass"), (treble_db, "treble")):
        if not db:
            continue
        b0, b1, b2, a0, a1, a2 = coeffs(HZ_BASS if kind == "bass" else HZ_TREBLE,
                                        db, sr, kind)
        out.append(f"biquad=b0={b0 / a0:.12f}:b1={b1 / a0:.12f}:b2={b2 / a0:.12f}"
                   f":a0=1:a1={a1 / a0:.12f}:a2={a2 / a0:.12f}")
    return ",".join(out)


if __name__ == "__main__":
    # Sanity: DC and Nyquist gain of each shelf must hit the requested dB.
    for kind, hz in (("bass", HZ_BASS), ("treble", HZ_TREBLE)):
        for db in (-30.0, -6.0, 6.0, 30.0):
            b0, b1, b2, a0, a1, a2 = coeffs(hz, db, 44100, kind)
            b = np.array([b0, b1, b2]) / a0
            a = np.array([1.0, a1 / a0, a2 / a0])
            dc = np.sum(b) / np.sum(a)
            ny = np.sum(b * np.array([1, -1, 1])) / np.sum(a * np.array([1, -1, 1]))
            print(f"{kind:6s} {db:+6.1f} dB  DC {20 * np.log10(abs(dc)):7.2f} dB   "
                  f"Nyquist {20 * np.log10(abs(ny)):7.2f} dB")
