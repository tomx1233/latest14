"""Validate local fingerprints with controls and current MP3 versus Ogg delivery.

No profile fitting, recognition requests, or change to the bot's export default.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import hashlib
import numpy as np
import soundfile as sf
from reference_v5.engine import process
from reference_v5.fingerprint import fingerprint,compare,file_print

OUT=Path('reports/copyfinger_newsong2')


def main():
    import killa_tools as kt
    paths=['TestSong.ogg','newsong2.mp3']
    prints={path:file_print(path) for path in paths}
    rows=[]
    for source in paths:
        before=hashlib.sha256(Path(source).read_bytes()).hexdigest()
        a,sr=sf.read(source,always_2d=True)
        stem=Path(source).stem
        baseline=prints[source]
        z=process(a,sr)
        dest=OUT/(stem+'_CopyFinger.ogg')
        with tempfile.TemporaryDirectory(prefix='localprint_') as tmp:
            wav=Path(tmp)/'processed.wav'
            sf.write(wav,z,sr,subtype='FLOAT')
            subprocess.run(kt._FFMPEG+['-i',str(wav),'-af','volume=-1.5dB']+kt._CLEAN_META_FLAGS+['-c:a','libvorbis','-q:a','8',str(dest)],check=True)
            control=Path(tmp)/'original_reencode.ogg'
            subprocess.run(kt._FFMPEG+['-i',source]+kt._CLEAN_META_FLAGS+['-c:a','libvorbis','-q:a','8',str(control)],check=True)
            ogg_audio,ogg_sr=sf.read(dest,always_2d=True)
            assert ogg_sr==sr and len(ogg_audio)==len(a)
            cases={
                'self_control':compare(baseline,baseline),
                'gain_minus20db_control':compare(baseline,fingerprint(a*.1,sr)),
                'ogg_reencode_only_control':compare(baseline,file_print(control)),
                'other_song_negative_control':compare(baseline,prints[paths[1] if source==paths[0] else paths[0]]),
                'copyfinger_preencode':compare(baseline,fingerprint(z,sr)),
                'copyfinger_mp3_current':compare(baseline,file_print(OUT/(stem+'_CopyFinger.mp3'))),
                'copyfinger_ogg_q8':compare(baseline,fingerprint(ogg_audio,ogg_sr)),
            }
        assert before==hashlib.sha256(Path(source).read_bytes()).hexdigest()
        rows.append(dict(source=source,source_unchanged=True,source_sha256=before,
            ogg_delivery=str(dest),ogg_sample_rate=ogg_sr,ogg_samples=len(ogg_audio),
            ogg_decoded_sample_peak=float(np.max(np.abs(ogg_audio))),comparisons=cases))
        print(source,flush=True)
        for name,c in cases.items(): print(name,c['whole_overlap'],flush=True)
    result=dict(method='CopyFinger LocalPrint v1',recognition_status='NOT TESTED: no third-party identification available',
                decision_threshold=None,notes='Scores are diagnostics, not recognition probabilities. Ogg and MP3 get the same DSP and -1.5 dB delivery gain.',tracks=rows)
    (OUT/'localprint-results.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    main()
