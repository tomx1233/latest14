"""Shared helpers for the Auto-Fit V5 reference analysis.

All measurements in this package are derived from the two supplied Ogg files:
  TestSong.ogg : original recording
  NewTest.ogg  : processed reference
"""
import os
import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "TestSong.ogg")
REF = os.path.join(HERE, "NewTest.ogg")
OUT = os.path.join(HERE, "analysis", "out")
os.makedirs(OUT, exist_ok=True)


def load(path):
    x, sr = sf.read(path, always_2d=True)
    return x, sr


def mid(x):
    return x.mean(axis=1)


def side(x):
    return (x[:, 0] - x[:, 1]) * 0.5


def db(v):
    return 20.0 * np.log10(np.maximum(np.asarray(v, dtype=float), 1e-12))


def rms(x):
    x = np.asarray(x, dtype=float)
    return float(np.sqrt(np.mean(x * x)))


def rms_db(x):
    return float(db(rms(x)))


def align_offset(a, b, max_lag=44100 * 3, sr=44100, band=(300, 3000)):
    """Broadband cross-correlation of the mono sums, restricted to a band."""
    from scipy.signal import butter, sosfilt
    sos = butter(4, [band[0] / (sr / 2), band[1] / (sr / 2)], btype="band", output="sos")
    a = sosfilt(sos, mid(a))[: sr * 40]
    b = sosfilt(sos, mid(b))[: sr * 40]
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    fa = np.fft.rfft(a, n)
    fb = np.fft.rfft(b, n)
    cc = np.fft.irfft(fa * np.conj(fb), n)
    cc = np.concatenate([cc[-max_lag:], cc[: max_lag + 1]])
    lag = int(np.argmax(np.abs(cc))) - max_lag
    return lag, cc


def local_lag(a, b, t0, win=4.0, max_lag=0.25, sr=44100, band=(300, 3000)):
    """Cross-correlation lag (seconds) between a and b inside one window."""
    from scipy.signal import butter, sosfilt
    sos = butter(4, [band[0] / (sr / 2), band[1] / (sr / 2)], btype="band", output="sos")
    i0 = int(t0 * sr)
    i1 = i0 + int(win * sr)
    if i1 > min(len(a), len(b)):
        i1 = min(len(a), len(b))
        i0 = i1 - int(win * sr)
    if i0 < 0:
        return None
    xa = sosfilt(sos, mid(a[i0:i1]))
    ml = int(max_lag * sr)
    xb = sosfilt(sos, mid(b[max(0, i0 - ml): i1 + ml]))
    off = i0 - max(0, i0 - ml)
    n = 1 << int(np.ceil(np.log2(len(xa) + len(xb))))
    cc = np.fft.irfft(np.fft.rfft(xb, n) * np.conj(np.fft.rfft(xa, n)), n)
    cc = np.concatenate([cc[-ml:], cc[: ml + 1]])
    k = int(np.argmax(np.abs(cc))) - ml
    return (k - off) / sr


def stft_db(x, sr, n_fft=4096, hop=1024):
    from scipy.signal import get_window
    w = get_window("hann", n_fft)
    nfr = 1 + (len(x) - n_fft) // hop
    frames = np.lib.stride_tricks.sliding_window_view(x, n_fft)[::hop][:nfr]
    S = np.fft.rfft(frames * w, axis=1)
    return 20 * np.log10(np.maximum(np.abs(S), 1e-9))


def ltas(x, sr, n_fft=16384, hop=8192):
    """Long-term average spectrum (dB per bin), mono input."""
    S = stft_db(x, sr, n_fft, hop)
    return np.fft.rfftfreq(n_fft, 1 / sr), 10 * np.log10(np.mean(10 ** (S / 10), axis=0))
