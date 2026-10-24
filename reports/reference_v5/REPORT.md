# CopyFinger — one-pass preset update

The Discord menu now exposes **CopyFinger** (`copyfinger`) as a fixed conversion preset, replacing the V5 Auto-Fit menu entry. It applies the fitted graph documented below **once**, without API calls, recognition windows, incremental tests, search, or fallback processing. It does not use the Auto-Fit API cooldown gate. Pitch stays 0.00 st, tempo/speed 1.00x. V4 remains unchanged.

The sound profile and previously measured render are unchanged. This rename does not improve the approximation or establish a fingerprint-recognition guarantee. Output filenames use `<source>_CopyFinger.mp3`. The internal V5 adapter remains available for historical tests; CopyFinger explicitly disables its recognition branch.

Validation after this change: **90 tests and 28 subtests passed**, including a test asserting one DSP invocation and no recognition/window/control calls. The earlier report below describes the original reference fitting and its limitations.

---

# Auto-Fit V5 (Reference): measured approximation

## Status and boundaries

Implemented `/copyr8` → **Auto-Fit V5 (Reference)** (`autofit-v5`). This is an independent JSON profile and NumPy/SciPy DSP path. It does not run or emulate Audacity effects. V1–V4, their macros, spectral processing and searches are unchanged. No pitch, clock, tempo, time-stretch, modulation, stereo-to-mono, noise injection, or recognition-driven fallback exists in V5.

**Not an exact reconstruction.** There was no earlier reference-fit script or validated render in this checkout. Audacity, its scripting pipe host, and installed plugins were unavailable; their effect IDs/parameters cannot be verified here. No Audacity macro is supplied with invented effect IDs. The JSON profile is the new processing graph. Listening and live recognition API validation were not performed. Outbound API access is restricted in this environment. Tests mock recognition outcomes; they do not establish an actual no-match.

## Verified source and measurements

The actual original is **TestSong.ogg**, not `testsong.mp3` (also present but unused). Both supplied Ogg files decode as stereo Vorbis at 44,100 Hz. FFmpeg headers are recorded in `diagnostics.json`; NewTest identifies `Lavc61.3.100 libvorbis`. Average container bitrates are approximately 429/487 kb/s.

| Measure | Original | Reference | V5 float render |
|---|---:|---:|---:|
| Samples/channel | 6,585,656 | 6,585,723 | 6,585,656 |
| Duration, seconds | 149.334603 | 149.336122 | 149.334603 |
| RMS | .308646 | .817396 | .796082 |
| Decoded sample peak | 2.92156 | 1.10653 | 1.07394 |
| Crest factor, dB | 19.523 | 2.631 | 2.600 |
| 50-ms RMS p95–p5, dB | 20.681 | 1.250 | 1.845 |
| L/R correlation | .96762 | .86295 | .78178 |
| Aggregate side/mid, dB | −17.807 | −11.334 | −9.120 |
| PSD centroid, Hz | 446 | 1,940 | 2,281 |
| 95% PSD roll-off, Hz | 1,970 | 9,572 | 8,882 |
| abs sample in .9959–1.0235 | .00197% | 27.165% | 5.733% |

Reference RMS rises 8.46 dB over original. Output is about .23 dB below reference RMS. These are sample peaks, **not true peaks**. The near-one bin is not a hard-clipped-sample measurement. No source normalization was applied before analysis; float decoding preserves original values above unity.

Methods: soundfile float64 decode; non-overlapping 2,205-sample RMS frames; Welch PSD, 4,096-sample windows, power averaged across channels; centroid/roll-off from that PSD; aggregate (not frame-average) side/mid power. These definitions explain differences from previously reported centroid, envelope and stereo figures. `measurements.json` includes band powers and all tested parameters. `spectrograms.png` uses identical −100 to −20 dB/Hz PSD limits, FFT size, frequency and time axes for all three files.

## Timing and tuning: unresolved reference diagnostics

Reference has 67 extra decoded samples (1.52 ms). Their cause is not established; no musical padding/cropping or compensation is applied. Equal duration is not treated as proof of pitch or timing identity.

The new 200–1,000 Hz local waveform diagnostic finds peaks around −1,170 samples in several windows, with normalized correlations varying roughly .24–.75. These **must not be treated as a trustworthy fixed offset**, especially given the earlier contradictory estimates and nonlinear transformation. Band-energy envelope diagnostics show frequency/time-dependent best lags, including zero and approximately −30 ms. Actual zero-lag correlations are also recorded, not normalized to their own maximum. These diagnostics do not confidently separate dynamics/filter phase from a reference offset or subtle timing/tuning change. No convincing monotonic drift is established, and no independent fine-tuning/octave analysis was completed. Reference tuning remains unverified. V5 stays at normal pitch/speed regardless. No −1,170 sample adjustment is used.

## Tested candidates and inference

Fit eight disjoint one-second excerpts spread from 10 to 138 seconds. Final measurement is whole-song, including material outside these excerpts. Objective combines band log powers, RMS, envelope spread, crest and L/R correlation; it is **not a perceptual listening score**. Fitting uses concatenated excerpt features; linked-envelope startup across those excerpts is an approximation. Full-song validation uses continuous processing.

| Controlled family | Excerpt objective (lower better) |
|---|---:|
| Broad tonal shaping + gain + hard clip | .84392 |
| Broad tonal shaping + gain + tanh | .82758 |
| Linked dynamics + smooth peak limiter | .40857 |
| Linked dynamics + hard clip | .40854 |
| Linked dynamics + tanh | .40316 |

All families use the same causal tonal basis. The small difference between the last three does not uniquely identify clipping topology. Strong dynamics plus brightening is supported by these measurements; exact processing order and original plugin identity are not established. Post-dynamics EQ, stacked compressors and independently controlled stereo compressors have **not** been exhaustively tested. No dedicated widener was justified: nonlinear processing already reduces correlation too far. This is a bounded first fit, not proof of a globally best chain.

## Exact implemented graph and confidence

Everything below runs in Python/SciPy at the decoded sample rate:

1. Four causal second-order Butterworth lowpasses at 60, 180, 1,200 and 5,000 Hz. Complementary differences form five basis signals `LP60`, `LP180−LP60`, `LP1200−LP180`, `LP5000−LP1200`, `input−LP5000`. These overlap with phase interaction; they are **not** ideal disjoint EQ bands.
2. Sum those signals at −8.94219, −14.62122, 0, +13.31825, +18.51765 dB.
3. Stereo-linked RMS power detector: 50-ms exponential smoothing of mean L/R squared samples. Multiply both channels by `max(sqrt(power), .02)^(-.87645852)`. No lookahead or time remapping.
4. Drive +4.90573 dB into per-channel `tanh` saturation.
5. Output gain +.61963 dB. This is deliberately very loud; no generic LUFS target or source-loudness matching.

High confidence in implementation invariants, moderate in broad tonal/dynamic hypothesis, low in original chain identity and audible equivalence. JSON stores full-precision settings and fixed 0/1/1 pitch/tempo/speed fields; altered fields are rejected. Causal filters have frequency-dependent phase/group delay; they do not insert/remove samples, and no delay correction is applied. Detector and nonlinearity have no lookahead. Original musical timeline and sample count remain unchanged.

FFmpeg in the bot only decodes, encodes and produces the delivery spectrogram; it does not repeat EQ/dynamics. WAV validation uses float PCM, preserving peaks above unity. Bot lossy exports apply **fixed −1.5 dB headroom**, explicitly reported separately; they are not the reference-level render. Metadata is stripped using `-map_metadata -1`, consistent with clean exports; input files are never overwritten. Existing filename sanitization stays in the bot.

## Render and A/B

- `TestSong-reference.wav`: reference-level float validation render. **Very loud; turn playback down first.** Players may clip its >1.0 samples.
- `Original-matched.ogg`, `Reference-matched.ogg`, `Output-matched.ogg`: all at the same −24 dBFS decoded pre-encode RMS, independently attenuated for level-matched comparison. This target accommodates the original's high crest factor without clipping. These are listening copies, not reference-level validation artifacts. Vorbis encoding can introduce small measurement changes.
- `spectrograms.png`, `measurements.json`, `diagnostics.json`: retained reproducible results.

Output remains measurably wider, with too much upper-mid energy, insufficient 80–320 Hz power, lower upper-treble roll-off and far fewer near-unity samples. Similar crest factor is not evidence of identical clipping. Audible differences still need human evaluation; no listening claim is made.

## Recognition and tests

Adapter reuses `_gapfree_windows`, `_probe_sweep`, `_control_check`, and their actual cooldown pacing with **API pacing (API Cooldown)** labeling. Inconclusive results stay inconclusive. Original control is run without changing either file. No recognition outcome changes any processing parameters, and unsuccessful checks are reported rather than triggering shifts.

Validated: **88 tests passed, 28 subtests passed** across `test_reference_v5.py`, `test_v4_tempo.py`, `test_v4_audio.py`, `test_gating.py`, `test_bot_delivery.py`, `test_updates.py`. New tests exercise all three nonlinearity families and compression strengths, reject non-normal timing parameters, check unchanged tone frequency/sample count, cover successful/unknown/inconclusive/matching recognition cases, and compare legacy macro/pipe files against the base commit. `killa_tools.py` retains its complete previous contents with only an appended V5 wrapper. Python compilation passes. No live Discord run was attempted.

Reproduce from repository root after installing requirements (plus imageio-ffmpeg if no FFmpeg binary is available):

```sh
python -m reference_v5.analyze
python -m reference_v5.validate
python -m pytest test_reference_v5.py test_v4_tempo.py test_v4_audio.py test_gating.py test_bot_delivery.py test_updates.py -q
```

Generated audio is ignored by Git; do not commit large intermediate datasets. Analysis scripts intentionally reproduce named outputs in `reports/reference_v5` and do not modify the supplied originals. Re-fitting updates only the V5 profile.
