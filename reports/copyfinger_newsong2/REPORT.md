# CopyFinger: whole-song test on newsong2.mp3

## Bottom line

The preset runs successfully on the new track and substantially changes its tone/dynamics. **It is not validated as recognition-resistant.** The user reports that this track was identified after conversion; that result is not contradicted by any local test. Strong clipping/compression does not guarantee destruction of identifying musical features.

Live recognition could **not** be completed here. Network access is limited to GitHub/package registries, excluding Shazam/AcoustID endpoints. This workspace also has no configured AcoustID key or private `.env`. These are unavailable checks, not zero-match results. No subjective listening test was performed. No claim of a changed/defeated fingerprint is made from waveform correlation or spectra. The earlier original-song no-match was also user-reported, not independently reverified here.

**No DSP profile or conversion behavior was changed in this testing pass.** Changing it blindly would not demonstrate improved recognition results and could damage the successful original fit. New work adds repeatable whole-song testing and an optional host-side recognition checker. CopyFinger still processes once, with no recognition/search inside conversion; V4 remains unchanged.

## What was actually exercised

Executed `killa_tools.copyfinger_process` on both complete original files, through real FFmpeg decode, real SciPy DSP, real MP3 encode and spectrogram generation. Not an excerpt-only simulation. Instrumentation verified one DSP invocation and made accidental recognition/control/shift calls fail the test. Both supplied originals' SHA-256 hashes were unchanged after processing.

Additionally processed continuous whole tracks into float validation signals for pre-encode measurements, compared source/output in overlapping 12-second diagnostic windows at 6-second hops, generated consistently scaled spectrograms, and produced −24 dBFS RMS matched listening copies. Window acoustic statistics are **not** API recognition tests. The whole-song raw metrics, per-window values, hashes and codec measurements are saved in JSON.

| Whole-song measure | TestSong original | TestSong CopyFinger DSP | newsong2 original | newsong2 CopyFinger DSP |
|---|---:|---:|---:|---:|
| Sample rate | 44,100 Hz | 44,100 Hz | 48,000 Hz | 48,000 Hz |
| Samples/channel | 6,585,656 | 6,585,656 | 11,545,705 | 11,545,705 |
| Decoded duration | 149.334603 s | 149.334603 s | 240.535521 s | 240.535521 s |
| RMS dBFS | −10.211 | −1.981 | −13.096 | −2.198 |
| Sample peak | 2.92156 | 1.07394 | .84941 | 1.07394 |
| Crest, dB | 19.523 | 2.600 | 11.678 | 2.817 |
| 50-ms envelope p95–p5, dB | 20.681 | 1.845 | 24.565 | 2.190 |
| L/R correlation | .96762 | .78178 | .92397 | .75465 |
| PSD centroid | 446 Hz | 2,281 Hz | 212 Hz | 1,975 Hz |
| 95% PSD roll-off | 1,970 Hz | 8,882 Hz | 668 Hz | 8,121 Hz |

The two input tracks have different tonal balance and dynamics. A fixed EQ/distortion transfer function is not a guarantee of equivalent fingerprint outcomes on different material. Output on newsong2 has a similar broad measured character to the fitted original, but that is not proof of recognition resistance or audible reference identity.

### Timing constraints

DSP sample count, sample rate and channel count are preserved for both tracks. Decoded MP3 delivery also has exactly the source's decoded sample count on both files, with gapless-aware decoding. Container/probe durations include codec framing (149.37/240.58 seconds) and must not be mistaken for tempo changes. No padding/cropping/time remapping is used to align music. Causal EQ filter phase still exists as documented previously. Tests cover fixed 440-Hz input at both 44.1 and 48 kHz across all candidate nonlinearities/compression strengths. Saturation adds harmonics, not pitch shifting.

### Export issue found

The current MP3 path uses FFmpeg's default **128 kbps** and fixed −1.5 dB pre-encode attenuation. That attenuation does **not** guarantee decoded peak headroom for this heavily distorted signal. Whole-song delivery results:

| Encoding at same pre-encode gain | TestSong decoded sample peak | newsong2 decoded sample peak |
|---|---:|---:|
| Current 128 kbps | 2.15190 | 2.09974 |
| Controlled 192 kbps export | 1.81015 | 1.62722 |
| Controlled 320 kbps export | 1.47420 | 1.51073 |

These are decoded **sample** peaks, not the percentage of clipped samples and not true-peak figures. They may clip in playback chains restricted to ±1. Changing bitrate alone does not resolve headroom, nor is it a validated recognition fix. The fixed-gain delivery claim must not be read as a peak guarantee. Codec comparisons changed no EQ/dynamics/pitch/tempo parameters. The implementation was left unchanged so this report describes the actual shipped preset rather than a silently substituted version.

## Deliverables

- `newsong2_CopyFinger.mp3`: actual current-preset export, full length. **Very loud; turn down playback first.** Contains decoded overshoots noted above.
- `newsong2_original_matched.ogg` / `newsong2_CopyFinger_matched.ogg`: safer level-matched listening copies at −24 dBFS RMS before encoding. These are not validation-level exports.
- Equivalent TestSong delivery and matched listening files.
- `spectrograms.png`: both full songs, before/after, identical FFT and −100…−20 dB/Hz PSD limits.
- `measurements.json` and `codec_tests.json`: exact measurements and reproducibility evidence.

Large float validation WAVs and trial-bitrate MP3s were removed after measurement to avoid retaining >140 MB of intermediate audio. The reproduction script regenerates them. Audio artifacts remain Git-ignored.

## Tests and remaining live validation

**104 tests passed, plus 28 subtests**, across `test_reference_v5.py`, `test_v4_tempo.py`, `test_v4_audio.py`, `test_gating.py`, `test_bot_delivery.py`, `test_updates.py`. New checks include both sample rates and tri-state recognition reporting. These tests are not live identification evidence.

Reproduce local conversion/measurements:

```sh
python -m reference_v5.test_tracks
```

To test actual recognition, on the normal bot machine with its installed recognition dependencies, private local configuration and working network:

```sh
python -m reference_v5.check_delivery newsong2.mp3 reports/copyfinger_newsong2/newsong2_CopyFinger.mp3 --output newsong2-recognition.json
python -m reference_v5.check_delivery TestSong.ogg reports/copyfinger_newsong2/TestSong_CopyFinger.mp3 --output TestSong-recognition.json
```

This **separate diagnostic command** never reprocesses audio or adjusts parameters. It reuses original-file controls, whole-song overlapping recognition windows, provider availability and actual **API pacing (API Cooldown)** from the existing bot. As in the existing sweep, it stops at the first match/inconclusive response because either defeats a verified clean sweep. Exit 0 = corroborated no-match; exit 1 = recognized; exit 2 = unverified/inconclusive. Files are hashed to confirm they were not modified. Check the service that produced the user's result too: another service/moderation database is not ruled out by a Shazam no-match. Do not share private keys or `.env`; the resulting JSON contains no credentials.

Until live checks of the converted files and original controls are available, recognition remains **unverified here / reported recognized for newsong2**. No claim that recognition has been fixed is justified.
