# Auto-Fit V5 (AfterEffects)

## Requested bot changes

- **CopyFinger retained**, using its unchanged original profile and processing.
- **CopyFinger Experimental removed from menu/routing**. Historical offline scripts and compatibility helper remain for reproducing earlier measurements, not as a selectable bot preset.
- **Auto-Fit V5 (AfterEffects)** exposed as a distinct mode using `macros/AutoFit V5 AfterEffects.json` and `reference_v5/aftereffects.py`, not CopyFinger's older `AutoFit V5 Reference.json`.
- V4 macros, spectral processing, searches and other existing modes unchanged.

V5 applies the fitted graph once, then reuses whole-song overlapping recognition checks, original-file controls and **API pacing (API Cooldown)**. Inconclusive responses are not verified no-matches. A failed recognition check never triggers a pitch/tempo/speed fallback. Normal export is `<source>_AutoFitV5.ogg`, Vorbis q8 with 1.5 dB fixed delivery attenuation. This is not source-loudness matching or a guaranteed decoded peak ceiling.

“Musical Hz” is implemented here as actual frequency-band shaping and supported harmonic/dynamic processing. No pitch shift/detuning, time stretching, clock/header manipulation, tempo/speed change, modulation, injected noise, or concealed source-timeline adjustment was introduced. More aggressive arbitrary effects were not assumed solely from the request's wording; this particular reference is darker, not the earlier heavily flattened bright reference.

## Supplied files and timing limitation

Both files were fetched from main and decoded as stereo 48 kHz:

| | BeforeEffects | AfterEffects |
|---|---:|---:|
| Samples/channel | 10,329,443 | 10,551,168 |
| Duration | 215.196729 s | 219.816000 s |
| RMS | .33846 | .27982 |
| Sample peak | 1.31399 | 1.04961 |
| Crest | 11.782 dB | 11.483 dB |
| 50-ms RMS p95–p5 | 22.916 dB | 34.167 dB |
| L/R correlation | .95193 | .98039 |
| PSD centroid | 352 Hz | 284 Hz |
| 95% PSD roll-off | 1,359 Hz | 1,090 Hz |

The reference is **4.619271 seconds longer** and ends with negligible/zero samples (e.g. reference seconds 216–218 are zero). This does not by itself indicate slowing. Twenty-one 8-second band-envelope correlations across 80–300, 300–1,200 and 1,200–5,000 Hz find lags of **−.28 to −.30 seconds**, approximately constant over the song, with normalized correlations .749–.982. That supports an offset rather than obvious long-term drift in these sampled envelope landmarks. It is not proof of exact internal timing identity.

Band-limited waveform correlations are much weaker (roughly .106–.179), with inconsistent best lags. A nearest-spectral-peak diagnostic produces modes around **−30 cents** in several passages, but other passages disagree and confidence is limited. Musical harmonics, EQ, phase and codec effects can mislead this estimator; a precise tuning change is **not established**. No original-plugin/pitch identity is claimed.

**V5 intentionally does not copy the apparent offset, extra silent tail or possible tuning difference.** It exports exactly the original 10,329,443 samples at 48 kHz, without cropping or padding the musical content. Hence it cannot exactly reproduce this reference's entire file/timeline. Causal EQ still has real frequency-dependent phase/group delay; no compensation is hidden in the export.

Diagnostics are recorded in `timing.json`, `waveform-timing.json` and `tuning-diagnostic.json`. The .29-second estimate is used solely to select comparable reference passages for statistical fitting; it is not in the deployed DSP.

## Why the old fingerprint percentage is misleading here

With the unchanged LocalPrint comparator, this actual original/modified pair has **46.93%** temporal agreement at zero lag. A descriptor-only alignment diagnostic using six analysis frames (.27864 s) raises it to **75.77%**, with chroma cosine rising from .8247 to .9386. No audio was shifted and no exported file was changed by this diagnostic. It is not a service recognition result.

A low zero-lag score can therefore reflect reference misalignment, not successful removal of musical identity. V5 is fitted to tonal/dynamic features, not optimized to force a local-score target. No maximum recognition percentage or third-party no-match guarantee is claimed.

## Fitting method and exact graph

Twelve continuous two-second passages span 10–203 seconds; six alternating passages are training and six validation. Input passages include a half-second causal warm-up omitted from measurement. Comparable target passages use the **analysis-only** envelope offset. Both candidate families use the same five complementary causal second-order lowpass basis at 60/180/1,200/5,000 Hz, broad gain, linked RMS detector and M/S side gain.

| Candidate | Training feature objective | Validation objective |
|---|---:|---:|
| Linear output stage | .48643 | .32311 |
| Tanh output stage | .43499 | .23294 |

These objectives combine band PSD log powers, RMS, envelope spread, crest and L/R correlation. They are not listening scores. Validation selected the tanh family; subsequently side gain was refined against whole-song reference correlation, so final stereo matching is **not independent validation**. Final whole-song measurements contain training material. The fit is bounded/approximate, and the low-band gain approaches its bound; static EQ/dynamics may not explain all reference processing.

Selected graph, all in SciPy/NumPy at the source clock:

1. Complementary causal basis `LP60`, `LP180−LP60`, `LP1200−LP180`, `LP5000−LP1200`, `input−LP5000` at **−23.9960 / +3.8637 / 0 / +1.1210 / −1.4404 dB**. These overlap with phase interaction; they are not rectangular-band levels or raw measured spectral ratios.
2. 50-ms linked RMS detector, .02 floor, gain exponent **−.00128295** (very little explicit compression).
3. Drive **−9.45447 dB**, then `tanh` saturation.
4. M/S side gain **.870391**, fixed from this reference study.
5. Output gain **+4.91620 dB**.
6. Bot delivery only: **−1.5 dB** and Vorbis q8 encoding. EQ/dynamics are not repeated in FFmpeg.

This is not an Audacity/plugin emulation, nor proof of the original chain or effect order. The reference's lower waveform correlation and possible tuning difference are not reproduced by this simple model.

## New render: remaining differences

| Measure | Reference entire file | V5 DSP before delivery gain |
|---|---:|---:|
| RMS | .27982 | .27118 |
| Crest | 11.483 dB | 11.763 dB |
| Sample peak | 1.04961 | 1.05053 |
| L/R correlation | .98039 | .98039 (explicitly calibrated) |
| 50-ms envelope spread | 34.167 dB | 26.249 dB |
| Centroid | 284 Hz | 206 Hz |
| 95% roll-off | 1,090 Hz | 715 Hz |

The approximation remains too bass-dominant/dark by these PSD measures and does not reproduce the reference's envelope range. Reference duration/tail differences also affect whole-file distribution measurements; equal excerpt contexts were used for fitting, not forced by changing the output timeline. Correlation matched as a statistic does not prove equivalent stereo processing.

Encoded delivery is 215.196729 s at 48 kHz, RMS .22939, peak .89205 and correlation .98055. Decoded sample peaks are not true-peak measurements. The 1.5 dB attenuation is reported separately from the reference-level DSP validation figures.

## Deliverables and validation

- `beforeeffects_AutoFitV5.ogg`: full-length V5 delivery render, normal pitch/tempo/speed.
- `Original-matched.ogg`, `Reference-matched.ogg`, `CopyFinger-matched.ogg`, `AutoFitV5-matched.ogg`: −24 dBFS RMS listening comparisons, not validation-level renders.
- `spectrograms.png`: all four full files on identical −100…−20 dB/Hz PSD and axis scales; the reference's longer tail is not concealed.
- `results.json`, timing/tuning diagnostic JSON, new profile, processing module, fitting script and tests.
- `SOUNDCLOUD.md`: separately documents the DRM/error-handling change and its limitations.

**154 tests passed, plus 28 subtests**, including new V5 timing guards and 44.1/48 kHz tone tests, actual new-graph dispatch, one DSP pass across all recognition outcomes, and SoundCloud metadata-only/alternate-source/error cases. Regression tests compare legacy effect/search function ASTs and macro/pipe bytes, exempting the explicitly requested downloader changes. Menu tests now require V5 and reject the removed Experimental choice.

No live Discord, SoundCloud download, recognition service, subjective listening, Audacity or installed-plugin validation was available. Source files and CopyFinger profile hashes were checked unchanged. No push was performed in this operation.

Reproduce the bounded offline fit:

```sh
python -m reference_v5.train_aftereffects
```

This updates only the new AfterEffects profile and its artifacts, not the original CopyFinger profile. Historical reports describe older experimental states; the current menu is documented in the root README. Generated audio is Git-ignored. Restart/sync the bot normally to expose V5.
