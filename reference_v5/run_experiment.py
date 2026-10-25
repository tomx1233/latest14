"""Offline candidate evaluation. Does not modify the bot, original or comparator."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import numpy as np
import soundfile as sf
from reference_v5.fingerprint import fingerprint,compare,file_print
from reference_v5.experiment import CANDIDATES,process
from reference_v5.test_tracks import metrics

OUT=Path('reports/copyfinger_experimental')


def main():
    import killa_tools as kt
    OUT.mkdir(parents=True,exist_ok=True)
    source=Path('newsong2.mp3')
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    comparator=Path('reference_v5/fingerprint.py')
    comparator_hash=hashlib.sha256(comparator.read_bytes()).hexdigest()
    x,sr=sf.read(source,always_2d=True)
    original=fingerprint(x,sr)
    baseline=compare(original,file_print('reports/copyfinger_newsong2/newsong2_CopyFinger.ogg'))
    rows=[]
    for name,p in CANDIDATES.items():
        z=process(x,sr,p)
        result=compare(original,fingerprint(z,sr))
        row=dict(name=name,parameters=p,preencode=result,metrics=metrics(z,sr))
        rows.append(row)
        print(name,result['whole_overlap'],flush=True)
    # Selection explicitly optimizes ONLY this local metric; not recognition proof.
    best=min(rows,key=lambda r:r['preencode']['whole_overlap']['temporal_bit_agreement'])
    z=process(x,sr,best['parameters'])
    export=OUT/'newsong2_CopyFinger-experimental.ogg'
    with tempfile.TemporaryDirectory() as tmp:
        wav=Path(tmp)/'processed.wav'
        sf.write(wav,z,sr,subtype='FLOAT')
        subprocess.run(kt._FFMPEG+['-i',str(wav),'-af','volume=-6dB']+kt._CLEAN_META_FLAGS+['-c:a','libvorbis','-q:a','8',str(export)],check=True)
        # Listening only; same RMS target as previous matched copies.
        sf.write(wav,z*10**(-24/20)/np.sqrt(np.mean(z*z)),sr,subtype='PCM_24')
        subprocess.run(kt._FFMPEG+['-i',str(wav)]+kt._CLEAN_META_FLAGS+['-c:a','libvorbis','-q:a','6',str(OUT/'newsong2_experimental_matched.ogg')],check=True)
    d,dsr=sf.read(export,always_2d=True)
    assert dsr==sr and len(d)==len(x)
    after=compare(original,fingerprint(d,dsr))
    # Holdout: apply selected settings to the earlier song, no retuning.
    a,asr=sf.read('TestSong.ogg',always_2d=True)
    b=process(a,asr,best['parameters'])
    holdout=compare(fingerprint(a,asr),fingerprint(b,asr))
    assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
    assert hashlib.sha256(comparator.read_bytes()).hexdigest()==comparator_hash
    report=dict(source_sha256=source_hash,comparator_sha256=comparator_hash,
        baseline=baseline,candidates=rows,selected=best['name'],delivery=after,
        delivery_metrics=metrics(d,dsr),holdout_TestSong=holdout,holdout_metrics=metrics(b,asr),
        recognition='NOT TESTED; local metric was used for candidate selection, not independent recognition validation',
        pitch_semitones=0,tempo_factor=1,speed_factor=1)
    (OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('SELECTED',best['name'],'DELIVERY',after['whole_overlap'],'HOLDOUT',holdout['whole_overlap'])

if __name__=='__main__': main()
