"""Full-track sweep of the saturator drive, with the shipped filter path."""
import sys, os, json, subprocess, re
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import killa_tools as kt
FF = kt._FFMPEG_BIN
CH = json.load(open(os.path.join(kt._HERE, "analysis", "out", "v5_chain.json"))) \
    if hasattr(kt, "_HERE") else json.load(open("out/v5_chain.json"))
REF = dict(I=1.9, LRA=0.7, TP=4.2, crest=2.63, zcr=4752, lr=0.8629, rng=0.80)
REF_BL = np.array([-2.6,-2.5,-1.9,-2.1,-2.2,-1.8,-1.9,-1.9,-2.4,-2.2,-1.8,-2.0,-2.0,-1.9])

def stats(f):
    p = subprocess.run([FF,"-hide_banner","-nostats","-i",f,"-filter_complex",
                        "ebur128=peak=true","-f","null","-"],capture_output=True,text=True).stderr
    I=float(re.findall(r"I:\s+(-?[\d.]+) LUFS",p)[-1]); L=float(re.findall(r"LRA:\s+(-?[\d.]+) LU",p)[-1])
    P=float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS",p)[-1])
    x=kt._v5_pcm(f); m=kt._v5_octave_curve(x)
    h=44100*10; k=len(x)//h; b=x.mean(1)[:k*h].reshape(k,h)
    bl=20*np.log10(np.maximum(np.sqrt((b**2).mean(1)),1e-9))
    return dict(I=round(I,1),LRA=round(L,1),TP=round(P,1),crest=m["crest_db"],
                zcr=m["zcr_per_sec"],lr=m["lr_corr"],rng=round(float(bl.max()-bl.min()),2),
                shape=round(float(np.sqrt(np.mean((bl-bl.mean()-(REF_BL-REF_BL.mean()))**2))),2))

def render(drive, out):
    c=dict(CH); c["drive_db"]=drive
    pre,sat=kt._v5_chain_filters(c)
    subprocess.run([FF,"-y","-hide_banner","-loglevel","error","-i","../TestSong.ogg",
                    "-af",f"{pre},{sat}","-c:a","pcm_f32le",out],check=True)
    return stats(out)

if __name__ == "__main__":
    print("ref ", REF)
    for d in [float(a) for a in sys.argv[1:]] or [CH["drive_db"]]:
        print(f"{d:5.1f}", render(d, "out/sweep.wav"))
