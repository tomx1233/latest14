# Third supplied pair: Reference3 profile study

## Scope and conclusions

Downloaded `newtestoriginal3.ogg` and `newtestmodified3.ogg` from GitHub main without switching the session branch. Both decode to stereo 44,100 Hz, **9,474,555 samples/channel / 214.842517 seconds**. Their hashes, full metrics, diagnostic correlations, candidate settings and scores are in `results.json`.

This is offline effects fitting using the newly supplied paired example, **not machine-learning training of a recognizer**. No external identification API was accessible, no subjective listening test was performed, and Audacity/plugins were unavailable. No external no-match outcome is assumed for either supplied modified file.

The new modified file is virtually mono and retains substantially more dynamics than NewTest.ogg. A mono downmix is evidence-supported for this pair, not for the first reference. A single shared fixed profile cannot simultaneously reproduce these distinct stereo outcomes. The cross-pair render also fails to reproduce the first reference's dynamics and tone. Therefore **existing CopyFinger, V4 and the LocalPrint comparator are unchanged**. A separate experimental Reference3 profile has been added for evaluation; there is no automatic source classifier, runtime search, or recognition fallback.

## Full-song measurements

Pre-encode fitting results are separated from lossy delivery results.

| Measurement | Original3 | Modified3 target | Existing CopyFinger | Reference3 fitted DSP |
|---|---:|---:|---:|---:|
| RMS | .26702 | .57359 | .79969 | .57774 |
| RMS dBFS | −11.469 | −4.828 | −1.942 | −4.765 |
| Sample peak | 1.24947 | 1.05289 | 1.07394 | .99177 |
| Crest dB | 13.404 | 5.276 | 2.561 | 4.694 |
| 50-ms RMS p95–p5 dB | 13.907 | 8.290 | 2.647 | 8.179 |
| L/R correlation | .79341 | .9999938 | .48387 | 1.00000 |
| PSD centroid Hz | 814 | 1,707 | 3,456 | 1,903 |
| 95% PSD roll-off Hz | 4,296 | 6,546 | 10,928 | 7,450 |

Original-to-target RMS increase is 6.64 dB. Existing CopyFinger is too bright, dynamically flattened and stereo-decorrelated for this particular target.

The bounded fit lowers the full-song weighted feature objective from **6.6161** (existing preset) to **.09067**. This custom objective is not a perceptual listening score, recognition score, or percentage of exact matching. Reference3 output still has excess high-frequency energy and differs in peak/crest behavior.

The final Vorbis q8 reference-level delivery decodes to RMS .57862, sample peak **1.15418**, crest 6.00 dB, centroid 1,875 Hz and roll-off 7,311 Hz. Codec effects account for differences from pre-encode numbers. Peaks are decoded sample peaks, not true-peak measurements. The normal-level export can clip in playback paths limited to ±1; use the matched copies for evaluation.

## Candidate fitting and validation

Sixteen non-overlapping continuous two-second passages span the song. Alternating passages form eight training and eight validation excerpts. Each input excerpt has a half-second causal filter/detector warm-up that is excluded from the measured passage. The target is read at the same musical timestamps. Excerpt features combine band PSD log powers, RMS, crest, envelope spread and L/R correlation.

Four bounded families were fitted on training passages. The validation score was used to select a family, so it is **not an untouched final test set**. Whole-song reporting includes training and validation passages plus the remainder.

| Family | Training objective | Validation objective |
|---|---:|---:|
| Linked stereo, tanh | .92090 | .78421 |
| Mono mean, hard clip | .08813 | .10782 |
| Mono mean, tanh | .07311 | .09178 |
| Mono mean, smooth limiter approximation | .09898 | .11277 |

These results favor mono-linked processing plus tonal shaping and saturation in this limited model family. They do not establish the original plugin identities, original effect order, or compressor topology. Even for the selected family, the inferred parameters are not exact recovered settings.

## Exact selected graph

`macros/CopyFinger Reference3 Experimental.json`, executed by `reference_v5/reference3.py`:

1. Explicit `(L+R)/2` mono mean, duplicated into two output channels. This policy applies only to this experimental profile; it is not imported into V4 or the default CopyFinger path.
2. Existing causal complementary five-band Butterworth basis at 60 / 180 / 1,200 / 5,000 Hz, weighted **−6.5070 / −4.7108 / 0 / +6.6603 / +6.4695 dB**. These are overlapping filter basis gains, not ideal rectangular-band EQ settings.
3. 50-ms linked RMS detector; gain exponent **−.0505245** with the existing .02 RMS floor. This model needs much less explicit feed-forward compression than the first reference profile; saturation itself also reduces dynamics.
4. **+8.77050 dB** drive into `tanh` saturation.
5. **−.071788 dB** output gain.

No source-loudness matching or generic LUFS target. The normal-level delivery is Vorbis q8 at unity export gain; the separate listening copies use −24 dBFS RMS before encoding. Python does the sound processing; FFmpeg only encodes and strips metadata. No EQ/dynamics is repeated in FFmpeg.

All candidates and the selected graph remain **0.00 semitones / tempo 1.00x / speed 1.00x**. Exactly the original number of samples and sample rate are retained in DSP and gapless-aware Ogg decode. Originals and the default profile/comparator hashes were checked unchanged.

## Timing and pitch uncertainty

New original/reference durations are exactly equal, but that alone does not establish pitch or internal timing identity. Five normalized 200–1,000 Hz local waveform correlations find best lags of **15–17 samples** with correlation .862–.880; zero-lag correlations are lower. This is approximately .34–.39 ms, stable within this diagnostic, and could reflect filter phase/group delay or a small offset. It is not corrected, cropped or padded. No long-term drift is apparent in these sparse checks, but finer tuning/pitch and rhythm analysis remains unverified. Causal filtering introduces phase response; the implementation does not change the clock or musical timeline. Tests confirm a fixed test-tone fundamental; they are not a reference-pitch estimator.

## What the new pair teaches about LocalPrint

Actual Original3 → Modified3 temporal agreement is **89.56%**, with fixed-key chroma cosine .98302. Original3 → fitted Reference3 is **93.73%**, chroma .98535. The closer fitted tonal/dynamic features do not imply identical fingerprint behavior. Similarity is not a recognition probability, and “modified” is not evidence of an external no-match.

LocalPrint was **not** changed or optimized during this fit. Replacing the default profile merely to lower its local percentage would be a different objective from reproducing these supplied references.

## First-pair cross-check and generalization

Applied without retuning to TestSong, this new profile produces RMS .57870, crest 4.679 dB, envelope spread **12.003 dB**, correlation 1.0 and centroid 1,070 Hz. NewTest target is RMS .81740, crest 2.631 dB, spread **1.250 dB**, correlation .86295 and centroid 1,940 Hz.

Thus this model **does not generalize as a universal replacement** for the first reference profile. The two supplied reference pairs support at least distinct parameter/stereo regimes. No reliable automatic selection rule has been demonstrated from only two paired examples. The new profile remains experimental and explicit.

## Deliverables and reproduction

- `newtestoriginal3_CopyFinger-reference3.ogg`: full-length reference-level candidate, **very loud / decoded overshoot**.
- `Original-matched.ogg`, `Reference-matched.ogg`, `Baseline-matched.ogg`, `Fitted-matched.ogg`: −24 dBFS RMS listening comparisons.
- `spectrograms.png`: original, target, existing preset and fitted output on identical −100…−20 dB/Hz PSD and axis scales.
- `results.json`: exact metrics, parameters, hashes, candidate scores, timings and cross-pair checks.
- Separate profile, wrapper, offline fitting script and tests.

Reproduce from repo root:

```sh
python -m reference_v5.train_reference3
python -m pytest test_reference3.py test_copyfinger_experimental.py test_localprint.py test_reference_v5.py test_v4_tempo.py test_v4_audio.py test_gating.py test_bot_delivery.py test_updates.py -q
```

Validation: **130 tests passed, plus 28 subtests**. New checks cover fixed timing/fundamental at 44.1 and 48 kHz, explicit mono policy, zero-input silence, rejection of non-normal pitch/tempo/speed fields and no automatic substitution into CopyFinger. No changes are pushed by this fitting operation. Generated audio is ignored by Git.
