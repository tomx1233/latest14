import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pytest
from reference_v5.aftereffects import process,PROFILE

@pytest.mark.parametrize('sr',[44100,48000])
def test_v5_clock_and_fundamental(sr):
    t=np.arange(sr*2)/sr;x=np.column_stack([.1*np.sin(2*np.pi*440*t)]*2)
    before=x.copy();y=process(x,sr)
    assert y.shape==x.shape and np.array_equal(x,before)
    assert np.argmax(abs(np.fft.rfft(y[sr:,0])))==440
    assert np.isfinite(y).all()

@pytest.mark.parametrize('key,value',[('pitch_semitones',.01),('tempo_factor',.99),('speed_factor',1.01)])
def test_v5_timing_locked(key,value):
    p=json.loads(PROFILE.read_text());p[key]=value
    with pytest.raises(ValueError):process(np.zeros((48000,2)),48000,p)

@pytest.mark.parametrize('clean,counts,known',[(True,[0],True),(True,[0],False),(False,[None],None),(False,[1],True)])
def test_v5_uses_new_graph_once_without_recognition_shifts(tmp_path,clean,counts,known):
    import soundfile as sf
    import killa_tools as kt
    import reference_v5.aftereffects as v5
    def command(args):
        if str(args[-1]).endswith('input.wav'):
            sf.write(args[-1],np.zeros((4800,2)),48000,subtype='FLOAT')
        return 0,'',''
    with patch.object(kt,'_run',side_effect=command),patch.object(kt,'_probe_sweep',return_value=(clean,counts)) as sweep,patch.object(kt,'_control_check',return_value=known) as control,patch.object(kt,'_gapfree_windows',return_value=[0,10]),patch.object(kt,'_result_info',return_value={}),patch.object(kt,'_brand_spectrogram'),patch.object(v5,'process',wraps=v5.process) as dsp,patch.object(kt,'_render_shifted_wav',side_effect=AssertionError('No shifts')):
        out=str(tmp_path/'v5.ogg');r=kt.copyr8_autofit_v5('original.ogg',out,str(tmp_path/'pic.png'))
    assert dsp.call_count==1
    assert r['clean']==clean and r['verified'] is known
    assert (r['pitch'],r['tempo'],r['speed'])==(0,1,1)
    sweep.assert_called_once_with(out,[0,10],progress=None)
    control.assert_called_once_with('original.ogg',progress=None)


def test_copyfinger_profile_still_original():
    p=json.loads(Path('macros/AutoFit V5 Reference.json').read_text())
    assert p['compression']==pytest.approx(.8764585197932326)
    assert PROFILE.name=='AutoFit V5 AfterEffects.json'
