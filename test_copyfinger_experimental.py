import numpy as np
import pytest
from reference_v5.experiment import CANDIDATES,process


@pytest.mark.parametrize('sr',[44100,48000])
@pytest.mark.parametrize('name',list(CANDIDATES))
def test_experiment_preserves_clock_and_fundamental(sr,name):
    t=np.arange(2*sr)/sr
    x=np.column_stack([.2*np.sin(2*np.pi*440*t)]*2)
    before=x.copy()
    y=process(x,sr,CANDIDATES[name])
    assert y.shape==x.shape and np.array_equal(x,before)
    assert np.isfinite(y).all()
    assert np.argmax(abs(np.fft.rfft(y[sr:,0])))==440


@pytest.mark.parametrize('name',list(CANDIDATES))
def test_experiment_adds_no_noise_to_silence(name):
    x=np.zeros((48000,2))
    assert np.array_equal(process(x,48000,CANDIDATES[name]),x)


@pytest.mark.parametrize('kw',[dict(pitch=.01),dict(tempo=.99),dict(speed=1.01)])
def test_experiment_rejects_non_normal(kw):
    with pytest.raises(ValueError):
        process(np.zeros((48000,2)),48000,CANDIDATES['multiband-extreme'],**kw)
