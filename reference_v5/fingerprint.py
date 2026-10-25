"""CopyFinger LocalPrint v1: offline, fixed-timeline fingerprint diagnostics.

Not Shazam/Chromaprint; no identification database, calibrated match threshold,
probability of recognition, pitch search, or time warping. Input files are read
only. Analysis downsampling preserves seconds and never changes exported audio.

python -m reference_v5.fingerprint original.mp3 converted.ogg --output pair.json
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy import signal
import soundfile as sf

ANALYSIS_RATE = 11025
HOP = 512
VERSION = 'CopyFinger LocalPrint v1'


@dataclass
class Print:
    bits: np.ndarray
    reliable: np.ndarray
    active: np.ndarray
    chroma: np.ndarray
    digest: str
    duration: float


def fingerprint(audio, sr):
    a = np.asarray(audio, dtype=np.float64)
    if a.ndim == 2:
        a = a.mean(axis=1)  # analysis only; never a conversion downmix
    if a.ndim != 1 or not np.isfinite(a).all() or sr <= 0:
        raise ValueError('Expected finite mono/stereo audio and positive sample rate')
    if len(a)/sr < 2:
        raise ValueError('Need at least two seconds of audio')
    duration = len(a)/sr
    divisor = math.gcd(int(sr), ANALYSIS_RATE)
    if sr != ANALYSIS_RATE:
        a = signal.resample_poly(a, ANALYSIS_RATE//divisor, int(sr)//divisor)
    f,t,p = signal.spectrogram(a, ANALYSIS_RATE, nperseg=2048,
                               noverlap=2048-HOP, mode='psd')
    # 24 geometric bands. Adjacent-band log contrasts suppress static EQ;
    # temporal differences suppress overall gain and retain rhythmic movement.
    edges = np.geomspace(80, 5000, 25)
    bands = np.stack([np.sum(p[(f >= lo)&(f < hi)],axis=0)
                      for lo,hi in zip(edges,edges[1:])],axis=1)
    bands /= max(float(np.max(bands)), 1e-30)
    logs = np.log10(np.maximum(bands, 1e-12))
    delta = np.diff(np.diff(logs,axis=1),axis=0)
    bits = delta > 0
    reliable = abs(delta) > .02  # exclude numerically ambiguous near-zero signs
    energy = np.sum(p,axis=0)
    active = energy > max(float(np.max(energy))*1e-6,1e-25)
    active = active[:-1]&active[1:]
    # Fixed-key (no chroma rotation) pitch-class energy descriptor.
    select = (f >= 80)&(f <= 5000)
    notes = np.rint(69+12*np.log2(f[select]/440)).astype(int)%12
    chroma = np.stack([np.sum(p[select][notes==k],axis=0) for k in range(12)],axis=1)
    chroma = np.sqrt(chroma[1:])
    chroma /= np.maximum(np.linalg.norm(chroma,axis=1,keepdims=True),1e-30)
    payload = np.packbits(np.column_stack([bits,active])).tobytes()
    digest = hashlib.sha256(VERSION.encode()+payload).hexdigest()
    return Print(bits,reliable,active,chroma,digest,duration)


def _scores(a,b,lo,hi):
    active = a.active[lo:hi]&b.active[lo:hi]
    mask = a.reliable[lo:hi]&b.reliable[lo:hi]&active[:,None]
    count = int(np.sum(mask))
    agreement = float(np.mean((a.bits[lo:hi]==b.bits[lo:hi])[mask])) if count else None
    cosine = np.sum(a.chroma[lo:hi]*b.chroma[lo:hi],axis=1)
    # Avoid treating short or silent windows as recognition evidence.
    sufficient = int(np.sum(active)) >= 20 and count >= 100
    return dict(status='measured' if sufficient else 'inconclusive_low_information',
                comparable_frames=int(np.sum(active)),compared_bits=count,
                temporal_bit_agreement=agreement if sufficient else None,
                fixed_key_chroma_cosine=float(np.mean(cosine[active])) if sufficient else None)


def compare(a,b):
    n = min(len(a.active),len(b.active))
    result = dict(method=VERSION,alignment='zero lag; no search, pitch rotation or time warp',
        fingerprint_sha256_equal=a.digest==b.digest,
        original_fingerprint_sha256=a.digest,converted_fingerprint_sha256=b.digest,
        duration_difference_seconds=b.duration-a.duration,
        original_frames=len(a.active),converted_frames=len(b.active),
        frame_step_seconds=HOP/ANALYSIS_RATE,
        shared_timeline_seconds=n*HOP/ANALYSIS_RATE,
        whole_overlap=_scores(a,b,0,n),windows=[],
        recognition_verdict='not_available: local diagnostics are not an API match test')
    win=round(12*ANALYSIS_RATE/HOP); step=round(6*ANALYSIS_RATE/HOP)
    starts=sorted(set(list(range(0,max(n-win,0),step))+[max(n-win,0)]))
    for lo in starts:
        hi=min(n,lo+win)
        result['windows'].append(dict(start_seconds=lo*HOP/ANALYSIS_RATE,
                                      end_seconds=hi*HOP/ANALYSIS_RATE,
                                      **_scores(a,b,lo,hi)))
    return result


def file_print(path):
    a,sr=sf.read(path,always_2d=True)
    return fingerprint(a,sr)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original',type=Path)
    parser.add_argument('converted',type=Path)
    parser.add_argument('--output',type=Path,default=Path('localprint-comparison.json'))
    args=parser.parse_args()
    result=compare(file_print(args.original),file_print(args.converted))
    result['file_sha256_equal']=hashlib.sha256(args.original.read_bytes()).digest()==hashlib.sha256(args.converted.read_bytes()).digest()
    result['inputs']=[str(args.original),str(args.converted)]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='windows'},indent=2))

if __name__=='__main__':
    main()
