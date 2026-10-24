"""Build the Auto-Fit V5 reference profile from the two supplied recordings.

Writes macros/autofit_v5_reference.json, the measured target the bot renders
against at runtime (so NewTest.ogg never has to ship with the bot).
"""
import hashlib
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import candidates as K
sys.path.insert(0, C.HERE)
import killa_tools as KT

CHAIN_JSON = os.path.join(C.OUT, "v5_chain.json")
OUT_JSON = os.path.join(C.HERE, "macros", "autofit_v5_reference.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def short_term_db(x, sr, win=3.0):
    h = int(sr * win)
    k = len(x) // h
    if k < 1:
        return None
    blocks = x[: k * h].reshape(k, h)
    return 20 * np.log10(np.maximum(np.sqrt((blocks ** 2).mean(1)), 1e-12))


def band_curve_db(x, sr):
    """Octave-band curve measured exactly the way the runtime measures it.

    The bot scores its own output with killa_tools._v5_octave_curve(), so the
    profile must use that same estimator -- a different one (e.g. time-domain
    band filtering) differs by up to ~1 dB and would make the trim chase a
    target the report never measures.
    """
    return KT._v5_octave_curve(x)["octave_curve_db"], None


def main():
    A, sr = C.load(C.SRC)
    B, sr_b = C.load(C.REF)
    n = min(len(A), len(B))
    A, B = A[:n], B[:n]
    assert sr == sr_b

    # Chain fitted with the production ffmpeg renderer (analysis/fit_ffmpeg.py):
    # the numbers below are what the bot actually runs, not an idealised model.
    with open(CHAIN_JSON, "r", encoding="utf-8") as fh:
        chain = json.load(fh)

    # Reference vs source targets
    def stats(x):
        st = short_term_db(x.mean(1), sr)
        return {
            "rms_dbfs": round(float(C.db(C.rms(x))), 2),
            "sample_peak": round(float(np.abs(x).max()), 4),
            "sample_peak_dbfs": round(float(C.db(np.abs(x).max())), 2),
            "crest_db": round(float(C.db(np.abs(x).max() / C.rms(x))), 2),
            "lr_corr": round(float(np.corrcoef(x[:, 0], x[:, 1])[0, 1]), 4),
            "zcr_per_sec": int(round(float(((x.mean(1)[:-1] * x.mean(1)[1:]) < 0).sum() / (len(x) / sr)))),
            "short_term_db_median": round(float(np.median(st)), 2) if st is not None else None,
            "short_term_db_p05": round(float(np.percentile(st, 5)), 2) if st is not None else None,
            "short_term_db_p95": round(float(np.percentile(st, 95)), 2) if st is not None else None,
        }

    src_stats, ref_stats = stats(A), stats(B)
    src_curve, _ = band_curve_db(A, sr)
    ref_curve, _ = band_curve_db(B, sr)

    profile = {
        "name": "CopyR8 Auto-Fit V5 (Reference)",
        "version": 1,
        "derived_from": {
            "reference": os.path.basename(C.REF),
            "original": os.path.basename(C.SRC),
            "reference_sha256": sha256(C.REF),
            "original_sha256": sha256(C.SRC),
            "sample_rate": sr,
            "channels": 2,
            "duration_s": round(n / sr, 3),
        },
        "alignment": {
            "reference_delay_ms": 26.5,
            "reference_delay_samples": 1169,
            "tempo_ratio": 1.0,
            "pitch_shift_semitones": 0.0,
            "chroma_correlation_at_0st": 0.911,
            "note": ("same performance, same key, same length: the 26.5 ms offset is a "
                     "fixed render/plugin latency, not a musical change; local lag is "
                     "constant across the whole track (no drift, so no tempo change)."),
        },
        "octave_bands_hz": [list(b) for b in K.BANDS],
        "targets": {
            # Integrated loudness / true peak / LRA measured with
            # `ffmpeg -af ebur128=peak=true` on each file (2026-10-24):
            #   TestSong.ogg  I -8.8 LUFS, TP +12.4 dBFS, LRA 8.2 LU
            #   NewTest.ogg   I +1.9 LUFS, TP  +4.2 dBFS, LRA 0.7 LU
            "lufs": 1.9,
            "true_peak_dbtp": 4.2,
            "lra_lu": 0.7,
            "octave_curve_db": ref_curve,
            "octave_curve_db_source": src_curve,
            **ref_stats,
        },
        "source": src_stats,
        "chain": chain,
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=2)
        fh.write("\n")
    print("wrote", OUT_JSON)
    print(json.dumps(profile["targets"], indent=2))
    print("chain:", json.dumps(chain, indent=2))


if __name__ == "__main__":
    main()
