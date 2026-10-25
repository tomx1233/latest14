"""Fixed-clock exploratory distortion profiles. No promised recognition cap."""
import numpy as np
from scipy import signal
from reference_v5.experiment import process as multiband,CANDIDATES

CANDIDATES65={
    'dense-quantized':dict(low=60,high=16000,levels=3,stages=1),
    'midrange':dict(low=250,high=4500,levels=7,stages=1),
    'telephone':dict(low=400,high=3000,levels=3,stages=1),
    'stacked-midrange':dict(low=250,high=4500,levels=7,stages=3),
    'stacked-six':dict(low=250,high=4500,levels=7,stages=6),
    'stacked-seven':dict(low=250,high=4500,levels=7,stages=7),
    'stacked-ten':dict(low=250,high=4500,levels=7,stages=10),
    'stacked-telephone':dict(low=400,high=3000,levels=3,stages=6),
}


def process(x,sr,settings,*,pitch=0.,tempo=1.,speed=1.):
    if (pitch,tempo,speed)!=(0.,1.,1.):
        raise ValueError('Pitch, tempo and speed must remain normal')
    y=multiband(x,sr,CANDIDATES['multiband-extreme'],pitch=pitch,tempo=tempo,speed=speed)
    high=min(settings['high'],sr*.45)
    sos=signal.butter(2,[settings['low'],high],fs=sr,btype='bandpass',output='sos')
    for _ in range(settings['stages']):
        y=signal.sosfilt(sos,y,axis=0)
        y=np.tanh(y*4)
        # Amplitude quantization only: no sample-rate reduction or clock changes.
        levels=settings['levels']
        y=np.round(y*levels)/levels
    assert y.shape==x.shape
    return y*.5


# Fixed deployed settings; no runtime search or score calculation.
SELECTED = 'stacked-seven'

def selected_process(x,sr):
    return process(x,sr,CANDIDATES65[SELECTED])
