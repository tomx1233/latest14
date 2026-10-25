"""Offline 65% local-score experiment; not a conversion-time search."""
import json,hashlib
from pathlib import Path
import numpy as np
import soundfile as sf
from reference_v5.fingerprint import fingerprint,compare
from reference_v5.target65 import CANDIDATES65,process,SELECTED

OUT=Path('reports/copyfinger_target65')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    comparator=Path('reference_v5/fingerprint.py')
    before=hashlib.sha256(comparator.read_bytes()).hexdigest()
    x,sr=sf.read('newsong2.mp3',always_2d=True); a=fingerprint(x,sr)
    rows=[]
    for name,p in CANDIDATES65.items():
        z=process(x,sr,p); result=compare(a,fingerprint(z,sr))
        row=dict(name=name,settings=p,comparison=result)
        rows.append(row)
        print(name,result['whole_overlap'],flush=True)
    best=next(row for row in rows if row['name']==SELECTED)
    assert hashlib.sha256(comparator.read_bytes()).hexdigest()==before
    report=dict(selection_reason='Fixed seven-stage profile: less extreme than tested ten-stage/telephone alternatives; no runtime selection',target=.65,comparator_sha256=before,candidates=rows,selected=best['name'],
                target_met=best['comparison']['whole_overlap']['temporal_bit_agreement']<=.65,
                recognition='not tested; local similarity is not recognition probability')
    (OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__': main()
