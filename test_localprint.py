import numpy as np
import pytest
from reference_v5.fingerprint import fingerprint,compare


def music(seed=1,sr=11025):
    rng=np.random.default_rng(seed)
    x=np.zeros(sr*8)
    t=np.arange(sr//2)/sr
    for i in range(16):
        f=rng.choice([220,261.63,293.66,329.63,392,440,493.88])
        n=min(len(t),len(x)-i*(sr//2))
        v=sum(np.sin(2*np.pi*f*k*t[:n])/k for k in range(1,7))
        x[i*(sr//2):i*(sr//2)+n]=v*np.exp(-t[:n]*3)
    return x


def test_self_and_gain():
    x=music(); a=fingerprint(x,11025)
    for y in [x,x*.001,x*12,-x]:
        r=compare(a,fingerprint(y,11025))
        assert r['fingerprint_sha256_equal']
        assert r['whole_overlap']['temporal_bit_agreement']==1
        assert r['whole_overlap']['fixed_key_chroma_cosine']==pytest.approx(1)


def test_different_music_is_less_similar():
    a=fingerprint(music(1),11025)
    r=compare(a,fingerprint(music(4),11025))
    assert not r['fingerprint_sha256_equal']
    assert r['whole_overlap']['temporal_bit_agreement']<.9


def test_silence_is_not_a_match():
    a=fingerprint(np.zeros(11025*4),11025)
    r=compare(a,a)
    assert r['whole_overlap']['status']=='inconclusive_low_information'
    assert r['whole_overlap']['temporal_bit_agreement'] is None
    assert r['whole_overlap']['fixed_key_chroma_cosine'] is None


def test_codec_and_samplerate_controls(tmp_path):
    import soundfile as sf
    from scipy.signal import resample_poly
    x=music(); a=fingerprint(x,11025)
    p=tmp_path/'control.ogg'; sf.write(p,x,11025,format='OGG',subtype='VORBIS')
    y,sr=sf.read(p); r=compare(a,fingerprint(y,sr))
    assert r['whole_overlap']['temporal_bit_agreement']>.75
    assert r['whole_overlap']['fixed_key_chroma_cosine']>.95
    r=compare(a,fingerprint(resample_poly(x,4,1),44100))
    assert r['whole_overlap']['temporal_bit_agreement']>.95


def test_duration_difference_is_reported_not_hidden():
    x=music(); r=compare(fingerprint(x,11025),fingerprint(x[:-11025],11025))
    assert r['duration_difference_seconds']==-1
    assert r['original_frames']>r['converted_frames']
    assert r['whole_overlap']['temporal_bit_agreement']==1
