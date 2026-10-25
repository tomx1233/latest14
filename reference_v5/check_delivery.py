"""Optional HOST-SIDE recognition check; never converts or changes the audio.

python -m reference_v5.check_delivery original.mp3 converted.mp3 --output result.json
Exit: 0 corroborated no-match, 1 recognized, 2 inconclusive/unverified.
Requires normal recognition dependencies and network access on the bot host.
"""
import argparse
import hashlib
import json
from pathlib import Path


def check(original, converted, kt, progress=print):
    windows = kt._gapfree_windows(converted)
    control = kt._control_check(original, progress=progress)
    clean, counts = kt._probe_sweep(converted, windows, progress=progress)
    # A failed request must not be interpreted as a confirmed no-match.
    identified = any(c is not None and c > 0 for c in counts or [])
    verified = clean and control is True
    status = 'recognized' if identified else 'verified_no_match' if verified else 'unverified'
    return dict(status=status,original_control=control,clean_sweep=clean,
                counts=counts,planned_window_starts=windows,
                providers=kt.active_recognition_providers(),
                note='Sweep may stop on the first match or inconclusive response; no processing is changed.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original',type=Path)
    parser.add_argument('converted',type=Path)
    parser.add_argument('--output',type=Path,default=Path('copyfinger-recognition.json'))
    args=parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv()
    import killa_tools as kt
    # Save evidence that the check did not modify either audio file.
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.original,args.converted)}
    try:
        result=check(str(args.original),str(args.converted),kt)
    except Exception as exc:
        # No raw API errors/credentials in reports. Failure is never a no-match.
        result=dict(status='unverified',reason='Recognition check failed; inspect local dependency/network setup.',error_type=type(exc).__name__)
    result['sha256']=hashes
    result['files_unchanged']=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'])
    return {'verified_no_match':0,'recognized':1,'unverified':2}[result['status']]

if __name__=='__main__':
    raise SystemExit(main())
