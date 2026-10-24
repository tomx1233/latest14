"""Bot adapter: same recognition pacing, no search or recognition fallback DSP."""
import os
import tempfile
import soundfile as sf
from reference_v5.engine import process


def run(input_path, output_path, spectrogram_path, progress=None, *, recognize=True):
    import killa_tools as kt
    def log(s):
        if progress:
            progress(s)
    def command(args):
        rc, _, err = kt._run(kt._FFMPEG + args)
        if rc:
            raise RuntimeError('V5 render failed: ' + err[-500:])
    with tempfile.TemporaryDirectory(prefix='reference_v5_') as tmp:
        decoded = os.path.join(tmp, 'input.wav')
        rendered = os.path.join(tmp, 'processed.wav')
        log('CopyFinger: single-pass reference processing at 0.00 st / tempo 1.00x / speed 1.00x')
        command(['-i', input_path, '-map_metadata', '-1', '-c:a', 'pcm_f32le', decoded])
        x, sr = sf.read(decoded, always_2d=True)
        if x.shape[1] != 2:
            raise RuntimeError('V5 reference profile requires stereo input; no automatic downmix.')
        sf.write(rendered, process(x, sr), sr, subtype='FLOAT')
        # Preserve reference-level validation WAV; never match source loudness.
        # Lossy delivery gets fixed peak headroom, not an adaptive loudness target.
        is_wav = os.path.splitext(output_path)[1].lower() == '.wav'
        command(['-i', rendered, '-map_metadata', '-1'] +
                (['-c:a', 'pcm_f32le'] if is_wav else ['-af', 'volume=-1.5dB']) + [output_path])
        clean, counts, verified = False, None, None
        if recognize:
            log('API pacing (API Cooldown) -- checking fixed-speed output; no shift fallback')
            clean, counts = kt._probe_sweep(output_path, kt._gapfree_windows(output_path), progress=progress)
            verified = kt._control_check(input_path, progress=progress)
            if not clean or verified is not True:
                log('Recognition not verified. Processing remains 0.00 st / 1.00x; no fallback applied.')
        command(['-i', output_path, '-lavfi',
                 'showspectrumpic=s=1100x280:legend=0:gain=.5:color=plasma', spectrogram_path])
        kt._brand_spectrogram(spectrogram_path)
        return dict(pitch=0.,tempo=1.,speed=1.,clean=clean,counts=counts,
                    verified=verified,cost=None,tremolo_applied=False,
                    info=kt._result_info(output_path, progress=progress),
                    reference_profile=True,delivery_gain_db=0 if is_wav else -1.5)
