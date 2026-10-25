import json
from pathlib import Path
import numpy as np
import pytest
from reference_v5.reference3 import process,PROFILE

P=json.loads(PROFILE.read_text())

@pytest.mark.parametrize('sr',[44100,48000])
def test_reference3_preserves_clock_pitch_and_explicit_mono(sr):
    t=np.arange(sr*2)/sr
    x=np.column_stack([.1*np.sin(2*np.pi*440*t),.2*np.sin(2*np.pi*440*t)])
    before=x.copy(); y=process(x,sr)
    assert y.shape==x.shape and np.array_equal(x,before)
    assert np.array_equal(y[:,0],y[:,1])
    assert np.argmax(abs(np.fft.rfft(y[sr:,0])))==440

@pytest.mark.parametrize('key,value',[('pitch_semitones',.01),('tempo_factor',.99),('speed_factor',1.01)])
def test_reference3_rejects_non_normal(key,value):
    p=dict(P); p[key]=value
    with pytest.raises(ValueError): process(np.zeros((44100,2)),44100,p)


def test_reference3_is_explicit_not_automatic():
    default=json.loads(Path('macros/AutoFit V5 Reference.json').read_text())
    assert default['compression']==pytest.approx(.8764585197932326)
    assert 'mono_mean' not in Path('reference_v5/bot.py').read_text()
    assert not np.any(process(np.zeros((44100,2)),44100))
