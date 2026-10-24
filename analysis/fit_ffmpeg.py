"""Fit the V5 chain with the SAME ffmpeg code path the bot ships.

The earlier numpy fit used idealised shelves; ffmpeg's biquad shelves have a
different slope, so the parameters are re-fitted here against the production
renderer. Objective and weights are unchanged from the analysis fit:
level-matched octave balance, crest, L/R correlation, zero-crossing density
and the amplitude distribution.
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PATH", "/tmp/ffbin:" + os.environ.get("PATH", ""))

import common as C
import candidates as K
import killa_tools as KT

BANDS = K.BANDS
T0, T1 = 20.0, 32.0
# Leveller settings are NOT fitted here: they come from the full-track dynamics
# measurement (10 s block levels: source spans 8.9 dB, the reference 0.8 dB, and
# the gain the reference applies tracks the input ~1:1). Ratio 10 is Audacity
# 2.3.3's Compressor maximum, so the macro can run the same stage.
LEVELER = {"leveler_threshold_db": -20.0, "leveler_ratio": 10.0,
           "leveler_makeup_db": 1.50, "leveler_attack_ms": 10.0,
           "leveler_release_ms": 400.0}


def render(args):
    """args = (hp, pre_fc, pre_db, drive_db, de_fc, de_db)"""
    hp, pre_fc, pre_db, drive_db, de_fc, de_db = args
    chain = {
        "pre_highpass_hz": float(hp), "low_shelf_db": 0.0,
        "pre_emphasis_hz": float(pre_fc), "pre_emphasis_db": float(pre_db),
        "drive_db": float(drive_db), "de_emphasis_hz": float(de_fc),
        "de_emphasis_db": float(de_db), "post_low_shelf_db": 0.0,
    }
    chain.update(LEVELER)
    pre, sat = KT._v5_chain_filters(chain)
    rc, _o, err = KT._run(KT._FFMPEG + ["-i", SRC_WAV, "-af", f"{pre},{sat}",
                                        "-c:a", "pcm_f32le", TMP_WAV])
    if rc != 0:
        raise RuntimeError(err)
    return KT._v5_pcm(TMP_WAV)


def stats(z, ref):
    pz, pr = KT._v5_octave_curve(z)["octave_curve_db"], REF_CURVE
    # octave curves are already mid-referenced, so no extra gain matching needed
    err = np.array(pz) - np.array(pr)
    peak, rms = np.abs(z).max(), np.sqrt((z ** 2).mean())
    crest = 20 * np.log10(peak / rms)
    crest_r = REF_STATS["crest_db"]
    lr = np.corrcoef(z[:, 0], z[:, 1])[0, 1]
    lr_r = REF_STATS["lr_corr"]
    m = z.mean(1)
    zcr = ((m[:-1] * m[1:]) < 0).mean() * 44100
    zcr_r = REF_STATS["zcr_per_sec"]
    hz, _ = np.histogram(z[:, 0] / np.abs(z).max(), 64, (-1, 1), density=True)
    hist = float(np.abs(hz - REF_HIST).mean())
    band = float(np.sqrt(np.mean(err ** 2)))
    score = (2.0 * band + 4.0 * abs(crest - crest_r)
             + 3.0 * abs(zcr / zcr_r - 1) + 40.0 * abs(lr - lr_r) + 20.0 * hist)
    return dict(score=score, band=band, crest=crest, zcr_ratio=zcr / zcr_r,
                lr=lr, lr_err=abs(lr - lr_r), hist=hist, err=err)


if __name__ == "__main__":
    import soundfile as sf
    from scipy.optimize import differential_evolution

    A, sr = C.load(C.SRC)
    B, _ = C.load(C.REF)
    s, e = int(T0 * sr), int(T1 * sr)
    SRC_WAV = os.path.join(C.OUT, "fit_src.wav")
    TMP_WAV = os.path.join(C.OUT, "fit_tmp.wav")
    sf.write(SRC_WAV, A[s:e], sr, subtype="FLOAT")
    ref_ex = B[s:e]
    REF_CURVE = KT._v5_octave_curve(ref_ex)["octave_curve_db"]
    REF_STATS = KT._v5_octave_curve(ref_ex)
    REF_STATS["crest_db"] = round(float(20 * np.log10(np.abs(ref_ex).max() / np.sqrt((ref_ex ** 2).mean()))), 2)
    REF_HIST, _ = np.histogram(ref_ex[:, 0] / np.abs(ref_ex).max(), 64, (-1, 1), density=True)
    print("reference excerpt:", {k: REF_STATS[k] for k in ("crest_db", "lr_corr", "zcr_per_sec")})
    print("reference curve:", REF_CURVE)

    def obj(p):
        return stats(render(p), None)["score"]

    bounds = [(40, 110), (2000, 9000), (6, 30), (0, 50), (1000, 8000), (-16, 0)]
    res = differential_evolution(obj, bounds, seed=7, maxiter=14, popsize=8,
                                 polish=False, tol=0.002, init="sobol")
    p = [float(v) for v in res.x]
    z = render(p)
    m = stats(z, None)
    print("score %.4f" % res.fun)
    print("hp=%.1f pre_fc=%.0f pre_db=%.2f drive_db=%.2f de_fc=%.0f de_db=%.2f" % tuple(p))
    print({k: round(float(v), 3) for k, v in m.items() if k != "err"})
    print("octave err:", " ".join(f"{lo}-{hi}:{v:+.1f}" for (lo, hi), v in zip(BANDS, m["err"])))
    import json
    with open(os.path.join(C.OUT, "v5_chain.json"), "w") as fh:
        json.dump({
            "pre_highpass_hz": round(p[0], 1), "pre_highpass_order": 4,
            "low_shelf_hz": 132.0, "low_shelf_db": 0.0,
            "pre_emphasis_hz": round(p[1], 0), "pre_emphasis_db": round(p[2], 2),
            "saturation": "atan", "drive_db": round(p[3], 2),
            "de_emphasis_hz": round(p[4], 0), "de_emphasis_db": round(p[5], 2),
            "post_low_shelf_db": 0.0, "post_highpass_hz": 0.0,
            **{k: round(float(v), 2) for k, v in LEVELER.items()},
            "fit": {"excerpt_s": [T0, T1], "band_rmse_db": round(float(m["band"]), 2),
                    "crest_db": round(float(m["crest"]), 2),
                    "zcr_ratio": round(float(m["zcr_ratio"]), 3),
                    "lr_corr": round(float(m["lr"]), 3)},
        }, fh, indent=2)
    print("wrote", os.path.join(C.OUT, "v5_chain.json"))
    for f in (SRC_WAV, TMP_WAV):
        try:
            os.remove(f)
        except OSError:
            pass
