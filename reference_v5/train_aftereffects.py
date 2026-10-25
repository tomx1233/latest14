"""Frequency/dynamics fitting only. Analyzed reference offset is NEVER exported."""
import json,hashlib,subprocess,tempfile,gc
from pathlib import Path
import numpy as np
from scipy import optimize
import soundfile as sf
from reference_v5.aftereffects import process_bands,process,PROFILE
from reference_v5.engine import bands,process as copyfinger
from reference_v5.train_reference3 import features
from reference_v5.test_tracks import metrics

OUT=Path('reports/autofit_v5')


def main():
    import killa_tools as kt
    OUT.mkdir(parents=True,exist_ok=True)
    paths=['beforeeffects.ogg','aftereffects.ogg','macros/AutoFit V5 Reference.json']
    hashes={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
    x,sr=sf.read(paths[0],always_2d=True);y,sy=sf.read(paths[1],always_2d=True);assert sr==sy
    offset=-.29 # analysis-only envelope landmark estimate; not a DSP delay
    starts=np.linspace(10,len(x)/sr-12,12)
    cache=[bands(x[int((t-.5)*sr):int((t+2)*sr)],sr) for t in starts]
    targets=[y[int((t+offset)*sr):int((t+offset+2)*sr)] for t in starts]
    ft=features(np.concatenate(targets[::2]),sr);fv=features(np.concatenate(targets[1::2]),sr)
    rows=[]
    for kind in ['linear','tanh']:
        def params(v):
            return dict(band_db=[v[0],v[1],0,v[2],v[3]],drive_db=float(v[4]) if kind=='tanh' else 0.,output_db=float(v[5]),compression=float(v[6]),side_gain=float(v[7]),nonlinearity=kind,pitch_semitones=0.,tempo_factor=1.,speed_factor=1.)
        def render(v,indices): return np.concatenate([process_bands(cache[i],sr,params(v))[round(.5*sr):] for i in indices])
        def residual(v): return features(render(v,range(0,12,2)),sr)-ft
        # Linear mode has a redundant frozen drive coordinate; tighten bounds.
        lo=[-24,-20,-24,-30,-15,-16,0,0];hi=[20,20,20,20,30,6,.8,1.5]
        fit=optimize.least_squares(residual,[0,0,-2,-4,0,-2,.01,.65],bounds=(lo,hi),max_nfev=45,diff_step=.01)
        row=dict(profile=params(fit.x),train_score=float(np.mean(residual(fit.x)**2)),validation_score=float(np.mean((features(render(fit.x,range(1,12,2)),sr)-fv)**2)))
        rows.append(row);print(kind,row,flush=True)
    best=min(rows,key=lambda r:r['validation_score'])
    del cache;gc.collect()
    z=process(x,sr,best['profile'])
    # Explicit full-song stereo refinement, not independent validation.
    mid=z.mean(axis=1);side=(z[:,0]-z[:,1])*.5
    vm=float(np.var(mid));vs=float(np.var(side));cov=float(np.mean((mid-mid.mean())*(side-side.mean())))
    target_corr=float(np.corrcoef(y.T)[0,1])
    def corr(f): return (vm-f*f*vs)/np.sqrt((vm+f*f*vs)**2-4*f*f*cov*cov)
    scale=optimize.brentq(lambda f:corr(f)-target_corr,.001,3.)
    final_profile=dict(best['profile']);final_profile['side_gain']*=scale
    PROFILE.write_text(json.dumps(final_profile,indent=2)+'\n')
    del z,mid,side;gc.collect()
    z=process(x,sr);old=copyfinger(x,sr)
    report=dict(input_sha256=hashes,analysis_only_reference_offset_seconds=offset,
        train_starts=starts[::2].tolist(),validation_starts=starts[1::2].tolist(),candidates=rows,
        selected_profile=final_profile,full_song_stereo_refinement_scale=scale,original=metrics(x,sr),reference_entire=metrics(y,sr),
        fitted_entire=metrics(z,sr),copyfinger=metrics(old,sr),
        note='No reference offset/tail/tuning applied to output. No live recognition or subjective listening.',
        musical_timing='No clock change, time stretch, sample shift, crop or padding')
    with tempfile.TemporaryDirectory() as tmp:
        wav=Path(tmp)/'processed.wav';sf.write(wav,z,sr,subtype='FLOAT')
        dest=OUT/'beforeeffects_AutoFitV5.ogg'
        subprocess.run(kt._FFMPEG+['-i',str(wav),'-af','volume=-1.5dB']+kt._CLEAN_META_FLAGS+['-c:a','libvorbis','-q:a','8',str(dest)],check=True)
        decoded,dsr=sf.read(dest,always_2d=True);assert dsr==sr and decoded.shape==x.shape
        report['delivery']=metrics(decoded,dsr);del decoded
        for name,a in [('Original',x),('Reference',y),('AutoFitV5',z),('CopyFinger',old)]:
            sf.write(wav,a*10**(-24/20)/np.sqrt(np.mean(a*a)),sr,subtype='PCM_24')
            subprocess.run(kt._FFMPEG+['-i',str(wav)]+kt._CLEAN_META_FLAGS+['-c:a','libvorbis','-q:a','6',str(OUT/(name+'-matched.ogg'))],check=True)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from scipy import signal
    fig,axs=plt.subplots(4,1,figsize=(13,11),sharex=True,sharey=True)
    for ax,a,name in zip(axs,[x,y,old,z],['BeforeEffects','AfterEffects reference','Unchanged CopyFinger','New Auto-Fit V5']):
        f,t,p=signal.spectrogram(a.mean(axis=1),sr,nperseg=2048,noverlap=1024)
        im=ax.pcolormesh(t,f,10*np.log10(p+1e-15),vmin=-100,vmax=-20,cmap='magma',shading='auto');ax.set_ylim(20,20000);ax.set_yscale('log');ax.set_title(name)
    axs[-1].set_xlabel('seconds');fig.colorbar(im,ax=axs,label='PSD dB/Hz (same scale)');fig.savefig(OUT/'spectrograms.png',dpi=130)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    (OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Reference',report['reference_entire']);print('Fitted',report['fitted_entire'])

if __name__=='__main__':main()
