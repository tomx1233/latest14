# Stronger CopyFinger experiment — lower local similarity, not verified evasion

## Result

With the **unchanged LocalPrint v1 comparator**, the selected experimental output lowers newsong2's temporal fingerprint agreement from **87.63% to 78.85%** (8.78 percentage points). Substantial shared structure remains. This is not a recognition probability, an external-service test, or a demonstrated solution to the reported identification.

The selected settings also score **79.63%** on the earlier TestSong, without retuning. That is a second-song generalization check, not a large independent validation dataset. LocalPrint selection can overfit LocalPrint: the same metric was used to choose the candidate. Fixed-key chroma remains high, .9440 on the encoded new-song experiment, so recognizable musical/harmonic content is still preserved.

## Controlled experiments

All four manually authored candidates were tested on the complete new song, not short excerpts. The comparator implementation is unchanged; its SHA-256 is recorded alongside the source hash in `results.json`. No threshold was changed or weak windows dropped to manufacture a lower score.

| Candidate | Pre-encode temporal agreement | Fixed-key chroma cosine |
|---|---:|---:|
| multiband-gentle | 82.86% | .9655 |
| multiband-dense | 79.67% | .9520 |
| multiband-extreme | 78.86% | .9436 |
| multiband-midforward | 79.34% | .9336 |

Selection minimizes whole-song temporal agreement only. Final encoded Ogg agreement is 78.85%. Original CopyFinger Ogg was 87.63%. The compared confident-bit count is 99,040 versus 101,446 for baseline, with the same 5,162 active comparable frames; scores remain conditional on the unchanged confidence-mask rules. Changes in valid bit positions are a limitation of this metric. Results are not all-bit mismatch percentages.

## Selected processing graph

`reference_v5/experiment.py`, candidate `multiband-extreme`:

1. Stereo-linked causal three-band split using second-order Butterworth lowpasses at 180 and 1,600 Hz: low, difference/mid, residual/high.
2. Independent **band** detectors, each linked across L/R, 3-ms exponential power smoothing. Normalize by `max(sqrt(power), .015)^1.0`.
3. Drive each controlled band by 15 into `tanh` and sum with low/mid/high weights .45/.8/1.0.
4. Causal second-order 100-Hz highpass, then `tanh(1.5 * signal)`.
5. Ogg Vorbis quality 8, fixed **−6 dB delivery attenuation**. This is separate from the original −1.5 dB export and not source-loudness matching.

No pitch shift, clock change, tempo/speed change, time warp, modulation, noise injection, or cropping/padding. Source is stereo 48 kHz; encoded result decodes to exactly **11,545,705 samples/channel**, like the original. Musical timeline is not remapped; causal filters still have their own phase/group delay. This is an experimental dynamics/saturation chain, not an Audacity/plugin emulation or a recovered reference chain.

## Sound-character tradeoff

Before delivery attenuation, newsong2 experiment has:

- RMS .8020; crest **1.91 dB** (baseline CopyFinger 2.82 dB).
- 50-ms RMS envelope spread **.94 dB** (baseline 2.19 dB).
- L/R correlation **.569** (baseline .755).
- PSD centroid **2,715 Hz** (baseline 1,975 Hz).

It is substantially more flattened, brighter and less stereo-correlated. Those are objective changes, not a subjective listening assessment. On the earlier song, reference correlation is .863 while experiment is .644; reference centroid is 1,940 Hz while experiment is 2,874 Hz. The experiment therefore moves further away from the measured reference in these respects. There was no subjective listening or live recognition available here.

The final Ogg's RMS is −7.96 dBFS and decoded sample peak .6704 after −6 dB attenuation. Encoding still changes crest factor; pre-encode and delivery numbers are separated in JSON.

## Files and status

- `newsong2_CopyFinger-experimental.ogg`: selected full-length experimental export.
- `newsong2_experimental_matched.ogg`: quieter −24 dBFS RMS pre-encode listening copy, matching the earlier comparison-copy target.
- `results.json`: all candidates, full-window comparisons, selected parameters, baseline, encoded delivery and second-song results.

**Existing CopyFinger profile, bot conversion, V4 and the comparator were not changed.** No runtime incremental testing was added. The experiment remains separate because a lower local score is not sufficient reason to replace the successful reference-fit preset.

Reproduce offline:

```sh
python -m reference_v5.run_experiment
```

Requires the previously generated baseline `reports/copyfinger_newsong2/newsong2_CopyFinger.ogg`; `python -m reference_v5.compare_codecs` regenerates it. Generated audio is Git-ignored.

Validation: **124 tests passed, plus 28 subtests** in the selected regression suite. New tests cover all four candidates at both 44.1/48 kHz, exact sample count, preserved test-tone fundamental, input-array immutability, no output from silence, and rejection of non-normal pitch/tempo/speed arguments. These prove implementation invariants, not recognition failure. A dramatically lower score was **not** achieved within this bounded experiment; no such claim is made.
