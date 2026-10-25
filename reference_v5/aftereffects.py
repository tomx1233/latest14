"""Auto-Fit V5 frequency/dynamics profile, distinct from CopyFinger's profile."""
import json
from pathlib import Path
import numpy as np
from scipy import signal
from reference_v5.engine import bands

PROFILE=Path(__file__).parent.parent/'macros'/'AutoFit V5 AfterEffects.json'


def process_bands(b,sr,p):
    x=np.einsum('b,bnc->nc',10**(np.asarray(p['band_db'])/20),b)
    strength=p.get('compression',0.)
    if strength:
        alpha=np.exp(-1/(sr*.05))
        power=signal.lfilter([1-alpha],[1,-alpha],np.mean(x*x,axis=1))
        x*=np.maximum(np.sqrt(power),.02)[:,None]**(-strength)
    x*=10**(p['drive_db']/20)
    if p['nonlinearity']=='tanh': x=np.tanh(x)
    elif p['nonlinearity']!='linear': raise ValueError('Unknown V5 nonlinearity')
    mid=x.mean(axis=1); side=(x[:,0]-x[:,1])*.5*p['side_gain']
    return np.column_stack([mid+side,mid-side])*10**(p['output_db']/20)


def process(x,sr,profile=None):
    p=profile or json.loads(PROFILE.read_text())
    if (p['pitch_semitones'],p['tempo_factor'],p['speed_factor'])!=(0,1,1):
        raise ValueError('V5 forbids pitch, tempo and speed changes')
    if x.ndim!=2 or x.shape[1]!=2 or sr<=10000: raise ValueError('V5 requires stereo above 10 kHz')
    y=process_bands(bands(x,sr),sr,p)
    assert y.shape==x.shape
    return y


def run(input_path,output_path,spectrogram_path,progress=None):
    from reference_v5.bot import run as adapter
    return adapter(input_path,output_path,spectrogram_path,progress,processor=process,
                   profile_name='Auto-Fit V5 (AfterEffects)',delivery_gain_db=-1.5,
                   ogg_quality=8 if Path(output_path).suffix.lower()=='.ogg' else None)
