# CopyFinger Experimental (65 target)

## Added to the bot

New `/copyr8` preset: **CopyFinger Experimental (65 target)** (`copyfinger-exp65`). It is a separate fixed one-pass conversion. Existing CopyFinger and V4 sound processing remain unchanged. The common adapter now accepts an explicitly selected DSP callback and export options; defaults retain the existing CopyFinger path.

**65% is an experimental local fingerprint-agreement goal, not a maximum, probability of recognition, service result, or safety guarantee.** No runtime analysis, search, incremental testing, API call, fallback shift or score threshold is part of conversion. The supplied audio is processed once through a fixed graph and exported as `<source>_CopyFinger_Experimental.ogg`. A chain containing repeated effects is not a runtime search.

## Actual whole-song encoded delivery results

| Source | Local temporal agreement | Goal ≤65%? | Highest measured 12-second window |
|---|---:|---|---:|
| newsong2.mp3 | **64.53%** | Yes, whole-song only | **68.93%** |
| TestSong.ogg | **65.30%** | No | **68.47%** |
| newtestoriginal3.ogg | **66.98%** | No | **70.68%** |

The existing CopyFinger Ogg scored 87.63% on newsong2; the preceding multiband experiment scored 78.85%. This version is lower on the unchanged comparator, but it does **not** meet the goal across all songs or all windows. This failure is explicitly retained in `delivery-results.json`; there is no enforcement claim.

The same settings were chosen on newsong2 and applied without retuning to the other two originals. Because newsong2 was used to choose settings, its target success is not independent validation. Live Shazam/AcoustID/service recognition remains unavailable and was not tested. The comparator has limited calibration; lower agreement is not necessarily less external recognizability.

## Unchanged scoring and candidate selection

`reference_v5/fingerprint.py` was unchanged. Its SHA-256 is recorded in the offline candidate and delivery reports. Whole-song comparisons retain all overlapping windows and use the same silence/confidence rules. LocalPrint's confident-bit masks still depend on both inputs, so changing processing can change which bits are compared. Results remain conditional agreement, not an all-bits difference score.

Eight bounded manually authored candidates were tested offline:

| Candidate | Whole-song pre-encode agreement on newsong2 |
|---|---:|
| Dense amplitude quantization | 77.62% |
| Midrange | 75.60% |
| Telephone | 73.83% |
| Stacked midrange, 3 stages | 70.18% |
| Stacked midrange, 6 stages | 65.38% |
| **Stacked midrange, 7 stages** | **64.46%** |
| Stacked midrange, 10 stages | 62.57% |
| Stacked telephone, 6 stages | 62.16% |

The fixed seven-stage midrange setting was selected as the first midrange stage count tested that reached the goal, rather than selecting the most destructive/lowest-scoring alternative. Final Ogg encoding changes agreement slightly to 64.53%. No comparator formula, scoring cutoff or pitch/time clock was adjusted.

## Exact fixed graph

`reference_v5/target65.py`, `SELECTED = 'stacked-seven'`:

1. Apply the existing separate multiband-extreme experimental graph: causal splits at 180/1,600 Hz, linked per-band 3-ms power detectors, unit-strength normalization with .015 floor, tanh drive 15, low/mid/high weights .45/.8/1, 100-Hz highpass and final tanh drive 1.5. This is **not** the normal CopyFinger graph.
2. Seven fixed serial stages, each containing:
   - Causal second-order-prototype Butterworth **250–4,500 Hz bandpass** (four poles total).
   - `tanh(4 * audio)` saturation.
   - Symmetric amplitude quantization `round(7 * audio) / 7`.
3. Scale by .5.
4. Export Ogg Vorbis quality 8 with **−6 dB additional fixed attenuation**. FFmpeg applies no duplicate EQ/dynamics.

Amplitude quantization adds deterministic distortion; it does not reduce sample rate or change the sample clock. There is no injected noise, oscillator, modulation, pitch/tempo/speed effect, silence insertion, time warping, musical cropping/padding, or track rearrangement.

**This is intentionally severe sound processing, not a recreation of either supplied modified reference.** Narrower bandwidth, flattened dynamics, reduced stereo correlation, strong harmonics and quantization artifacts are expected. On test tones, an upper harmonic can become stronger than the original fundamental. Tests establish that the original fundamental frequency component is retained without detuning; they do **not** establish unchanged timbre or perceived pitch. No subjective listening assessment was available here. Do not interpret “0.00 st processing” as a promise that this heavily distorted result sounds unchanged in key/timbre.

## Timing and level discipline

Real adapter tests confirm one DSP invocation and no API/control calls. All three output files retain source sample rate and exact decoded sample count:

- newsong2: 48,000 Hz / 11,545,705 samples per channel.
- TestSong: 44,100 Hz / 6,585,656 samples per channel.
- Original3: 44,100 Hz / 9,474,555 samples per channel.

There is no deliberate sample delay or time remapping. Serial causal filters do introduce phase/group delay and alter transients. At 48 kHz, the seven added bandpasses alone have approximately 7.02 ms group delay at 250 Hz, 2.95 ms at 440 Hz, .78 ms at 1 kHz and .46 ms at 4 kHz. These are frequency-dependent linear-filter estimates, not total graph latency. Detector dynamics and the original multiband graph also affect the waveform. No compensation is used. Some reduction in a zero-lag local fingerprint score may reflect filter/transient effects that robust external recognizers tolerate; it is not evidence that musical identity was removed.

Encoded peak samples are .3832, .3747 and .3661 for the three songs. Their RMS is approximately −12.60/−12.52/−12.49 dBFS. This lower delivery level is fixed headroom, not source-loudness matching or a fingerprint trick; LocalPrint was tested to be gain-invariant. The experiment's dynamics are much flatter than either reference in places (50-ms p95–p5 spread .47/.29/.25 dB). These peak figures are decoded sample peaks, not true-peak guarantees.

## Files and tests

- `newsong2_CopyFinger_Experimental.ogg`, `TestSong_CopyFinger_Experimental.ogg`, `newtestoriginal3_CopyFinger_Experimental.ogg`: actual fixed-preset full-length exports.
- Corresponding `<source>_matched.ogg`: quieter −24 dBFS RMS listening copies.
- `results.json`: all offline candidates and selected settings.
- `delivery-results.json`: encoded whole-song/window scores, successful and failed target checks, source/comparator hashes and metrics.
- Per-song delivery spectrograms are diagnostic illustrations, not a same-scale reference comparison.

Generated audio is ignored by Git. Source hashes were checked unchanged. Existing CopyFinger profile, V4 macros and LocalPrint were not altered by selection.

**139 tests passed, plus 28 subtests** across the selected regression suite. Added tests cover input immutability, exact sample count, silence, finite output, retained fundamental component at 44.1/48 kHz, rejection of non-normal pitch/tempo/speed arguments, one adapter invocation, zero recognition calls, explicit Ogg encoding, fixed attenuation and correct separate menu routing.

Reproduce offline:

```sh
python -m reference_v5.try65
python -m reference_v5.validate65
```

`try65` evaluates manually authored candidates but does not change the deployed selection. `validate65` applies the fixed preset to all three originals without retuning. Restart/sync the existing bot normally to expose the new preset. **No automatic cap, recognition guarantee or runtime search was added.**
