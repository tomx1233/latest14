# CopyFinger LocalPrint v1 — local fingerprint comparison

## Answer

Yes: a separate **offline fingerprint comparator** is now implemented and tested. It can demonstrate that a conversion changes this method's fingerprint while also showing how much identifying structure remains similar. It does **not** impersonate Shazam, AcoustID, or an upload platform's detector and cannot certify that they will fail to recognize a song.

The two measured songs retain considerable shared structure after CopyFinger. **There is no local evidence that switching to Ogg makes them harder to recognize.** Ogg preserves this particular temporal fingerprint slightly better than the current MP3 export. Format changes alone are not a dependable fingerprint-breaking mechanism.

## Results on actual complete files

Temporal agreement compares confident local fingerprint bits; chroma similarity compares pitch-class energy at the original key. Neither number is a recognition probability. No acceptance/rejection threshold is established.

| Comparison against original | TestSong temporal agreement | newsong2 temporal agreement |
|---|---:|---:|
| Identical audio | 100.000% | 100.000% |
| Gain-only −20 dB control | 100.000% | 100.000% |
| Ogg re-encode only, no CopyFinger | 99.918% | 99.884% |
| CopyFinger before codec | 87.978% | 87.665% |
| CopyFinger current MP3 | 87.570% | 87.383% |
| CopyFinger Ogg, Vorbis quality 8 | 87.984% | 87.630% |
| Other song, unrelated control at same nominal timeline | 49.555% | 49.555% |

For newsong2 the fixed-key chroma cosine is .96076 (MP3) / .96107 (Ogg), compared with .71643 for the unrelated track. For TestSong it is .95012 / .95054. A chroma descriptor can be similar between different songs sharing harmony; it is supporting context, not identification proof.

The exact LocalPrint fingerprint SHA-256 changes after processing **and after ordinary codec-only re-encoding**. That is why “the fingerprint hash changed” is not sufficient evidence that a robust recognizer has lost the song. A byte hash is also a different concept from a robust audio fingerprint; the pair CLI reports both separately.

The local method finds similar retention on both songs, so it does not explain why one was reportedly recognized by an external service while the other was not. Database coverage, passages tested, service algorithms, and the exact submitted export can all matter; these remain hypotheses without live results.

## How LocalPrint works

Implemented in `reference_v5/fingerprint.py`:

1. Read decoded audio without altering the file. Analyze mono channel average at 11,025 Hz using rational sample-rate conversion that preserves duration; this is **analysis only**, not a conversion/export stage.
2. Compute a 2,048-point PSD spectrogram with a 512-sample hop (approximately 46.44 ms).
3. Aggregate energy into 24 geometric bands from 80 to 5,000 Hz. Normalize and floor band power before taking logarithms.
4. Compute adjacent-band log contrast, then its change between neighboring frames. The sign forms 23 bits per frame. This suppresses overall gain and reduces sensitivity to static tonal balance while preserving temporal structure.
5. Exclude silence (below −60 dB relative frame power, plus an absolute floor). Compare only bits whose contrast-change magnitude is greater than .02 in **both** files. Reports include valid frame and compared-bit counts; conditional agreement is not an all-bits mismatch rate.
6. Separately compute normalized 12-bin pitch-class energy vectors, with no chroma rotation/pitch search.
7. Compare at **zero lag**, with full-overlap statistics and overlapping 12-second windows. No drift fitting, time warp, pitch shift, or hidden sample alignment occurs. Duration differences and unmatched tails are reported rather than silently erased. Shared structure is scored only over the overlapping timeline, not treated as an entire-file match.

Silent/low-information comparisons are inconclusive, not successful matches. Exact fingerprint digests are versioned. This is a pairwise known-original diagnostic, **not a general identification engine**: it does not search an unknown-song database or locate arbitrary excerpts within a track. No universal recognition threshold is claimed. Results depend on analysis definitions, and calibration here is limited to synthetic tests and these two supplied songs.

## Ogg experiment

`reference_v5/compare_codecs.py` generates Ogg using the exact unchanged CopyFinger graph and the same fixed −1.5 dB delivery attenuation as the current MP3. It does not change the bot's default export, perform a parameter search, or add recognition to conversion.

- `newsong2_CopyFinger.ogg`: stereo 48 kHz, exactly 11,545,705 decoded samples.
- `TestSong_CopyFinger.ogg`: stereo 44.1 kHz, exactly 6,585,656 decoded samples.
- Both originals' hashes verified unchanged.
- Ogg decoded sample peaks: approximately **1.0801** (newsong2) / **1.0810** (TestSong), versus 2.0997 / 2.1519 for current MP3. This is improved peak fidelity, **not** proof of recognition resistance. Ogg still exceeds unity; use reduced playback volume.
- Existing `*_CopyFinger_matched.ogg` files are safer listening copies at −24 dBFS RMS, not normal-level validation renders.

Full scores, windows, comparison coverage, durations, digests and controls are in `localprint-results.json`. Generated audio remains Git-ignored.

## Use

Compare any original and converted version locally:

```sh
python -m reference_v5.fingerprint newsong2.mp3 reports/copyfinger_newsong2/newsong2_CopyFinger.ogg --output localprint-pair.json
```

Reproduce both-song controls and MP3/Ogg comparison (requires the existing MP3 outputs; `python -m reference_v5.test_tracks` regenerates those):

```sh
python -m reference_v5.compare_codecs
```

These tools require no API keys and make no recognition network requests. They stay outside CopyFinger's one-pass preset. For actual service identification, use the separately documented `reference_v5.check_delivery` on the normal bot host; this local tool is not a substitute for that result.

## Validation

**109 tests passed, plus 28 subtests**, across the existing selected regression suite plus `test_localprint.py`. New tests cover identity, amplitude and polarity invariance, unrelated synthesized music, low-information silence, codec-only changes, analysis sample-rate conversion and duration mismatch reporting. Synthetic codec-control agreement is not assumed to equal real music performance. No DSP parameters, existing macro, or V4 behavior changed in this addition. No subjective listening or live service test was performed here.
