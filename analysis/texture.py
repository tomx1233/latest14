"""Add the reference's 'static' (inter-harmonic density) to the V5 render.

Measured gap this closes (300 Hz - 3 kHz, 18-42 s excerpt):

    reference   HNR 4.96   crest 2.53   clipped samples 29.9 %
    V5 output   HNR 8.29   crest 4.90   clipped samples 19.0 %

HNR here is mean(spectral peaks) / median(spectrum) per frame: a high value
means clean harmonics with quiet gaps between them, a low value means the gaps
are filled in -- which is what "static" sounds like. The reference is far
fuller between its harmonics than any serial EQ-into-clipper arrangement can
produce (tested: repeating the chain, resampling aliasing, bit depth, MP3 and
Vorbis coding, tremolo/limiter modulation, detune doubling, bitcrushing, gated
noise, harder clipping, more pre-emphasis -- all stay above HNR 6.9).

What does work is a PARALLEL band-limited saturation: saturate a 1-6 kHz copy
hard enough to generate dense distortion, mix it back, then clip the sum to the
reference's crest. That is also why the user's own Bass and Treble attempt went
static in both directions: on a full-scale clipped file the EQ either pushes
already-clipped samples further into the ceiling or unbalances the mix and the
following normalise/clip pass puts the distortion back.
"""
import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import killa_tools as kt

FF = kt._FFMPEG_BIN
OUT = "results"

TEXTURE = dict(
    band=(1000, 6000),
    drive_db=40.0,
    wet=0.6,
    clip_drive_db=10.0,
    note="fitted on 18-42 s: HNR 5.49 vs reference 4.96, crest 2.56 vs 2.53",
)


def hnr(x, band=(300, 3000), n=16384, sr=44100):
    m = x.mean(1)
    w = np.hanning(n)
    vals = []
    for i in range(0, len(m) - n, n // 2):
        S = np.abs(np.fft.rfft(m[i:i + n] * w)) ** 2
        f = np.fft.rfftfreq(n, 1 / sr)
        q = S[(f >= band[0]) & (f < band[1])]
        if q.sum() <= 0:
            continue
        pk = (q[1:-1] > q[:-2]) & (q[1:-1] > q[2:])
        vals.append(q[1:-1][pk].mean() / np.median(q))
    return float(np.mean(vals)) if vals else 0.0


def crest(y):
    return 20 * np.log10(np.abs(y).max() / np.sqrt((y ** 2).mean()))


def report(path, label):
    x = kt._v5_pcm(path)
    a = np.abs(x)
    target = kt.autofit_v5_profile()["targets"]["octave_curve_db"]
    band = np.sqrt(np.mean(
        (np.array(kt._v5_octave_curve(x)["octave_curve_db"])
         - np.array(target)) ** 2))
    print(f"{label:22s} HNR {hnr(x):5.2f}  crest {crest(x):5.2f}  "
          f"clipped {100 * (a >= 0.999).mean():5.1f}%  octave RMSE {band:4.2f} dB")
    return dict(hnr=hnr(x), crest=crest(x),
                clipped_pct=float(100 * (a >= 0.999).mean()),
                octave_rmse=float(band))


def texture_graph(base, t, sr=44100):
    """ffmpeg filter_complex adding a parallel saturated band.

    The trailing `aeval` clip restores the reference's crest; a peak/RMS check
    after it is what the fit used, so the two stages are together, not optional.
    """
    lo, hi = t["band"]
    k = 10 ** (t["drive_db"] / 20)
    kc = 10 ** (t["clip_drive_db"] / 20)
    return (
        f"[0:a]aformat=sample_rates={sr}:sample_fmts=fltp:channel_layouts=stereo,"
        f"asplit=2[dry][toband];"
        f"[toband]highpass=f={lo}:poles=2,highpass=f={lo}:poles=2,"
        f"lowpass=f={hi}:poles=2,lowpass=f={hi}:poles=2,"
        f"aformat=sample_rates={sr}:sample_fmts=fltp,"
        f"aeval=exprs='tanh(val(0)*{k:.4f})|tanh(val(1)*{k:.4f})'[sat];"
        f"[dry][sat]amix=inputs=2:weights='1 {t['wet']}':normalize=0,"
        f"aformat=sample_rates={sr}:sample_fmts=fltp,"
        f"aeval=exprs='atan(val(0)*{kc:.6f})*0.63661977|"
        f"atan(val(1)*{kc:.6f})*0.63661977'"
        f"[out]"
    )


def main():
    prof = kt.autofit_v5_profile()
    base = os.path.join(OUT, "texture_base.wav")
    print("rendering the shipped V5 chain...")
    kt._v5_render_base("../TestSong.ogg", base, prof, progress=print)

    print("\nreference / shipped / textured (18-42 s excerpt = the fitted window)")
    ref = os.path.join("..", "NewTest.ogg")
    s, e = int(18 * 44100), int(42 * 44100)
    for path, label in ((ref, "reference"), (base, "V5 shipped")):
        x = kt._v5_pcm(path)[s:e]
        print(f"{label:22s} HNR {hnr(x):5.2f}  crest {crest(x):5.2f}  "
              f"clipped {100 * (np.abs(x) >= 0.999).mean():5.1f}%")

    mix = os.path.join(OUT, "texture_mix.wav")
    graph = texture_graph("[0:a]", TEXTURE)
    rc, _o, err = kt._run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", base,
                           "-filter_complex", graph, "-map", "[out]",
                           "-c:a", "pcm_f32le", mix])
    if rc != 0:
        raise SystemExit(f"texture render failed: {err}")
    x = kt._v5_pcm(mix)[s:e]
    print(f"{'V5 + static':22s} HNR {hnr(x):5.2f}  crest {crest(x):5.2f}  "
          f"clipped {100 * (np.abs(x) >= 0.999).mean():5.1f}%")

    # the added band energy must be pulled back by the existing residual trim
    trim, applied = kt._v5_trim_filter(kt._v5_octave_curve(kt._v5_pcm(mix))["octave_curve_db"], prof)
    print("\nresidual trim needed after the texture stage:",
          [round(v, 2) for v in applied])
    print("trim filter:", trim or "(none)")

    out = os.path.join(OUT, "TestSong_v5_reference_static.mp3")
    if trim:
        fixed = os.path.join(OUT, "texture_fixed.wav")
        rc, _o, err = kt._run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", mix,
                               "-af", trim, "-c:a", "pcm_f32le", fixed])
        if rc != 0:
            raise SystemExit(f"trim failed: {err}")
        mix = fixed
    info = kt._v5_export(mix, out, prof, progress=print)
    print("export:", info)
    print("\nFull track:")
    rows = {
        "reference": report(ref, "reference"),
        "shipped": report(os.path.join(OUT, "TestSong_v5_reference.mp3"), "V5 shipped"),
        "textured": report(out, "V5 + static"),
    }
    rows["texture"] = TEXTURE
    json.dump(rows, open(os.path.join(OUT, "texture_summary.json"), "w"), indent=1)
    print("\nwrote", out)


if __name__ == "__main__":
    main()
