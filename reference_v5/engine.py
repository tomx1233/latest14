"""Independent fixed-clock V5 DSP. Not an Audacity/plugin emulation."""
import json
from pathlib import Path
import numpy as np
from scipy import signal

PROFILE = Path(__file__).parent.parent / 'macros' / 'AutoFit V5 Reference.json'

def bands(x, sr):
    # Complementary causal lowpass differences sum exactly to the input.
    lows = [signal.sosfilt(signal.butter(2, f, fs=sr, output='sos'), x, axis=0)
            for f in (60, 180, 1200, 5000)]
    return np.stack([lows[0], *[b-a for a,b in zip(lows,lows[1:])], x-lows[-1]], axis=0)

def process_bands(b, sr, p):
    x = np.einsum('b,bnc->nc', 10**(np.array(p['band_db'])/20), b)
    # Optional linked feed-forward compression, no lookahead or time remapping.
    strength = p.get('compression', 0.)
    if strength:
        power = signal.lfilter([1-np.exp(-1/(sr*.05))], [1,-np.exp(-1/(sr*.05))],
                               np.mean(x*x, axis=1))
        x *= np.maximum(np.sqrt(power), .02)[:,None] ** (-strength)
    drive = 10**(p['drive_db']/20)
    if p['nonlinearity'] == 'hard':
        x = np.clip(x*drive, -1, 1)
    elif p['nonlinearity'] == 'tanh':
        x = np.tanh(x*drive)
    else:
        # Smooth peak limiting, explicitly not a plugin compressor model.
        x = (x*drive)/(1+abs(x*drive)**8)**(1/8)
    return x * 10**(p.get('output_db',0)/20)

def process(x, sr, profile=None):
    p = profile or json.loads(PROFILE.read_text())
    if (p['pitch_semitones'], p['tempo_factor'], p['speed_factor']) != (0.,1.,1.):
        raise ValueError('V5 forbids pitch, tempo and speed changes')
    if sr <= 10000:
        raise ValueError('V5 needs sample rate above 10 kHz; no implicit resampling')
    out = process_bands(bands(x, sr), sr, p)
    assert out.shape == x.shape
    return out
