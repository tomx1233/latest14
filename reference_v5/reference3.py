"""Evidence-specific Reference 3 profile; never selected by the bot implicitly."""
import json
from pathlib import Path
import numpy as np
from reference_v5.engine import process as base_process

PROFILE=Path(__file__).parent.parent/'macros'/'CopyFinger Reference3 Experimental.json'


def process(x,sr,profile=None):
    p=profile or json.loads(PROFILE.read_text())
    if p.get('stereo_mode') not in ('linked_stereo','mono_mean'):
        raise ValueError('Unknown explicit stereo policy')
    if x.ndim!=2 or x.shape[1]!=2:
        raise ValueError('Stereo source required; no channel inference')
    # Downmix is supported by this reference only, not a change to V5/default.
    source=np.repeat(x.mean(axis=1,keepdims=True),2,axis=1) if p['stereo_mode']=='mono_mean' else x
    return base_process(source,sr,p)
