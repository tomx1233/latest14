"""Supplemental diagnostics and listening copies; no timeline modifications."""
import json,subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal
import imageio_ffmpeg
out=Path('reports/reference_v5'); r=json.loads((out/'measurements.json').read_text())
x,sr=sf.read('TestSong.ogg'); y,_=sf.read('NewTest.ogg'); z,_=sf.read(out/'TestSong-reference.wav')
extra={'format_headers':{},'envelope_alignment':[]}
for name in ['TestSong.ogg','NewTest.ogg']:
    p=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-i',name],capture_output=True,text=True)
    extra['format_headers'][name]=p.stderr
# Correlate 10-ms band-energy envelopes, genuine normalization, no offset applied.
for lo,hi in [(80,300),(300,1200),(1200,5000)]:
    sos=signal.butter(3,[lo,hi],fs=sr,btype='bandpass',output='sos')
    env=[]
    for a in [x,y]:
        v=signal.sosfilt(sos,a,axis=0); n=len(v)//441
        e=np.sqrt(np.mean(v[:n*441].reshape(n,441,2)**2,axis=(1,2)))
        env.append(e)
    for t in [10,40,70,100,130]:
        a,b=[e[t*100:(t+10)*100] for e in env]
        a=a-a.mean(); b=b-b.mean(); c=signal.correlate(b,a)/np.sqrt(np.dot(a,a)*np.dot(b,b))
        l=signal.correlation_lags(len(b),len(a)); mask=abs(l)<=10; c=c[mask]; l=l[mask]; k=np.argmax(c)
        extra['envelope_alignment'].append(dict(band=[lo,hi],time=t,lag_ms=int(l[k]*10),correlation=float(c[k]),zero_lag_correlation=float(c[l==0][0])))
# Level-matched A/B at RMS -24 dBFS; diagnostic copies only.
for name,a in [('Original',x),('Reference',y),('Output',z)]:
    gain=10**(-24/20)/np.sqrt(np.mean(a*a))
    peak=abs(a*gain).max()
    # Shared target is already safe for these inputs.
    assert peak<1
    sf.write(out/(name+'-matched.wav'),a*gain,sr,subtype='PCM_24')
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-y','-i',str(out/(name+'-matched.wav')),'-map_metadata','-1','-c:a','libvorbis','-q:a','6',str(out/(name+'-matched.ogg'))],check=True)
(out/'diagnostics.json').write_text(json.dumps(extra,indent=2))
print(json.dumps(extra,indent=2))
