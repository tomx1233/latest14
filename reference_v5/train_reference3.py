"""Bounded tonal/dynamic fit to actual reference 3, not LocalPrint minimization.

Offline experiment only; never modifies the shipped CopyFinger profile.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

import numpy as np
from scipy import signal,optimize
import soundfile as sf
from reference_v5.engine import bands,process_bands,process as baseline_process
from reference_v5.reference3 import process
from reference_v5.test_tracks import metrics
from reference_v5.fingerprint import fingerprint,compare

OUT=Path('reports/reference3')
NEWPROFILE=Path('macros/CopyFinger Reference3 Experimental.json')


def features(a,sr):
    m=metrics(a,sr)
    f,p=signal.welch(a,fs=sr,nperseg=4096,axis=0); p=p.mean(axis=1)
    edges=[20,40,80,160,320,1280,2560,5120,10240,16000,20000]
    levels=[10*np.log10(np.sum(p[(f>=lo)&(f<hi)])+1e-20) for lo,hi in zip(edges,edges[1:])]
    return np.r_[np.array(levels)*.35,m['rms_dbfs']*1.5,m['envelope_p95_p5_db']*.6,m['crest_db'],m['lr_correlation']*8]


def main():
    import killa_tools as kt
    OUT.mkdir(parents=True,exist_ok=True)
    inputs=['newtestoriginal3.ogg','newtestmodified3.ogg','macros/AutoFit V5 Reference.json','reference_v5/fingerprint.py']
    hashes={name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in inputs}
    x,sr=sf.read(inputs[0],always_2d=True); y,sy=sf.read(inputs[1],always_2d=True)
    if sr!=sy or x.shape!=y.shape:
        raise ValueError('This fit requires equal sample rate and decoded sample count; never align by stretching')
    # 16 continuous two-second excerpts; alternating train/validation sets.
    starts=np.linspace(8,len(x)/sr-8,16)
    targets=[y[int(t*sr):int((t+2)*sr)] for t in starts]
    train_target=features(np.concatenate(targets[::2]),sr)
    val_target=features(np.concatenate(targets[1::2]),sr)
    rows=[]
    for mode,kind in [('linked_stereo','tanh'),('mono_mean','hard'),('mono_mean','tanh'),('mono_mean','limiter')]:
        cache=[]
        for t in starts:
            a=x[int((t-.5)*sr):int((t+2)*sr)]
            if mode=='mono_mean': a=np.repeat(a.mean(axis=1,keepdims=True),2,axis=1)
            cache.append(bands(a,sr))
        def params(v):
            return dict(band_db=[v[0],v[1],0,v[2],v[3]],drive_db=float(v[4]),output_db=float(v[5]),compression=float(v[6]),nonlinearity=kind,stereo_mode=mode,pitch_semitones=0.,tempo_factor=1.,speed_factor=1.)
        def render(v,indices):
            return np.concatenate([process_bands(cache[i],sr,params(v))[round(.5*sr):] for i in indices])
        def residual(v): return features(render(v,range(0,16,2)),sr)-train_target
        fit=optimize.least_squares(residual,[-6,0,6,6,5,0,.3],bounds=([-30,-24,-15,-15,-15,-8,0],[10,24,24,30,35,4,.95]),max_nfev=65,diff_step=.01)
        train=float(np.mean(residual(fit.x)**2))
        validation=float(np.mean((features(render(fit.x,range(1,16,2)),sr)-val_target)**2))
        row=dict(profile=params(fit.x),train_score=train,validation_score=validation,nfev=int(fit.nfev))
        rows.append(row); print(mode,kind,train,validation,flush=True)
    best=min(rows,key=lambda r:r['validation_score'])
    NEWPROFILE.write_text(json.dumps(best['profile'],indent=2)+'\n')
    z=process(x,sr,best['profile']); baseline=baseline_process(x,sr)
    original_print=fingerprint(x,sr)
    # Broad timing diagnostic, no offset applied and no proof of fine tuning.
    timing=[]
    sos=signal.butter(3,[200,1000],fs=sr,btype='bandpass',output='sos')
    for t in np.linspace(10,len(x)/sr-12,5):
        a=signal.sosfilt(sos,x[int(t*sr):int((t+2)*sr)].mean(axis=1))[1000:]
        b=signal.sosfilt(sos,y[int(t*sr):int((t+2)*sr)].mean(axis=1))[1000:]
        a-=a.mean(); b-=b.mean(); c=signal.correlate(b,a,method='fft')/np.sqrt(np.dot(a,a)*np.dot(b,b)); lag=signal.correlation_lags(len(b),len(a)); keep=abs(lag)<2205; c=c[keep]; lag=lag[keep]; k=np.argmax(c)
        timing.append(dict(time_seconds=float(t),best_lag_samples=int(lag[k]),normalized_correlation=float(c[k]),zero_lag_correlation=float(c[lag==0][0])))
    # First-pair cross-check: proves this profile is not automatically universal.
    old,sold=sf.read('TestSong.ogg',always_2d=True); oldref,_=sf.read('NewTest.ogg',always_2d=True)
    oldout=process(old,sold,best['profile'])
    result=dict(input_sha256=hashes,train_starts=starts[::2].tolist(),validation_starts=starts[1::2].tolist(),candidates=rows,selected_profile=best['profile'],
        original=metrics(x,sr),reference=metrics(y,sr),baseline=metrics(baseline,sr),fitted=metrics(z,sr),
        full_song_baseline_objective=float(np.mean((features(baseline,sr)-features(y,sr))**2)),
        full_song_fitted_objective=float(np.mean((features(z,sr)-features(y,sr))**2)),
        localprint_actual_pair=compare(original_print,fingerprint(y,sr)),localprint_fitted=compare(original_print,fingerprint(z,sr)),
        timing=timing,first_pair_crosscheck=dict(reference=metrics(oldref,sold),new_profile_output=metrics(oldout,sold)),
        live_recognition='NOT TESTED; reference fitting, not fingerprint-score optimization')
    with tempfile.TemporaryDirectory() as tmp:
        wav=Path(tmp)/'audio.wav'
        sf.write(wav,z,sr,subtype='FLOAT')
        dest=OUT/'newtestoriginal3_CopyFinger-reference3.ogg'
        subprocess.run(kt._FFMPEG+['-i',str(wav)]+kt._CLEAN_META_FLAGS+['-c:a','libvorbis','-q:a','8',str(dest)],check=True)
        decoded,dsr=sf.read(dest,always_2d=True)
        assert dsr==sr and len(decoded)==len(x)
        result['delivery']=metrics(decoded,dsr)
        for name,a in [('Original',x),('Reference',y),('Fitted',z),('Baseline',baseline)]:
            sf.write(wav,a*10**(-24/20)/np.sqrt(np.mean(a*a)),sr,subtype='PCM_24')
            subprocess.run(kt._FFMPEG+['-i',str(wav)]+kt._CLEAN_META_FLAGS+['-c:a','libvorbis','-q:a','6',str(OUT/(name+'-matched.ogg'))],check=True)
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(4,1,figsize=(13,11),sharex=True,sharey=True)
    for ax,a,name in zip(axs,[x,y,baseline,z],['Original3','Modified3 reference','Existing CopyFinger','Reference3 experiment']):
        f,t,p=signal.spectrogram(a.mean(axis=1),sr,nperseg=2048,noverlap=1024)
        im=ax.pcolormesh(t,f,10*np.log10(p+1e-15),vmin=-100,vmax=-20,shading='auto',cmap='magma'); ax.set_ylim(20,20000); ax.set_yscale('log'); ax.set_title(name)
    axs[-1].set_xlabel('seconds'); fig.colorbar(im,ax=axs,label='PSD dB/Hz (identical scale)'); fig.savefig(OUT/'spectrograms.png',dpi=130)
    assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())
    (OUT/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Selected',best['profile']); print('Full objectives',result['full_song_baseline_objective'],result['full_song_fitted_objective'])
    print('Reference',result['reference']); print('Fitted',result['fitted'])

if __name__=='__main__': main()
