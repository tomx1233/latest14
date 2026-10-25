"""Fixed-clock invariants and recognition outcomes, without live API calls."""
import copy
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pytest
from reference_v5.engine import process, PROFILE

P = json.loads(PROFILE.read_text())

@pytest.mark.parametrize('sr', [44100,48000])
@pytest.mark.parametrize('kind', ['hard','tanh','limiter'])
@pytest.mark.parametrize('compression', [0,.5,.95])
def test_every_candidate_preserves_clock(kind, compression, sr):
    t=np.arange(sr*2)/sr
    x=np.column_stack([.2*np.sin(2*np.pi*440*t)]*2)
    p=dict(P,nonlinearity=kind,compression=compression)
    y=process(x,sr,p)
    assert y.shape==x.shape
    # Nonlinearity may add harmonics, but must not move the fundamental.
    spec=abs(np.fft.rfft(y[sr:,0])); assert np.argmax(spec)==440
    assert (p['pitch_semitones'],p['tempo_factor'],p['speed_factor'])==(0,1,1)

@pytest.mark.parametrize('key,value',[('pitch_semitones',.01),('tempo_factor',.999),('speed_factor',1.001)])
def test_reject_non_normal(key,value):
    p=copy.deepcopy(P); p[key]=value
    with pytest.raises(ValueError): process(np.zeros((100,2)),44100,p)

@pytest.mark.parametrize('clean,counts,control',[(True,[0,0],True),(True,[0],False),(False,[None],None),(False,[1],True)])
def test_recognition_never_changes_dsp(tmp_path,clean,counts,control):
    import soundfile as sf
    import killa_tools as kt
    import reference_v5.bot as bot
    source=tmp_path/'input.wav'; out=tmp_path/'output.wav'; pic=tmp_path/'pic.png'
    sf.write(source,np.zeros((4410,2)),44100)
    rendered=[]
    def command(args):
        if str(args[-1]).endswith('input.wav'):
            sf.write(args[-1],np.zeros((4410,2)),44100,subtype='FLOAT')
        return 0,'',''
    real=bot.process
    def spy(x,sr):
        y=real(x,sr); rendered.append(y); return y
    with patch.object(kt,'_run',side_effect=command),patch.object(kt,'_probe_sweep',return_value=(clean,counts)),patch.object(kt,'_gapfree_windows',return_value=[0]),patch.object(kt,'_control_check',return_value=control),patch.object(kt,'_result_info',return_value={}),patch.object(kt,'_brand_spectrogram'),patch.object(bot,'process',side_effect=spy):
        r=bot.run(str(source),str(out),str(pic))
    assert len(rendered)==1
    assert (r['pitch'],r['tempo'],r['speed'])==(0,1,1)
    assert r['clean']==clean and r['verified'] is control

def test_old_modes_unchanged():
    import subprocess
    for name in ['audacity_processor.py','audacity_pipe.py','macros/CopyR8 AutoFit V3.txt','macros/CopyR8 AutoFit V4.txt']:
        assert Path(name).read_bytes()==subprocess.check_output(['git','show','49c6bc5:'+name])
    old=subprocess.check_output(['git','show','49c6bc5:killa_tools.py']).decode()
    # Downloader behavior is intentionally changing; legacy effect/search graphs are not.
    import ast
    baseline={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(old).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    current={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(Path('killa_tools.py').read_text()).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    for name,body in baseline.items():
        if name not in {'download_media','_err_hint'}:
            assert current[name]==body, name


def test_copyfinger_is_one_pass_without_recognition(tmp_path):
    import soundfile as sf
    import killa_tools as kt
    import reference_v5.bot as bot
    source=tmp_path/'source.wav'
    sf.write(source,np.zeros((4410,2)),44100)
    def command(args):
        if str(args[-1]).endswith('input.wav'):
            sf.write(args[-1],np.zeros((4410,2)),44100,subtype='FLOAT')
        return 0,'',''
    with patch.object(kt,'_run',side_effect=command),patch.object(kt,'_probe_sweep',side_effect=AssertionError('No API allowed')),patch.object(kt,'_control_check',side_effect=AssertionError('No control allowed')),patch.object(kt,'_gapfree_windows',side_effect=AssertionError('No windows allowed')),patch.object(kt,'_result_info',return_value={}),patch.object(kt,'_brand_spectrogram'),patch.object(bot,'process',wraps=bot.process) as dsp:
        r=kt.copyfinger_process(str(source),str(tmp_path/'out.mp3'),str(tmp_path/'pic.png'))
    assert dsp.call_count==1
    assert (r['pitch'],r['tempo'],r['speed'])==(0,1,1)
    assert r['counts'] is None and r['verified'] is None


def test_copyfinger_menu_is_a_fixed_preset():
    s=Path('audio_bot.py').read_text()
    assert 'Choice(name="CopyFinger", value="copyfinger")' in s
    assert 'Choice(name="Auto-Fit V5 (AfterEffects)", value="autofit-v5")' in s
    line=next(line for line in s.splitlines() if 'is_autofit = preset in' in line)
    assert 'copyfinger' not in line


@pytest.mark.parametrize('clean,counts,control,status', [
    (True,[0,0],True,'verified_no_match'),
    (True,[0,0],False,'unverified'),
    (True,[0,0],None,'unverified'),
    (False,[None],True,'unverified'),
    (False,[1],True,'recognized'),
])
def test_host_delivery_check_keeps_tristate(clean,counts,control,status):
    from types import SimpleNamespace
    from reference_v5.check_delivery import check
    from unittest.mock import Mock
    kt=SimpleNamespace(_gapfree_windows=Mock(return_value=[0.,10.]),
        _control_check=Mock(return_value=control),
        _probe_sweep=Mock(return_value=(clean,counts)),
        active_recognition_providers=Mock(return_value=['ShazamIO']))
    assert check('source.mp3','converted.mp3',kt,progress=None)['status']==status
    kt._probe_sweep.assert_called_once_with('converted.mp3',[0.,10.],progress=None)
