"""Randomised search: pre-emphasis -> saturation -> post-correction.

The three stages are all expressible in Audacity 2.3.3 (Filter Curve / Bass and
Treble / Amplify / Clip Fix / SC1), so anything found here can be shipped as a
macro. Scoring is against measured NewTest.ogg statistics on a fixed excerpt.
"""
import numpy as np
import common as C
import candidates as K
from scipy.signal import butter, sosfilt

SR = 44100


def fft_shelf(x, fc, gain_db, kind="high"):
    n = x.shape[0]
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(n, 1 / SR)
    if kind == "high":
        H = np.abs(f / (f + fc + 1e-9))
    else:
        H = np.abs(fc / (f + fc + 1e-9))
    H = 1 + (10 ** (gain_db / 20) - 1) * H
    if X.ndim > 1:
        H = H[:, None]
    return np.fft.irfft(X * H, n, axis=0)


def hp(x, fc, order=4):
    if fc <= 0:
        return x
    sos = butter(order, fc / (SR / 2), btype="high", output="sos")
    return sosfilt(sos, x, axis=0)


def sat(y, kind, drive):
    if kind == "hard":
        return np.clip(y * drive, -1, 1)
    if kind == "tanh":
        return np.tanh(y * drive)
    if kind == "atan":
        return np.arctan(y * drive) * (2 / np.pi)
    raise ValueError(kind)


def render(x, hp_fc, pre_fc, pre_db, drive, kind, post_fc, post_db, wet=1.0):
    y = hp(x, hp_fc)
    if pre_db:
        y = fft_shelf(y, pre_fc, pre_db)
    peak = np.abs(y).max()
    y = y / max(peak, 1e-9)
    d = sat(y, kind, drive)
    if post_db:
        d = fft_shelf(d, post_fc, post_db)
    y = (1 - wet) * x + wet * d
    return y / max(np.abs(y).max(), 1e-9)


def score(z, ref):
    n = min(len(z), len(ref))
    z, ref = z[:n], ref[:n]
    bl_c, bl_r = K.band_levels(z.mean(1)), K.band_levels(ref.mean(1))
    g = np.median(C.db(bl_r[3:6]) - C.db(bl_c[3:6]))
    err = (C.db(bl_c) + g) - C.db(bl_r)
    band = float(np.sqrt(np.mean(err ** 2)))          # skip 30-60 (sub)
    crest = C.db(np.abs(z).max() / C.rms(z))
    crest_r = C.db(np.abs(ref).max() / C.rms(ref))
    lr = np.corrcoef(z[:, 0], z[:, 1])[0, 1]
    lr_r = np.corrcoef(ref[:, 0], ref[:, 1])[0, 1]
    m = z.mean(1)
    zcr = ((m[:-1] * m[1:]) < 0).mean() * SR
    m2 = ref.mean(1)
    zcr_r = ((m2[:-1] * m2[1:]) < 0).mean() * SR
    hz, _ = np.histogram(z[:, 0] / np.abs(z).max(), 64, (-1, 1), density=True)
    hr, _ = np.histogram(ref[:, 0] / np.abs(ref).max(), 64, (-1, 1), density=True)
    hist = float(np.abs(hz - hr).mean())
    s = (band * 2.0 + 4.0 * abs(crest - crest_r) + 3.0 * abs(zcr / zcr_r - 1)
         + 4.0 * abs(lr - lr_r) * 10 + 20.0 * hist)
    return dict(score=s, band=band, crest=crest, zcr_ratio=zcr / zcr_r,
                lr=lr, lr_err=abs(lr - lr_r), hist=hist, err=err)


# ---- fast, FFT-based metric used by the optimiser -------------------------
def band_power(x, sr=SR, n_fft=8192):
    """Octave-band power of a mono signal via one STFT (fast)."""
    from scipy.signal import get_window
    w = get_window("hann", n_fft)
    hop = n_fft // 2
    nfr = 1 + (len(x) - n_fft) // hop
    fr = np.lib.stride_tricks.sliding_window_view(x, n_fft)[::hop][:nfr]
    P = np.abs(np.fft.rfft(fr * w, axis=1)) ** 2
    f = np.fft.rfftfreq(n_fft, 1 / sr)
    P = P.mean(0)
    out = []
    for lo, hi in K.BANDS:
        m = (f >= lo) & (f < hi)
        out.append(P[m].sum())
    return np.array(out)


def fast_stats(z, ref, sr=SR):
    pz, pr = band_power(z.mean(1), sr), band_power(ref.mean(1), sr)
    dz, dr = 10 * np.log10(pz + 1e-12), 10 * np.log10(pr + 1e-12)
    g = np.median(dr[2:6] - dz[2:6])
    err = (dz + g) - dr
    crest = C.db(np.abs(z).max() / C.rms(z))
    crest_r = C.db(np.abs(ref).max() / C.rms(ref))
    lr = np.corrcoef(z[:, 0], z[:, 1])[0, 1]
    lr_r = np.corrcoef(ref[:, 0], ref[:, 1])[0, 1]
    m, m2 = z.mean(1), ref.mean(1)
    zcr = ((m[:-1] * m[1:]) < 0).mean()
    zcr_r = ((m2[:-1] * m2[1:]) < 0).mean()
    hz, _ = np.histogram(z[:, 0] / np.abs(z).max(), 64, (-1, 1), density=True)
    hr, _ = np.histogram(ref[:, 0] / np.abs(ref).max(), 64, (-1, 1), density=True)
    hist = float(np.abs(hz - hr).mean())
    band = float(np.sqrt(np.mean(err ** 2)))
    s = (2.0 * band + 4.0 * abs(crest - crest_r) + 3.0 * abs(zcr / zcr_r - 1)
         + 40.0 * abs(lr - lr_r) + 20.0 * hist)
    return dict(score=s, band=band, crest=crest, crest_err=abs(crest - crest_r),
                zcr_ratio=zcr / zcr_r, lr=lr, lr_err=abs(lr - lr_r), hist=hist, err=err)
