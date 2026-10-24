"""Candidate rendering + scoring against NewTest.ogg.

Every candidate is built from TestSong.ogg only. Scoring is level-matched and
multi-metric so that a louder candidate is not automatically "better".
"""
import os
import numpy as np
import common as C
from scipy.signal import butter, sosfilt, sosfiltfilt, csd, welch

BANDS = [(30, 60), (60, 120), (120, 240), (240, 480), (480, 960),
         (960, 1920), (1920, 3840), (3840, 7680), (7680, 15360)]
LAG = 1169  # samples; reference is delayed by ~26.5 ms relative to TestSong


def bp(x, lo, hi, sr=44100, zero_phase=True):
    sos = butter(4, [lo / (sr / 2), hi / (sr / 2)], btype="band", output="sos")
    return sosfiltfilt(sos, x) if zero_phase else sosfilt(sos, x)


def band_levels(x, sr=44100):
    return np.array([C.rms(bp(x, lo, hi, sr)) for lo, hi in BANDS])


def coherence_profile(a, b, sr=44100, nperseg=16384):
    f, Cxy = csd(a, b, sr, nperseg=nperseg, noverlap=nperseg // 2)
    _, Cxx = welch(a, sr, nperseg=nperseg, noverlap=nperseg // 2)
    _, Cyy = welch(b, sr, nperseg=nperseg, noverlap=nperseg // 2)
    return f, np.abs(Cxy) ** 2 / (Cxx * Cyy + 1e-30)


def compare(cand, ref, sr=44100, lag=LAG, verbose=True, name=""):
    """Compare two stereo arrays of equal length; cand is time-aligned already."""
    n = min(len(cand), len(ref))
    cand = cand[:n]
    ref = ref[:n]
    out = {}
    out["rms_db"] = C.db(C.rms(cand))
    out["ref_rms_db"] = C.db(C.rms(ref))
    out["crest"] = C.db(np.abs(cand).max() / C.rms(cand))
    out["ref_crest"] = C.db(np.abs(ref).max() / C.rms(ref))
    out["peak"] = np.abs(cand).max()

    # band levels, gain matched on 120-2000 Hz
    bl_c, bl_r = band_levels(cand.mean(1), sr), band_levels(ref.mean(1), sr)
    g = np.median(C.db(bl_r[2:5]) - C.db(bl_c[2:5]))
    err = (C.db(bl_c) + g) - C.db(bl_r)
    out["band_err_db"] = err
    out["band_rmse"] = float(np.sqrt(np.mean(err ** 2)))
    out["gain_db"] = float(g)

    # L/R correlation
    def lr_corr(x):
        return float(np.corrcoef(x[:, 0], x[:, 1])[0, 1])
    out["lr_corr"] = lr_corr(cand)
    out["ref_lr_corr"] = lr_corr(ref)

    # ZCR
    def zcr(x):
        m = x.mean(1)
        return float(((m[:-1] * m[1:]) < 0).sum() / (len(m) / sr))
    out["zcr"] = zcr(cand)
    out["ref_zcr"] = zcr(ref)

    # coherence of the mono mid against the reference
    am, bm = cand.mean(1), ref.mean(1)
    f, coh = coherence_profile(am, bm, sr)
    m_lo = (f > 40) & (f < 400)
    m_hi = (f > 1000) & (f < 16000)
    out["coh_lo"] = float(np.median(coh[m_lo]))
    out["coh_hi"] = float(np.median(coh[m_hi]))

    # bass envelope correlation (the surviving program material)
    ea = np.abs(bp(am, 20, 150, sr))
    eb = np.abs(bp(bm, 20, 150, sr))
    def env(x, ms=20):
        h = int(sr * ms / 1000)
        k = len(x) // h
        return np.sqrt((x[:k * h].reshape(k, h) ** 2).mean(1))
    Ea, Eb = env(ea), env(eb)
    out["bass_env_corr"] = float(np.corrcoef(Ea, Eb)[0, 1])

    # amplitude histogram distance (shape only)
    hist_c, edges = np.histogram(cand[:, 0] / max(np.abs(cand).max(), 1e-9), bins=64, range=(-1, 1), density=True)
    hist_r, _ = np.histogram(ref[:, 0] / max(np.abs(ref).max(), 1e-9), bins=64, range=(-1, 1), density=True)
    out["hist_l1"] = float(np.abs(hist_c - hist_r).sum() / 64)

    if verbose:
        print(f"[{name}] rms {out['rms_db']:+.1f}dB (ref {out['ref_rms_db']:+.1f}) "
              f"crest {out['crest']:.1f} (ref {out['ref_crest']:.1f}) peak {out['peak']:.2f}")
        print(f"     band RMSE {out['band_rmse']:.1f} dB | L/R {out['lr_corr']:.3f} "
              f"(ref {out['ref_lr_corr']:.3f}) | ZCR {out['zcr']:.0f} (ref {out['ref_zcr']:.0f})")
        print(f"     coh_lo {out['coh_lo']:.3f} coh_hi {out['coh_hi']:.3f} | "
              f"bass_env_corr {out['bass_env_corr']:.3f} | histL1 {out['hist_l1']:.4f}")
        print("     per-octave error (dB): " + " ".join(
            f"{lo}-{hi}:{e:+.0f}" for (lo, hi), e in zip(BANDS, err)))
    return out


def align(cand, ref_len, lag=LAG):
    """Insert `lag` samples of delay into the candidate, then match length."""
    if lag > 0:
        pad = np.zeros((lag, cand.shape[1]))
        cand = np.vstack([pad, cand])
    elif lag < 0:
        cand = cand[-lag:]
    if len(cand) < ref_len:
        cand = np.vstack([cand, np.zeros((ref_len - len(cand), cand.shape[1]))])
    return cand[:ref_len]
