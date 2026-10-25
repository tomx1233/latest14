"""Experimental multiband dynamics, separate from shipped CopyFinger.

No fingerprint metric modifications, pitch/time manipulation, noise or modulation.
Parameters are bounded manually authored candidates, not a runtime fit/search.
"""
import numpy as np
from scipy import signal

CANDIDATES = {
    'multiband-gentle': dict(strength=.92, detector_ms=30, drive=2, highpass=35),
    'multiband-dense': dict(strength=1., detector_ms=10, drive=5, highpass=60),
    'multiband-extreme': dict(strength=1., detector_ms=3, drive=15, highpass=100),
    'multiband-midforward': dict(strength=1., detector_ms=10, drive=8, highpass=180),
}


def process(x, sr, settings, *, pitch=0., tempo=1., speed=1.):
    if (pitch,tempo,speed)!=(0.,1.,1.):
        raise ValueError('Experimental processing also forbids pitch/tempo/speed changes')
    if sr<=16000 or x.ndim!=2 or x.shape[1]!=2:
        raise ValueError('Stereo audio above 16 kHz required; no implicit resampling')
    # Causal three-way band split and linked per-band feed-forward dynamics.
    low=signal.sosfilt(signal.butter(2,180,fs=sr,output='sos'),x,axis=0)
    upper=signal.sosfilt(signal.butter(2,1600,fs=sr,output='sos'),x,axis=0)
    out=np.zeros_like(x,dtype=np.float64)
    alpha=np.exp(-1/(sr*settings['detector_ms']/1000))
    # Gains keep the low end below mids/highs; not derived from raw spectral ratios.
    for band,gain in [(low,.45),(upper-low,.8),(x-upper,1.)]:
        power=signal.lfilter([1-alpha],[1,-alpha],np.mean(band*band,axis=1))
        controlled=band*np.maximum(np.sqrt(power),.015)[:,None]**(-settings['strength'])
        out+=gain*np.tanh(controlled*settings['drive'])
    out=signal.sosfilt(signal.butter(2,settings['highpass'],fs=sr,btype='highpass',output='sos'),out,axis=0)
    out=np.tanh(out*1.5)
    assert out.shape==x.shape
    return out
