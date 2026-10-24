"""Offline whole-track CopyFinger validation. No recognition or parameter search.

python -m reference_v5.test_tracks
Produces delivery renders, matched listening copies, metrics and same-scale PSDs.
No lookup outcome is inferred from acoustic similarity statistics.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import numpy as np
from scipy import signal
import soundfile as sf

from reference_v5.engine import process, PROFILE

OUT = Path('reports/copyfinger_newsong2')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def metrics(a, sr):
    rms = float(np.sqrt(np.mean(a*a)))
    peak = float(np.max(np.abs(a)))
    n = round(sr*.05)
    frame = a[:len(a)//n*n].reshape(-1,n,a.shape[1])
    env = np.sqrt(np.mean(frame*frame,axis=(1,2)))
    f,p = signal.welch(a,fs=sr,nperseg=4096,axis=0)
    p = p.mean(axis=1)
    return dict(samples=len(a), sample_rate=sr, channels=a.shape[1],
        duration_seconds=len(a)/sr, rms=rms, rms_dbfs=float(20*np.log10(rms+1e-20)),
        sample_peak=peak, crest_db=float(20*np.log10(peak/(rms+1e-20))),
        envelope_p95_p5_db=float(np.diff(np.percentile(20*np.log10(env+1e-20),[5,95]))[0]),
        lr_correlation=float(np.corrcoef(a.T)[0,1]),
        centroid_hz=float(np.sum(f*p)/sum(p)),
        rolloff95_hz=float(f[np.searchsorted(np.cumsum(p),.95*sum(p))]))

def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import killa_tools as kt
    import reference_v5.bot as bot
    OUT.mkdir(parents=True,exist_ok=True)
    report = dict(profile_sha256=digest(PROFILE),pitch_semitones=0,tempo_factor=1,
                  speed_factor=1,live_recognition='NOT RUN: network allowlist excludes recognition services; no API key configured',tracks=[])
    fig,axes=plt.subplots(2,2,figsize=(14,8),sharey=True)
    for row,source in enumerate(['TestSong.ogg','newsong2.mp3']):
        original_hash=digest(source)
        stem=Path(source).stem
        delivery=OUT/(stem+'_CopyFinger.mp3')
        picture=OUT/(stem+'_delivery_spectrogram.png')
        calls=[]
        real_process=bot.process
        def capture(a,sr):
            z=real_process(a,sr)
            calls.append(dict(sample_rate=sr,input_samples=len(a),output_samples=len(z)))
            return z
        # Any accidental recognition or shift call makes this validation fail.
        with patch.object(bot,'process',side_effect=capture), \
             patch.object(kt,'_probe_sweep',side_effect=AssertionError('Unexpected API call')), \
             patch.object(kt,'_control_check',side_effect=AssertionError('Unexpected control call')), \
             patch.object(kt,'_render_shifted_wav',side_effect=AssertionError('Unexpected shift')):
            result=kt.copyfinger_process(source,str(delivery),str(picture),print)
        assert len(calls)==1 and calls[0]['input_samples']==calls[0]['output_samples']
        assert digest(source)==original_hash
        x,sr=sf.read(source,always_2d=True)
        z=process(x,sr)
        sf.write(OUT/(stem+'_validation.wav'),z,sr,subtype='FLOAT')
        d,dsr=sf.read(delivery,always_2d=True)
        assert dsr==sr
        # Whole-song overlapping 12-second diagnostic windows, 6-second hop.
        # NO API requests; these RMS comparisons are not recognition checks.
        windows=[]
        duration=len(x)/sr
        starts=list(np.arange(0,max(duration-12,0),6))+[max(duration-12,0)]
        for t in starts:
            a=x[int(t*sr):int((t+12)*sr)]; b=z[int(t*sr):int((t+12)*sr)]
            windows.append(dict(start_seconds=float(t),source_rms_dbfs=metrics(a,sr)['rms_dbfs'],output_rms_dbfs=metrics(b,sr)['rms_dbfs']))
        # Local zero-lag normalized waveform correlation; not a fingerprint score.
        correlation=[]
        for t in np.linspace(5,max(5,duration-7),5):
            a=x[int(t*sr):int((t+2)*sr)].mean(axis=1)
            b=z[int(t*sr):int((t+2)*sr)].mean(axis=1)
            a-=a.mean(); b-=b.mean()
            correlation.append(dict(start_seconds=float(t),zero_lag_correlation=float(np.dot(a,b)/np.sqrt(np.dot(a,a)*np.dot(b,b)))))
        for col,(a,title) in enumerate([(x,'Original'),(z,'CopyFinger validation')]):
            f,t,p=signal.spectrogram(a.mean(axis=1),sr,nperseg=2048,noverlap=1024)
            ax=axes[row,col]
            im=ax.pcolormesh(t,f,10*np.log10(p+1e-15),vmin=-100,vmax=-20,cmap='magma',shading='auto')
            ax.set_yscale('log'); ax.set_ylim(20,20000); ax.set_xlabel('seconds'); ax.set_ylabel('Hz'); ax.set_title(stem+' — '+title)
            rms=np.sqrt(np.mean(a*a))
            gain=10**(-24/20)/rms
            # Reduce both copies further if necessary, using the same RMS target.
            # These supplied tracks both fit at -24 dBFS RMS.
            assert np.max(np.abs(a*gain))<1
            with tempfile.TemporaryDirectory() as tmp:
                preview=Path(tmp)/'preview.wav'
                sf.write(preview,a*gain,sr,subtype='PCM_24')
                dest=OUT/(stem+('_original_matched.ogg' if col==0 else '_CopyFinger_matched.ogg'))
                subprocess.run([kt._FFMPEG_BIN,'-v','error','-y','-i',str(preview),'-map_metadata','-1','-c:a','libvorbis','-q:a','6',str(dest)],check=True)
        # FFmpeg decodes MP3 with gapless metadata; count any residual codec padding.
        report['tracks'].append(dict(source=source,source_sha256=original_hash,
             delivery=str(delivery),source_untouched=True,dsp_calls=calls,
             original=metrics(x,sr),validation=metrics(z,sr),delivery_metrics=metrics(d,dsr),
             delivery_minus_input_samples=len(d)-len(x),recognition=result['verified'],
             diagnostic_windows=windows,waveform_correlations=correlation,
             delivery_info=result['info']))
        print(stem,report['tracks'][-1]['original'],report['tracks'][-1]['validation'],flush=True)
    fig.colorbar(im,ax=axes.ravel().tolist(),label='PSD dB/Hz (identical scale)')
    fig.savefig(OUT/'spectrograms.png',dpi=130)
    (OUT/'measurements.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Saved',OUT/'measurements.json')

if __name__=='__main__':
    main()
