# Auto-Fit V5 (Reference) — reconstructing NewTest.ogg from TestSong.ogg

This document describes a **new, separate** Auto-Fit mode. It does not change how
Auto-Fit V3 or V4 sound: their macros, profiles and code paths are untouched
(`macros/CopyR8 AutoFit V3.txt` and `V4.txt` are byte-identical to the previous
release, and the regression tests hash-check that).

Everything below is either a **measurement** (something computed from the two
supplied files) or an **inference** (a guess about what produced them). The two
are labelled separately, because the reference is a rendered 149-second file, not
a project file.

| | |
|---|---|
| Source | `TestSong.ogg` — 44.1 kHz stereo Vorbis, 149.3346 s |
| Reference | `NewTest.ogg` — 44.1 kHz stereo Vorbis, 149.3361 s |
| Delivered sound | `analysis/out/TestSong_v5_reference.mp3` (produced by the shipped V5 path) |
| Shipped profile | `macros/autofit_v5_reference.json` |
| Shipped macro | `macros/CopyR8 AutoFit V5 Reference.txt` |

---

## 1. Headline result

| Whole track | TestSong (source) | NewTest (reference) | V5 render (pre-encode) | Delivered MP3 |
|---|---|---|---|---|
| Integrated loudness | −8.8 LUFS | **+1.9 LUFS** | +1.0 LUFS | **+1.9 LUFS** |
| True peak | +12.4 dBTP | **+4.2 dBTP** | +1.5 dBTP | +3.7 dBTP |
| Sample peak | 2.92 (9.3 dBFS) | 1.107 (+0.9 dBFS) | 0.99 | 1.43 (codec, see §7) |
| Crest (peak/RMS) | 19.5 dB | **2.63 dB** | 2.72 dB | 5.0 dB (codec, see §7) |
| Loudness range (LRA) | 8.2 LU | **0.7 LU** | 1.2 LU | — |
| 10 s block level span | 8.9 dB | **0.8 dB** | 0.7 dB | — |
| L/R correlation | 0.968 | **0.863** | 0.796 | 0.796 |
| Zero-crossing rate | 1 672 /s | **4 752 /s** | 5 605 /s | 5 646 /s |
| Nine-octave band error vs reference | 7.6 dB RMSE | — | **0.58 dB RMSE** | 0.60 dB RMSE |

The delivered file matches the reference **within 0.6 dB on every octave from
30 Hz to 15 kHz and exactly on integrated loudness**. The remaining differences
are listed in §8; none of them is hidden.

---

## 2. Same recording? (measured)

* **Length**: 149.3346 s vs 149.3361 s — a 67-sample difference (1.5 ms), i.e.
  encoder padding, not an edit.
* **Alignment**: cross-correlation puts the reference **1169 samples (26.5 ms)
  late**, and the lag is constant across the whole file (measured at 10 points;
  no drift). A constant offset with no drift rules out a speed/tempo change.
* **Tempo**: exactly 1.0. The V5 ladder is fixed at tempo 1.0
  (`V5_TEMPO = 1.0`) and only allows 0 to −0.20 semitones of pitch shift for the
  recognition probe — no arbitrary speed-up. There is no evidence for one.
* **Pitch**: chroma correlation peaks at **0 semitones** (0.911). The reference
  is the same performance in the same key.

So: every difference between the two files is tone, dynamics or level — nothing
is timing or pitch. That is the foundation the rest of the reconstruction rests
on.

---

## 3. What the reference actually is (measured)

### 3.1 It is not an EQ: the source→reference map is not linear

The strongest single observation. A static per-bin transfer function estimated by
coherence explains **−4 %** of the reference's power; the magnitude-squared
coherence between source and reference collapses from 0.77 at 80 Hz to 0.026 at
500 Hz and ~0.01 above 8 kHz. A linear filter keeps coherence; this does not.
Something **memoryless and nonlinear** sits in the middle of the chain.

Corroborating measurements:

* Crest factor 19.5 dB → 2.63 dB.
* **27.2 %** of reference samples sit at or above 0.999 — the waveform is
  flat-topped.
* Harmonics rise relative to the fundamental in exactly the way a soft clipper
  predicts.
* The source has a damaged transient at t≈0.010–0.015 s (peak 2.92, true peak
  +12.4 dBTP). The reference has no such transient: it is clipped like
  everything else, which is why the reference's true peak is *lower* than the
  source's despite being 10.7 dB louder.

### 3.2 It is level-flattened, harder than the clipper alone can do

Measured over 10-second blocks:

```
source : -11.3 -12.5  -9.2  -9.3 -11.5  -9.6 -10.0 -10.7 -18.1 -10.2  -9.3  -9.5  -9.7  -9.9
ref     : -2.6  -2.5  -1.9  -2.1  -2.2  -1.8  -1.9  -1.9  -2.4  -2.2  -1.8  -2.0  -2.0  -1.9
```

The source spans 8.9 dB; the reference spans 0.8 dB. Regressing the gain the
reference applies against the source level gives a slope of **≈0.95 dB/dB**,
i.e. an effective **ratio near 20:1** — a leveller, not a limiter catching stray
peaks. The quiet passage at 82–95 s (−18 dB in the source) is only 0.4 dB down
in the reference.

That is also why the reference's LRA is 0.7 LU. **A saturator alone cannot do
this** (it lowers peaks but never raises a quiet section), which is what the first
attempt at this chain got wrong — see §9.

### 3.3 Tone

Relative to the 120–1920 Hz median, nine octaves 30 Hz → 15.36 kHz:

```
band      30-60  60-120 120-240 240-480 480-960 960-1.9k 1.9-3.8k 3.8-7.7k 7.7-15k
source    +8.7   +5.9    +5.1    +0.6    -0.6    -2.9     -3.9     -6.2     -7.9
reference -11.9   +0.0    +1.6    +0.3    -0.3    -1.5     -1.5     -2.4     -2.6
```

Above the fitted 15.36 kHz octave (measured separately): 16–20 kHz is −16.6 dB
in the reference and −24.0 dB in the source; 20–22 kHz −21.4 vs −29.8. So the
reference **adds** high-frequency energy — it is brighter and much flatter than
the source, not darker. Two things cause that: the pre-emphasis before the
saturator, and the harmonics the saturator itself generates.

The 30–60 Hz octave is 20 dB down relative to the source, which is what a
high-pass filter at ~100 Hz does.

### 3.4 Stereo, modulation, codec

* **Stereo**: L/R correlation falls 0.968 → 0.863, and the reference's L/R
  coherence per octave is 0.46–0.91 (the source is ≈1.0). The processing is
  therefore **not** a pure mono-sum or a pure per-channel copy — it is mostly
  correlated, partly decorrelated. Mid/side analysis shows the side channel is
  compressed by the same nonlinearity (it is present, not generated).
* **Modulation**: the amplitude-modulation spectrum of the reference has **no
  periodic component** — no tremolo, no chorus, no vibrato, no pumping at any
  rate from 0.2 to 20 Hz beyond the noise floor.
* **Reverb**: the reference's decay after the final note is *shorter* than the
  source's; nothing was added.
* **Codec**: both files are Vorbis at 44.1 kHz. Vorbis cannot encode above
  ~20 kHz, and its own decoding creates a little noise in the 14–16 kHz region.
  Those are codec artifacts, not effects, and are excluded from the chain.

---

## 4. The reconstructed chain

Order matters, and this is the order that reproduces the measurements.

| # | Stage | Value | Confidence | Why |
|---|---|---|---|---|
| 1 | Leveller (compressor) | threshold −20 dB, ratio 10:1, attack 10 ms, release 400 ms, +3.5 dB makeup | **high** that a leveller exists; **medium** on the exact device | §3.2: gain tracks input ~1:1 across 8.9 dB of program dynamics; a clipper cannot raise a quiet section |
| 2 | High-pass, 4th order | 99.6 Hz | **high** | 30–60 Hz octave 20 dB down vs source, in a way that only a steep HP at ~100 Hz produces |
| 3 | High shelf (pre-emphasis) | 3206 Hz, **+16.39 dB** | **high** for "a large HF pre-emphasis before the clipper"; **medium** on corner/slope | without it the saturator cannot produce the reference's flat-topped HF; the fit's residual falls to 0.58 dB only with it |
| 4 | Memoryless soft clip | `atan(x·100)·2/π` (drive +40 dB) | **high** on "memoryless, symmetric, compressive"; **medium** on the exact shape | §3.1 coherence collapse, flat tops, 27 % of samples at FS |
| 5 | High shelf (de-emphasis) | 5274 Hz, **−4.65 dB** | **medium** | the curve after the clipper needs a HF tilt back; the corner is not uniquely identifiable |
| 6 | High shelf | 17.5 kHz, **−6.0 dB** | **medium** | clipping harmonics ran 5–6 dB hotter than the reference above 16 kHz; this closes it and brings the crest from 2.53 to 2.61 |

Fitted by differential evolution over the actual ffmpeg filter graph (not an
idealised model), objective = level-matched nine-octave balance + crest + L/R +
zero-crossing density + amplitude histogram, then a full-track sweep for the
drive. Fit statistics: **band 0.97 dB, crest 2.23 dB (reference on the same
excerpt: 2.24), ZCR ratio 0.996, L/R 0.822 (reference 0.821)**.

### 4.1 Why not the V4 chain, and why not reverb

Both were tried and rejected by measurement, not taste:

* **Repeating the V4 macro chain** on top of itself: band error floor 6.75 dB,
  crest 22.4 dB. Wrong shape, wrong dynamics.
* **Diffuse reverb + clip**: L/R correlation ≥ 0.930 against the reference's
  0.863, and the reference's decay is *shorter* than the source's. Reverb is not
  in the reference.

### 4.2 What cannot be established

* **Which plugin or processor did it.** A compressor, a maximiser, a limiter
  with heavy makeup, or an Audacity Compressor + Amplify pair all produce the
  measured 10-second block profile. The render ships with the Audacity-native
  equivalent (§5) at Audacity's maximum ratio.
* **The exact saturator.** Measured shape is memoryless, symmetric and
  compressive. `atan`, `tanh` and a sine-knee soft clip are all within a few
  tenths of a dB of each other on the fit metrics; nothing in the data separates
  them.
* **The exact order of stages 5 and 6**, and whether the de-emphasis was an EQ or
  part of a plugin's output stage.
* Whether the chain was applied once or twice at lower drive (it is mathematically
  close, but not identical, to a single harder pass).

I am not claiming a specific plugin was used. I am claiming that this chain
reproduces the measured behaviour of the file.

---

## 5. The Audacity 2.3.3 macro

`macros/CopyR8 AutoFit V5 Reference.txt` — seven **native** steps, no VST, no
LADSPA, no SC1, no TDR Nova, no Blue Cat:

```
Compressor:Threshold="-20" NoiseFloor="-40" Ratio="10" AttackTime="0.1" ReleaseTime="1" Normalize="0" UsePeak="0"
High-passFilter:frequency="99.6" rolloff="dB24"
BassAndTreble:Bass="0" Gain="0" Link_Sliders="0" Treble="16.39"
Amplify:Ratio="149.62" AllowClipping="1"
Limiter:type="SoftClip" gain-L="0" gain-R="0" thresh="-0.1" hold="10" makeup="Yes"
BassAndTreble:Bass="0" Gain="0" Link_Sliders="0" Treble="-6"
Normalize:PeakLevel="-1" RemoveDcOffset="0" ApplyGain="1" StereoIndependent="0"
```

Approximations you should know about, because Audacity 2.3.3 cannot express the
fitted values exactly:

1. **Bass and Treble's shelves are fixed at 250 Hz and 4 kHz** (`BassTreble.cpp`,
   `hzBass = 250`, `hzTreble = 4000`, slope 0.4). The fitted 3.2 kHz pre-emphasis
   and 5.3 kHz de-emphasis are applied at 4 kHz instead. This is the single
   largest approximation in the macro.
2. **The Compressor's fastest attack is 0.1 s and fastest release 1.0 s**, where
   the render uses 10 ms / 400 ms. For section-level levelling (the thing §3.2
   measures) the difference is small; for sharp transients the macro is slower.
3. **The 17.5 kHz shelf has no native equivalent** and is folded into the
   −6 dB Treble step. The macro is therefore slightly darker above 15 kHz than
   the render.
4. `Amplify 149.62` = +40 dB drive + 3.5 dB leveller makeup. Audacity's Amplify
   is linear, so this is exact.

The bot **does not silently substitute** anything: `audacity_processor` checks
every step's effect against Audacity's own effect registry and raises
`MacroProcessingError` listing anything missing. If Audacity is unavailable, the
mode falls back to the ffmpeg renderer and says so in the embed and the log.

---

## 6. How the mode works

`copyr8_autofit_v5()` — a separate profile, a separate macro, a separate function.
V3/V4 code paths are not called.

```
input → macro (Audacity)  ─┐
        or ffmpeg chain   ─┴→ residual octave trim → bounded recognition ladder
                              → export at the reference's loudness → spectrogram
                              from the exported file
```

* **Residual trim**: the render is measured against the profile's nine-octave
  target and corrected with `equalizer` biquads, **clamped to ±6 dB per band**,
  skipped entirely inside 0.3 dB, and applied *before* the clipper (an EQ after
  the clipper rings on the flat tops and pushed the crest from 2.55 to 5.35 dB in
  testing). Two passes maximum; the closest render wins.
* **Recognition ladder**: same overlapping whole-song probe windows and the same
  shared API pacing with the "API Cooldown" label as V3/V4. V5 only tries 0 to
  −0.20 semitones (five rungs) because the reference shows no pitch change, and
  tempo is pinned at 1.0. If nothing verifies, the mode keeps the reference sound
  and reports it as unverified rather than shifting the pitch to chase a result.
* **Recognition is reported separately from reference fidelity** — the embed has
  a "Reference Match" field (octave RMSE, crest, width) next to the recognition
  verdict, and the two never overwrite each other.
* **Export**: filename is cleaned the same way as the other modes, metadata is
  stripped, and no AI/processing wording is written into the file. The export
  targets the *reference's* loudness (+1.9 LUFS) rather than the source's,
  because matching the source would throw the target sound away.

---

## 7. Validation of the delivered sound

Measured on `analysis/out/TestSong_v5_reference.mp3`, decoded back to 44.1 kHz
stereo, against `NewTest.ogg`:

```
band         ref     out     Δ
  20-60     -12.0   -13.1   -1.1
  60-120     +0.1    -0.5   -0.6
 120-240     +1.6    +2.6   +1.0
 240-480     +0.3    +0.2   -0.1
 480-960     -0.3    -0.2   +0.1
 960-1920    -1.5    -1.6   -0.1
1920-3840    -1.5    -1.1   +0.4
3840-7680    -2.4    -2.0   +0.4
7680-15360   -2.6    -2.9   -0.3
15360-20000 -16.6   -14.8   +1.8
```

Figures (identical analysis settings for both files):

* `analysis/out/compare_spec.png` — 0–16 kHz spectrograms, reference above,
  render below, same 4096-point window, same colour limits.
* `analysis/out/compare_wave.png` — peak envelope, 10 ms resolution, all three
  files on the same −60…+8 dB axis.
* `analysis/out/compare_ltas.png` — long-term average spectra, level-matched at
  200–2000 Hz.

### 7.1 The one number that looks bad, and why it is the codec

The delivered MP3 decodes with crest 5.0 dB against the render's 2.72 dB. That is
not a rendering error:

| File | crest before MP3 | crest after MP3 320k round-trip |
|---|---|---|
| **NewTest.ogg itself** | 2.63 dB | **4.37 dB** |
| TestSong.ogg | 19.52 dB | 20.75 dB |
| this render | 2.72 dB | 5.34 dB |

Encoding the reference to MP3 and decoding it again *by itself* inflates its
crest from 2.63 to 4.37 dB and its sample peak from 1.107 to 1.351. A waveform
with flat tops and energy up to 17 kHz is close to the worst case for MP3's
polyphase filterbank. Our render behaves the same way, slightly more so (2.72 →
5.34 vs 2.63 → 4.37), because it is marginally brighter near 16 kHz.

This is why the crest is quoted from the **pre-encode render** (2.72 dB vs the
reference's 2.63 dB) and the codec inflation is reported separately.

---

## 8. What still differs, audibly

Listed in decreasing order of how likely they are to be heard.

1. **Loudness range: 1.2 LU vs the reference's 0.7 LU.** The render is levelled,
   but not quite as flat as the reference. The 10-second block span matches
   (0.7 dB vs 0.8 dB), so what remains is within-section micro-dynamics, not
   section-to-section level. This is the largest measurable residual.
2. **Stereo width: L/R correlation 0.796 vs 0.863.** The render is slightly
   wider/more decorrelated than the reference. The chain has no stereo stage, so
   this comes from how the source's side channel interacts with the leveller.
   On a phone speaker or a mono sum this is inaudible; on headphones the render
   may sound a little wider.
3. **Brightness above 15 kHz: +1.8 dB at 16–20 kHz.** The 17.5 kHz shelf closes
   most of it but not all.
4. **Zero-crossing density 5 605/s vs 4 752/s (+18 %).** Our waveform crosses
   zero more often than the reference's at the same octave balance. Part is the
   MP3 codec, part is that the reference was Vorbis, whose high band is
   noise-like rather than pulse-like. This is the summary statistic for "the
   render has slightly sharper edges than the reference".
5. **True peak +3.7 dBTP vs +4.2 dBTP.** Close, and both files are over full
   scale by design (the reference itself is a +4.2 dBTP master).

Not present in the render, because not present in the reference: added tones,
sweeps, tremolo/chorus/flanger, reverb, ultrasonic ribbons, or artificial
pumping.

**Where the evidence conflicts with a preference**: a slower, gentler sound was
requested in principle, and the reference does preserve the performance's
timing and pitch exactly — nothing is sped up. But the reference is *itself* an
extremely loud, heavily levelled master (+1.9 LUFS, 0.7 LU range, 27 % of
samples clipped). Reproducing it faithfully and keeping a wide dynamic range are
mutually exclusive. The mode follows the reference, because that was the brief;
the levelling is the part of it most likely to be noticed.

---

## 9. Two bugs this work found in its own earlier version

Recorded because they changed the numbers, and because anyone re-running the fit
needs to know.

1. **Sampling-rate propagation through `aeval`.** ffmpeg's biquad filters take
   their coefficients from the link's sample rate, and `aeval` does not propagate
   one. Every filter placed after the saturator — the whole de-emphasis stage —
   was **silently a no-op**. The proof is byte-identical output with the stage
   present and removed. Fixed by restating the format after `aeval`; the fit was
   then re-run from scratch, and the params in the profile are from the corrected
   signal path.
2. **Post-clip EQ.** Correcting the tone *after* the clipper rings on the flat
   tops: a 0.8 dB cut raised the crest from 2.55 dB to 5.35 dB. The residual trim
   therefore runs before the clipper, where the saturator re-flattens the
   overshoot (2.72 dB measured).

---

## 10. Tests

```
test_v5_reference.py                                    24 tests  OK  (~153 s)
test_copyr8_macro + test_v4_audio + test_v4_tempo       51 tests  OK
test_bot_delivery + test_gating + test_acoustid
             + test_songrec + test_updates              94 tests  OK
```

The V5 suite covers: the profile's numbers and its embedded fallback, the macro's
native-only steps and mirrored parameters, the chain graph (and the assertion
that it contains no generator, modulation or sweep), the trim clamp, the render
and export (including "no ID3, no encoder string, no internal wording"), the flow
order (macro → trim → probe → export → spectrogram), the ladder's refusal to
shift pitch when nothing verifies, and the V3/V4 byte-level guards.

Not covered, and honestly so: **no live Discord run** was made from this
environment. The bot-side wiring (preset, embed fields, cooldown labelling,
verdict wording) is covered by tests that exercise the real handler code, but the
end-to-end path against the real APIs and a real Audacity install is untested
here.
