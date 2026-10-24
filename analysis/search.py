"""Grid search over a compact, Audacity-expressible chain on a fixed excerpt.

Chain shape (all Audacity-native / LADSPA-reachable):
  High-pass -> High-shelf (Bass and Treble / TDR Nova) -> gain -> hard clip
The hard clip stands in for Audacity's Clip Fix / SC1-at-max repeated passes.
"""
import itertools
import numpy as np
import common as C
import candidates as K
from scipy.signal import butter, sosfiltfilt, sosfilt

T0, T1 = 20.0, 80.0  # s, search excerpt


def shelf_gain(x, sr, fc, gain_db, kind="high"):
    """Zero-phase FFT shelf (approximates a 1-pole shelf response)."""
    n = len(x)
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(n, 1 / sr)
    if X.ndim > 1:
        X = X * (1 if True else 1)
    # one-pole magnitude response, mirrored for the shelf
    if kind == "high":
        H = np.abs(f / (f + fc + 1e-9))  # 0 at low, 1 at high
        H = 1 + (10 ** (gain_db / 20) - 1) * H
    else:
        H = np.abs(fc / (f + fc + 1e-9))
        H = 1 + (10 ** (gain_db / 20) - 1) * H
    if X.ndim > 1:
        H = H[:, None]
    return np.fft.irfft(X * H, n, axis=0)


def chain(x, sr, hp=0.0, sh_hz=0.0, sh_db=0.0, gain_db=0.0, clip=1.0, npass=1):
    y = x.copy()
    if hp > 0:
        sos = butter(2, hp / (sr / 2), btype="high", output="sos")
        y = sosfilt(sos, y, axis=0)
    if sh_hz > 0 and sh_db != 0:
        y = shelf_gain(y, sr, sh_hz, sh_db)
    y = y * (10 ** (gain_db / 20))
    for _ in range(npass):
        y = np.clip(y, -clip, clip)
        y = y / max(np.abs(y).max(), 1e-9) * clip
    return y


def metrics(cand, ref, sr=44100):
    n = min(len(cand), len(ref))
    cand, ref = cand[:n], ref[:n]
    bl_c, bl_r = K.band_levels(cand.mean(1), sr), K.band_levels(ref.mean(1), sr)
    g = np.median(C.db(bl_r[2:5]) - C.db(bl_c[2:5]))
    err = (C.db(bl_c) + g) - C.db(bl_r)
    crest_c = C.db(np.abs(cand).max() / C.rms(cand))
    crest_r = C.db(np.abs(ref).max() / C.rms(ref))
    lr_c = np.corrcoef(cand[:, 0], cand[:, 1])[0, 1]
    lr_r = np.corrcoef(ref[:, 0], ref[:, 1])[0, 1]
    m = cand.mean(1)
    zcr_c = ((m[:-1] * m[1:]) < 0).mean() * sr
    m2 = ref.mean(1)
    zcr_r = ((m2[:-1] * m2[1:]) < 0).mean() * sr
    hc, _ = np.histogram(cand[:, 0] / np.abs(cand).max(), 64, (-1, 1), density=True)
    hr, _ = np.histogram(ref[:, 0] / np.abs(ref).max(), 64, (-1, 1), density=True)
    return dict(band_rmse=float(np.sqrt(np.mean(err ** 2))), err=err,
                crest_err=abs(crest_c - crest_r), lr_err=abs(lr_c - lr_r),
                zcr_ratio=zcr_c / zcr_r, hist=float(np.abs(hc - hr).mean()),
                crest=crest_c, lr=lr_c, zcr=zcr_c)


def run(excerpt_a, excerpt_b, grid, sr=44100):
    rows = []
    for hp, sh_hz, sh_db, gain_db, npass in grid:
        y = chain(excerpt_a, sr, hp, sh_hz, sh_db, gain_db, 1.0, npass)
        m = metrics(y, excerpt_b, sr)
        m.update(hp=hp, sh_hz=sh_hz, sh_db=sh_db, gain_db=gain_db, npass=npass)
        rows.append(m)
    return rows
