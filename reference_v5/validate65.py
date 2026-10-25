"""Real encoded-delivery tests for the fixed experimental profile; no retuning."""
import hashlib,json,gc,subprocess
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
from reference_v5.fingerprint import fingerprint,compare
from reference_v5.test_tracks import metrics
from reference_v5.target65 import SELECTED,CANDIDATES65

OUT=Path('reports/copyfinger_target65')


def main():
    import killa_tools as kt
    import reference_v5.target65 as mode
    OUT.mkdir(parents=True,exist_ok=True)
    comparator=Path('reference_v5/fingerprint.py')
    comparator_hash=hashlib.sha256(comparator.read_bytes()).hexdigest()
    rows=[]
    for path in ['newsong2.mp3','TestSong.ogg','newtestoriginal3.ogg']:
        source_hash=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        dest=OUT/(Path(path).stem+'_CopyFinger_Experimental.ogg')
        with patch.object(kt,'_probe_sweep',side_effect=AssertionError('Unexpected API call')),patch.object(kt,'_control_check',side_effect=AssertionError('Unexpected control')),patch.object(mode,'selected_process',wraps=mode.selected_process) as dsp:
            kt.copyfinger_experimental_process(path,str(dest),str(OUT/(Path(path).stem+'_spectrum.png')),print)
            assert dsp.call_count==1
        del dsp
        gc.collect()
        x,sr=sf.read(path,always_2d=True); y,ysr=sf.read(dest,always_2d=True)
        assert sr==ysr and x.shape==y.shape
        c=compare(fingerprint(x,sr),fingerprint(y,ysr))
        # Report successes AND failures; never imply a cap across songs/windows.
        score=c['whole_overlap']['temporal_bit_agreement']
        measured=[w['temporal_bit_agreement'] for w in c['windows'] if w['temporal_bit_agreement'] is not None]
        rows.append(dict(source=path,source_sha256=source_hash,delivery=str(dest),
            target_met=score is not None and score<=.65,comparison=c,metrics=metrics(y,sr),
            worst_window_agreement=max(measured) if measured else None))
        print(path,score,'WORST WINDOW',max(measured),flush=True)
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==source_hash
        # Stream preview encoding to avoid extra full-song array allocations.
        gain=10**(-24/20)/np.sqrt(np.mean(y*y))
        del x,y
        gc.collect()
        subprocess.run(kt._FFMPEG+['-i',str(dest),'-af',f'volume={gain}',
            '-map_metadata','-1','-c:a','libvorbis','-q:a','6',
            str(OUT/(Path(path).stem+'_matched.ogg'))],check=True)
    assert hashlib.sha256(comparator.read_bytes()).hexdigest()==comparator_hash
    result=dict(selected=SELECTED,settings=CANDIDATES65[SELECTED],target=.65,
                comparator_sha256=comparator_hash,tracks=rows,
                live_recognition='NOT TESTED; no probability/cap can be inferred',pitch_shift=0,tempo_factor=1,speed_factor=1)
    (OUT/'delivery-results.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__': main()
