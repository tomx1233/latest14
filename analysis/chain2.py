"""Two-stage 'clip -> tone -> clip' model, fitted with Audacity's exact filters."""
import os, sys, subprocess, itertools, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import killa_tools as kt
import basstreble as BT

FF = kt._FFMPEG_BIN
SR = 44100
PRE2 = "results/bt_pre2.wav"      # leveler + high-pass only
T0, T1 = 20.0, 50.0
BANDS = [(20,60),(60,120),(120,240),(240,480),(480,960),(960,1920),
         (1920,3840),(3840,7680),(7680,15360)]
FLAT = [(200,500),(500,1000),(1000,2000),(2000,4000),(4000,8000),(8000,12000)]

def build_pre2():
    c = dict(kt.autofit_v5_profile()["chain"])
    c["pre_emphasis_db"] = 0.0          # tone handled by Bass and Treble below
    pre = kt._v5_pre_filter(c)
    subprocess.run([FF,"-y","-hide_banner","-loglevel","error","-i","../TestSong.ogg",
                    "-af",pre,"-c:a","pcm_f32le",PRE2], check=True)

def curve(x):
    m=x.mean(1); n=8192; w=np.hanning(n); acc=np.zeros(n//2+1); c=0
    for i in range(0,len(m)-n,n//2):
        acc+=np.abs(np.fft.rfft(m[i:i+n]*w))**2; c+=1
    f=np.fft.rfftfreq(n,1/SR)
    lv=np.array([10*np.log10(max(acc[(f>=a)&(f<b)].sum()/c,1e-20)) for a,b in BANDS])
    return lv-np.median(lv[2:6])

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

def atan_clip(y, drive_db):
    k = 10.0**(drive_db/20.0)
    return np.arctan(y*k)*(2/np.pi)

def chain(x, t1, d1, t2, d2):
    y = BT.apply(x, treble_db=t1) if t1 else x
    y = atan_clip(y, d1)
    y = BT.apply(y, treble_db=t2) if t2 else y
    if d2:
        y = y*(1.0/np.abs(y).max())
        y = atan_clip(y, d2)
    return y

def ref_stats():
    b = kt._v5_pcm("../NewTest.ogg")
    s, e = int(T0*SR), int(T1*SR)
    return dict(curve=curve(b[s:e]), flat=flatness(b[s:e]), crest=crest(b[s:e]),
                zcr=kt._v5_octave_curve(b[s:e])["zcr_per_sec"],
                lr=kt._v5_octave_curve(b[s:e])["lr_corr"])

if __name__ == "__main__":
    if not os.path.exists(PRE2):
        build_pre2()
    x = kt._v5_pcm(PRE2)[int(T0*SR):int(T1*SR)]
    R = ref_stats()
    print("ref  curve", np.round(R["curve"],1), "flat", np.round(R["flat"],3),
          "crest", round(R["crest"],2), "zcr", R["zcr"], "lr", round(R["lr"],3))
    print(f"{'t1':>4}{'d1':>5}{'t2':>5}{'d2':>5} {'crest':>6}{'band':>6}{'flat1-4':>8}{'flat4-8':>8}{'zcr':>6}{'lr':>6}")
    best=[]
    for t1 in (10,16,22):
        for d1 in (34,40,46):
            for t2 in (-6,-12,-18):
                for d2 in (0,20,30,40):
                    y = chain(x, t1, d1, t2, d2)
                    c=curve(y); fl=flatness(y); m=kt._v5_octave_curve(y)
                    band=float(np.sqrt(np.mean((c-R["curve"])**2)))
                    score = (band*2 + abs(m["crest_db"]-R["crest"])*2
                             + abs(fl[2:5].mean()-R["flat"][2:5].mean())*20
                             + abs(m["zcr_per_sec"]/R["zcr"]-1)*10
                             + abs(m["lr_corr"]-R["lr"])*40)
                    best.append((score,t1,d1,t2,d2,band,m["crest_db"],fl[2:5].mean(),fl[4],m["zcr_per_sec"],m["lr_corr"]))
    best.sort()
    for b in best[:10]:
        print(f"{b[1]:4.0f}{b[2]:5.0f}{b[3]:5.0f}{b[4]:5.0f} {b[6]:6.2f}{b[5]:6.2f}{b[7]:8.3f}{b[8]:8.3f}{b[9]:6d}{b[10]:6.3f}  score {b[0]:.2f}")
    json.dump([list(map(float,b)) for b in best[:40]], open("results/chain2_grid.json","w"), indent=1)
