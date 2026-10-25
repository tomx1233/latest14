import numpy as np
import pytest
from pathlib import Path
from unittest.mock import patch
from reference_v5.target65 import process,selected_process,CANDIDATES65,SELECTED


@pytest.mark.parametrize('sr',[44100,48000])
@pytest.mark.parametrize('frequency',[110,220,440])
def test_fixed_clock_and_original_fundamental_component(sr,frequency):
    t=np.arange(sr*2)/sr
    x=np.column_stack([.2*np.sin(2*np.pi*frequency*t)]*2); before=x.copy()
    y=selected_process(x,sr)
    assert y.shape==x.shape and np.array_equal(x,before)
    assert np.isfinite(y).all()
    spectrum=abs(np.fft.rfft(y[sr:,0]))
    # Distortion may make an upper harmonic dominant. Verify the original
    # fundamental component, not a claim that timbre/perceived pitch is unchanged.
    assert np.argmax(spectrum[frequency-3:frequency+4])+frequency-3==frequency
    assert spectrum[frequency]/spectrum.max()>.05


def test_silence_and_timing_guards():
    x=np.zeros((44100,2))
    assert np.array_equal(selected_process(x,44100),x)
    for kwargs in [dict(pitch=.1),dict(tempo=.99),dict(speed=1.01)]:
        with pytest.raises(ValueError): process(x,44100,CANDIDATES65[SELECTED],**kwargs)


def test_experimental_adapter_is_single_pass_without_checks(tmp_path):
    import soundfile as sf
    import killa_tools as kt
    import reference_v5.target65 as mode
    commands=[]
    def run(args):
        commands.append(args)
        if str(args[-1]).endswith('input.wav'):
            sf.write(args[-1],np.zeros((4410,2)),44100,subtype='FLOAT')
        return 0,'',''
    with patch.object(kt,'_run',side_effect=run),patch.object(kt,'_probe_sweep',side_effect=AssertionError('No API')),patch.object(kt,'_control_check',side_effect=AssertionError('No control')),patch.object(kt,'_result_info',return_value={}),patch.object(kt,'_brand_spectrogram'),patch.object(mode,'selected_process',wraps=mode.selected_process) as dsp:
        r=kt.copyfinger_experimental_process('source.wav',str(tmp_path/'out.ogg'),str(tmp_path/'plot.png'))
    assert dsp.call_count==1
    assert r['verified'] is None and r['counts'] is None
    assert (r['pitch'],r['tempo'],r['speed'])==(0,1,1)
    assert r['delivery_gain_db']==-6
    encode=next(c for c in commands if c[-1]==str(tmp_path/'out.ogg'))
    assert encode[encode.index('-q:a')+1]=='8'
    assert encode[encode.index('-af')+1]=='volume=-6dB'
    assert 'libvorbis' in encode
    with pytest.raises(ValueError): kt.copyfinger_experimental_process('x','bad.mp3','p.png')


def test_experimental_menu_removed_but_offline_experiments_retained():
    source=Path('audio_bot.py').read_text()
    assert 'copyfinger-exp65' not in source
    assert 'Choice(name="Auto-Fit V5 (AfterEffects)", value="autofit-v5")' in source
    assert 'Choice(name="CopyFinger", value="copyfinger")' in source
