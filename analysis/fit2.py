"""Refit the V5 chain with the 'static' signature in the objective.

The first fit matched the octave curve, crest, L/R, ZCR and the amplitude
histogram, but NOT how much energy sits *between* the harmonics. The reference
is measurably fuller between harmonics (per-frame spectral flatness 500 Hz-8 kHz:
0.43 vs the source's 0.26) -- that is the static the user hears, and the old
fit left the mid band clean (0.32).

Structure follows what the user was doing by hand: Audacity's Bass and Treble
before and after a clipper, with Amplify in between to drive it.
"""
import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import killa_tools as kt
import basstreble as BT

SR = 44100
BANDS = [(20, 60), (60, 120), (120, 240), (240, 480), (480, 960),
         (960, 1920), (1920, 3840), (3840, 7680), (7680, 15360)]
FLAT_BANDS = [(200, 500), (500, 1000), (1000, 2000), (2000, 4000),
              (4000, 8000), (8000, 12000)]

PRE = "results/fit2_src.wav"


def octave_curve(x, n=8192):
    m = x.mean(1)
    w = np.hanning(n)
    acc = np.zeros(n // 2 + 1)
    c = 0
    for i in range(0, len(m) - n, n // 2):
        acc += np.abs(np.fft.rfft(m[i:i + n] * w)) ** 2
        c += 1
    f = np.fft.rfftfreq(n, 1 / SR)
    lv = np.array([10 * np.log10(max(acc[(f >= a) & (f < b)].sum() / c, 1e-20))
                   for a, b in BANDS])
    return lv - np.median(lv[2:6])


def flatness(x, n=4096):
    m = x.mean(1)
    w = np.hanning(n)
    S = np.stack([np.abs(np.fft.rfft(m[i:i + n] * w)) ** 2
                  for i in range(0, len(m) - n, n // 2)])
    f = np.fft.rfftfreq(n, 1 / SR)
    out = []
    for a, b in FLAT_BANDS:
        seg = S[:, (f >= a) & (f < b)]
        gm = np.exp(np.mean(np.log(seg + 1e-30), axis=1))
        am = seg.mean(axis=1)
        out.append(float(((gm / am) * (am / am.sum())).sum()))
    return np.array(out)


def stats(x):
    m = kt._v5_octave_curve(x)
    return dict(curve=octave_curve(x), flat=flatness(x), crest=m["crest_db"],
                zcr=m["zcr_per_sec"], lr=m["lr_corr"])


def clip_atan(y, drive_db):
    k = 10.0 ** (drive_db / 20.0)
    return np.arctan(y * k) * (2 / np.pi)


def apply_chain(x, p):
    """p = (pre_bass, pre_treble, drive, post_bass, post_treble, shape_bias)."""
    pre_bass, pre_treble, drive, post_bass, post_treble, bias = p
    y = BT.apply(x, bass_db=pre_bass, treble_db=pre_treble)
    y = y / np.abs(y).max() * 10 ** (bias / 20.0)
    y = clip_atan(y, drive)
    y = BT.apply(y, bass_db=post_bass, treble_db=post_treble)
    return y / np.abs(y).max()


def score(p, x, ref):
    y = apply_chain(x, p)
    s = stats(y)
    band = float(np.sqrt(np.mean((s["curve"] - ref["curve"]) ** 2)))
    fl = float(np.sqrt(np.mean((s["flat"] - ref["flat"]) ** 2)))
    pen = (2.0 * band + 12.0 * fl
           + 3.0 * abs(s["crest"] - ref["crest"])
           + 8.0 * abs(s["zcr"] / ref["zcr"] - 1)
           + 40.0 * abs(s["lr"] - ref["lr"]))
    return pen, band, fl, s


def main():
    import soundfile as sf
    from scipy.optimize import differential_evolution

    src_wav = "results/bt_pre2.wav"
    if not os.path.exists(src_wav):
        c = dict(kt.autofit_v5_profile()["chain"])
        c["pre_emphasis_db"] = 0.0
        import subprocess
        subprocess.run([kt._FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "error",
                        "-i", "../TestSong.ogg", "-af", kt._v5_pre_filter(c),
                        "-c:a", "pcm_f32le", src_wav], check=True)

    # 24 s sample: long enough for the quieter sections to count
    s, e = int(18 * SR), int(42 * SR)
    x = kt._v5_pcm(src_wav)[s:e]
    ref = stats(kt._v5_pcm("../NewTest.ogg")[s:e])
    print("reference:", {k: (np.round(v, 3) if isinstance(v, np.ndarray) else v)
                         for k, v in ref.items()})
    print("source   :", {k: (np.round(v, 3) if isinstance(v, np.ndarray) else v)
                         for k, v in stats(x).items()})

    bounds = [(-24, 24), (-12, 30), (6, 48), (-24, 24), (-30, 12), (-12, 12)]
    res = differential_evolution(lambda p: score(p, x, ref)[0], bounds, seed=11,
                                 maxiter=40, popsize=12, tol=1e-4, polish=False,
                                 init="sobol", workers=1)
    pen, band, fl, s = score(res.x, x, ref)
    print(f"\nscore {pen:.3f}  band {band:.2f} dB  flatness {fl:.4f}")
    print("pre_bass=%.1f pre_treble=%.1f drive=%.1f post_bass=%.1f post_treble=%.1f bias=%.1f"
          % tuple(res.x))
    print("curve out", np.round(s["curve"], 2))
    print("curve ref", np.round(ref["curve"], 2))
    print("flat  out", np.round(s["flat"], 3))
    print("flat  ref", np.round(ref["flat"], 3))
    print("crest %.2f/%.2f  zcr %d/%d  lr %.3f/%.3f"
          % (s["crest"], ref["crest"], s["zcr"], ref["zcr"], s["lr"], ref["lr"]))
    json.dump({"params": [float(v) for v in res.x], "score": pen,
               "band": band, "flat": fl, "out": s, "ref": ref,
               "names": ["pre_bass", "pre_treble", "drive", "post_bass",
                         "post_treble", "bias"]},
              open("results/fit2.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
