"""Reproducible controlled fit; run from repository root."""
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal, optimize
from reference_v5.engine import bands, process_bands, process
OUT=Path('reports/reference_v5'); OUT.mkdir(parents=True,exist_ok=True)
x,sr=sf.read('TestSong.ogg',always_2d=True); y,sy=sf.read('NewTest.ogg',always_2d=True)
assert sr==sy

def metrics(a):
    n=len(a)//2205
    env=np.sqrt(np.mean(a[:n*2205].reshape(n,2205,-1)**2,axis=(1,2)))
    f,p=signal.welch(a,fs=sr,nperseg=4096,axis=0); p=p.mean(axis=1)
    edges=[20,40,80,160,320,1280,2560,5120,10240,16000,20000]
    bp=[float(10*np.log10(np.sum(p[(f>=lo)&(f<hi)])+1e-20)) for lo,hi in zip(edges,edges[1:])]
    rms=float(np.sqrt(np.mean(a*a))); peak=float(abs(a).max())
    m=(a[:,0]+a[:,1])/2; s=(a[:,0]-a[:,1])/2
    return dict(samples=len(a),sample_rate=sr,duration=len(a)/sr,rms=rms,peak=peak,
      crest_db=float(20*np.log10(peak/rms)),envelope_range_db=float(np.diff(np.percentile(20*np.log10(env+1e-12),[5,95]))[0]),
      near_one_fraction=float(np.mean((abs(a)>=.9959)&(abs(a)<=1.0235))),
      lr_correlation=float(np.corrcoef(a.T)[0,1]),side_mid_db=float(10*np.log10(np.mean(s*s)/np.mean(m*m))),
      centroid_hz=float(np.sum(f*p)/sum(p)),rolloff95_hz=float(f[np.searchsorted(np.cumsum(p),.95*sum(p))]),band_power_db=bp)

# Eight disjoint one-second excerpts across the song for fit; held-out full song below.
ids=np.concatenate([np.arange(int(t*sr),int((t+1)*sr)) for t in np.linspace(10,138,8)])
b=bands(x,sr)[:,ids,:]; target=y[ids]; tm=metrics(target)
def features(a):
    m=metrics(a)
    return np.r_[np.array(m['band_power_db'])*.35,20*np.log10(m['rms'])*1.5,m['envelope_range_db']*.6,m['crest_db'],m['lr_correlation']*8]
tf=features(target)
rows=[]; best=None
for kind,comp in [('hard',False),('tanh',False),('limiter',True),('hard',True),('tanh',True)]:
    def params(v):
        return dict(band_db=[v[0],v[1],0,v[2],v[3]],drive_db=v[4],output_db=v[5],compression=v[6] if comp else 0,nonlinearity=kind,pitch_semitones=0.,tempo_factor=1.,speed_factor=1.)
    def residual(v):
        return features(process_bands(b,sr,params(v)))-tf
    bounds=([-30,-15,-10,-10,0,-6]+([0] if comp else []),[5,15,25,30,40,2]+([.95] if comp else []))
    fit=optimize.least_squares(residual,[-10,0,8,12,14,0]+([.5] if comp else []),bounds=bounds,max_nfev=65,diff_step=.01)
    score=float(np.mean(residual(fit.x)**2)); p=params(fit.x)
    rows.append(dict(kind=kind,compression_enabled=comp,score=score,profile=p))
    print(kind,comp,score,p,flush=True)
    if best is None or score<best[0]: best=(score,p)
p=best[1]; Path('macros/AutoFit V5 Reference.json').write_text(json.dumps(p,indent=2)+'\n')
z=process(x,sr,p)
sf.write(OUT/'TestSong-reference.wav',z,sr,subtype='FLOAT')
# Identical attenuation for reference/output listening, not source-loudness matching.
for name,a in [('TestSong-preview',z),('NewTest-preview',y)]: sf.write(OUT/(name+'.wav'),a*10**(-15/20),sr,subtype='PCM_24')
# Genuine normalized band-limited local correlation, lag and runner-up confidence.
alignment=[]
sos=signal.butter(3,[200,1000],fs=sr,btype='bandpass',output='sos')
for t in [10,40,70,100,130]:
    a=signal.sosfilt(sos,x[int(t*sr):int((t+2)*sr)].mean(axis=1))[1000:]
    c=signal.sosfilt(sos,y[int(t*sr):int((t+2)*sr)].mean(axis=1))[1000:]
    cor=signal.correlate(c,a,method='fft'); lags=signal.correlation_lags(len(c),len(a)); sel=abs(lags)<2205
    cor=cor[sel]/np.sqrt(np.dot(a,a)*np.dot(c,c)); lags=lags[sel]; k=np.argmax(cor)
    alignment.append(dict(time=t,lag_samples=int(lags[k]),normalized_correlation=float(cor[k])))
report=dict(original=metrics(x),reference=metrics(y),output=metrics(z),candidates=rows,alignment=alignment,profile=p)
(OUT/'measurements.json').write_text(json.dumps(report,indent=2))
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axs=plt.subplots(3,1,figsize=(13,10),sharex=True,sharey=True)
for ax,a,title in zip(axs,[x,y,z],['Original','Reference','V5 output']):
    f,t,s=signal.spectrogram(a.mean(axis=1),sr,nperseg=2048,noverlap=1024)
    im=ax.pcolormesh(t,f,10*np.log10(s+1e-15),vmin=-100,vmax=-20,shading='auto',cmap='magma'); ax.set_ylim(20,20000); ax.set_yscale('log'); ax.set_title(title); ax.set_ylabel('Hz')
axs[-1].set_xlabel('Seconds'); fig.colorbar(im,ax=axs,label='PSD dB/Hz (same scale)'); fig.savefig(OUT/'spectrograms.png',dpi=140)
