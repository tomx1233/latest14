"""Does Bass and Treble around a clipper create the reference's mid-band hash?"""
import os, sys, subprocess
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import killa_tools as kt
import basstreble as BT

FF = kt._FFMPEG_BIN
SR = 44100
PRE = "results/bt_pre.wav"

BANDS = [(20,60),(60,120),(120,240),(240,480),(480,960),(960,1920),
         (1920,3840),(3840,7680),(7680,15360)]
FLAT = [(200,500),(500,1000),(1000,2000),(2000,4000),(4000,8000),(8000,12000)]

def build_pre():
    chain = dict(kt.autofit_v5_profile()["chain"])
    # everything up to (not including) the saturator
    pre = kt._v5_pre_filter(chain)
    subprocess.run([FF,"-y","-hide_banner","-loglevel","error","-i","../TestSong.ogg",
                    "-af",pre,"-c:a","pcm_f32le",PRE], check=True)

def curve(x):
    m=x.mean(1); n=8192; w=np.hanning(n); acc=np.zeros(n//2+1); c=0
    for i in range(0,len(m)-n,n//2):
        acc+=np.abs(np.fft.rfft(m[i:i+n]*w))**2; c+=1
    f=np.fft.rfftfreq(n,1/SR)
    lv=np.array([10*np.log10(max(acc[(f>=a)&(f<b)].sum()/c,1e-20)) for a,b in BANDS])
    mid=np.median(lv[2:6])
    return lv-mid

def flatness(x):
    m=x.mean(1); n=4096; w=np.hanning(n); acc=np.zeros(n//2+1); c=0
    for i in range(0,len(m)-n,n//2):
        acc+=np.abs(np.fft.rfft(m[i:i+n]*w))**2; c+=1
    acc/=c; f=np.fft.rfftfreq(n,1/SR)
    out=[]
    for a,b in FLAT:
        seg=acc[(f>=a)&(f<b)]
        out.append(np.exp(np.mean(np.log(seg+1e-30)))/seg.mean())
    return np.array(out)

def crest(x):
    return 20*np.log10(np.abs(x).max()/np.sqrt((x**2).mean()))

def run(x, t1, drive, t2, clip=True):
    y = BT.apply(x, treble_db=t1)
    k = 10**(drive/20)
    y = np.arctan(y*k)*(2/np.pi)
    y = BT.apply(y, treble_db=t2)
    if clip:
        y = np.clip(y, -1, 1)
    return y

REF_CURVE = curve(kt._v5_pcm("../NewTest.ogg"))
REF_FLAT = flatness(kt._v5_pcm("../NewTest.ogg"))
REF_CREST = crest(kt._v5_pcm("../NewTest.ogg"))
print("ref curve", np.round(REF_CURVE,1))
print("ref flat ", np.round(REF_FLAT,3), " crest", round(REF_CREST,2))

if __name__ == "__main__":
    if not os.path.exists(PRE):
        build_pre()
    x = kt._v5_pcm(PRE)
    print(f"\n{'t1':>5} {'drive':>6} {'t2':>5} {'crest':>6} {'band':>6} {'flat_mid':>9} {'flat_hi':>8}")
    for t1 in (6, 12, 18, 24):
        for t2 in (-6, -12, -18):
            y = run(x, t1, 40.0, t2)
            c = curve(y); fl = flatness(y)
            band = float(np.sqrt(np.mean((c-REF_CURVE)**2)))
            print(f"{t1:5.0f} {40.0:6.1f} {t2:5.0f} {crest(y):6.2f} {band:6.2f} "
                  f"{fl[2:5].mean():9.4f} {fl[4:].mean():8.4f}")
