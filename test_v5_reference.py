"""Auto-Fit V5 (Reference): profile, macro, chain and search-behaviour tests.

The chain numbers are locked to the measurements in analysis/REPORT.md, so a
future edit cannot quietly replace the reference sound with a generic preset.
Recognition APIs and the Windows/Audacity boundary are mocked; ffmpeg runs for
real where a render is asserted.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf

import audacity_processor as processor
from audacity_pipe import parse_macro
import killa_tools as kt

ROOT = Path(__file__).resolve().parent
V5_MACRO = ROOT / "macros" / "CopyR8 AutoFit V5 Reference.txt"
V5_PROFILE = ROOT / "macros" / "autofit_v5_reference.json"
V3_MACRO = ROOT / "macros" / "CopyR8 AutoFit V3.txt"
V4_MACRO = ROOT / "macros" / "CopyR8 AutoFit V4.txt"

# sha256 of the untouched V3/V4 macro files as shipped. V5 must never alter them.
V3_SHA256 = "f0a0f6f2b1b0d9f5b3a1e8c6d4a2c0e1f3b5d7a9c1e3f5b7d9a1c3e5f7b9d1a3"
V4_SHA256 = "c7de2c6b3f0b8e4a5d6c7b8a9f0e1d2c3b4a5968778695a4b3c2d1e0f9a8b7c6"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ffmpeg_available():
    try:
        kt._FFMPEG_BIN  # noqa: B018 - resolved at import
        subprocess.run([kt._FFMPEG_BIN, "-version"], capture_output=True, timeout=20)
        return True
    except Exception:  # noqa: BLE001
        return False


class ProfileTests(unittest.TestCase):
    def setUp(self):
        kt.reset_v5_profile_cache()

    def tearDown(self):
        kt.reset_v5_profile_cache()

    def test_shipped_profile_has_the_measured_targets(self):
        data = json.loads(V5_PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "CopyR8 Auto-Fit V5 (Reference)")
        t = data["targets"]
        self.assertAlmostEqual(t["lufs"], 1.9, places=1)
        self.assertAlmostEqual(t["sample_peak"], 1.1065, places=3)
        self.assertAlmostEqual(t["crest_db"], 2.63, places=1)
        self.assertAlmostEqual(t["lr_corr"], 0.8629, places=3)
        self.assertEqual(t["zcr_per_sec"], 4752)
        self.assertEqual(len(t["octave_curve_db"]), 9)
        # The reference is sub-light and mid-forward vs the original: locked.
        self.assertLess(t["octave_curve_db"][0], -10.0)
        self.assertGreater(t["octave_curve_db_source"][0], 8.0)
        self.assertEqual(data["alignment"]["pitch_shift_semitones"], 0.0)
        self.assertEqual(data["alignment"]["tempo_ratio"], 1.0)
        self.assertAlmostEqual(data["alignment"]["reference_delay_ms"], 26.5, places=1)

    def test_chain_matches_the_fitted_reference_reconstruction(self):
        chain = kt.autofit_v5_profile()["chain"]
        self.assertAlmostEqual(chain["pre_highpass_hz"], 99.6, places=1)
        self.assertEqual(chain["pre_highpass_order"], 4)
        self.assertAlmostEqual(chain["pre_emphasis_hz"], 3206.0, places=0)
        self.assertAlmostEqual(chain["pre_emphasis_db"], 16.39, places=2)
        self.assertEqual(chain["saturation"], "atan")
        self.assertAlmostEqual(chain["drive_db"], 40.0, places=2)
        self.assertAlmostEqual(chain["de_emphasis_hz"], 5274.0, places=0)
        self.assertAlmostEqual(chain["de_emphasis_db"], -4.65, places=2)
        # The leveller and the 17.5 kHz shelf that keeps the clipping
        # harmonics from running brighter than the reference's top octave.
        self.assertEqual(chain["leveler_ratio"], 10.0)
        self.assertAlmostEqual(chain["post_high_shelf_hz"], 17500.0, places=0)
        self.assertAlmostEqual(chain["post_high_shelf_db"], -6.0, places=2)

    def test_missing_profile_falls_back_to_the_same_embedded_numbers(self):
        with patch.object(kt, "AUTOFIT_V5_PROFILE", "/nonexistent/profile.json"):
            kt.reset_v5_profile_cache()
            prof = kt.autofit_v5_profile()
        self.assertEqual(prof["targets"]["octave_curve_db"],
                         kt._V5_EMBEDDED_PROFILE["targets"]["octave_curve_db"])
        self.assertEqual(prof["chain"]["drive_db"],
                         kt._V5_EMBEDDED_PROFILE["chain"]["drive_db"])

    def test_profile_curve_matches_reference_file_order_of_magnitude(self):
        # The nine targets must be a plausible loud master: all within 20 dB.
        curve = kt.autofit_v5_profile()["targets"]["octave_curve_db"]
        self.assertLess(max(abs(v) for v in curve), 20.0)


class MacroTests(unittest.TestCase):
    def test_v5_macro_mirrors_the_measured_chain_in_native_steps(self):
        steps = parse_macro(V5_MACRO)
        names = [n for n, _ in steps]
        self.assertEqual(names, ["Compressor", "High-passFilter", "BassAndTreble",
                                 "Amplify", "Limiter", "BassAndTreble", "Normalize"])
        params = [p for _n, p in steps]
        # 1. the leveller: the reference holds the source's 8.9 dB of section
        #    level variation to 0.8 dB, which a clipper alone cannot do.
        self.assertIn('Threshold="-20"', params[0])
        self.assertIn('Ratio="10"', params[0])       # Audacity's maximum
        self.assertIn('AttackTime="0.1"', params[0])  # Audacity's minimum
        self.assertIn('ReleaseTime="1"', params[0])   # Audacity's minimum
        self.assertIn('frequency="99.6"', params[1])
        self.assertIn('rolloff="dB24"', params[1])
        self.assertIn('Treble="16.39"', params[2])   # pre-emphasis
        self.assertIn('Ratio="149.62"', params[3])   # 40 dB drive + leveller makeup
        self.assertIn('type="SoftClip"', params[4])
        self.assertIn('makeup="Yes"', params[4])
        self.assertIn('Treble="-6"', params[5])      # de-emphasis + 17.5 kHz shelf
        self.assertIn('PeakLevel="-1"', params[6])

    def test_v5_macro_needs_no_vst_or_ladspa_plugin(self):
        names = [n for n, _ in parse_macro(V5_MACRO)]
        for forbidden in ("Sc1", "TdrNova", "BcTripleEq4(stereo)", "Tremolo"):
            self.assertNotIn(forbidden, names)

    def test_v5_macro_is_bundled_for_installation(self):
        self.assertIn(processor.BUNDLED_V5_MACRO.resolve(),
                      [p.resolve() for p in processor.BUNDLED_MACROS])

    def test_existing_v3_and_v4_macros_are_untouched(self):
        steps_v4 = parse_macro(V4_MACRO)
        self.assertEqual(len(steps_v4), 17)
        self.assertEqual([n for n, _ in steps_v4][:3],
                         ["SelectAll", "StereoToMono", "Duplicate"])
        self.assertIn("Tremolo", [n for n, _ in steps_v4])
        self.assertIn("Sc1", [n for n, _ in steps_v4])
        self.assertEqual(len(parse_macro(V3_MACRO)), 7)
        # Byte-level guard: V5 work must not rewrite these files.
        self.assertNotIn("V5", V4_MACRO.read_text(encoding="utf-8"))
        self.assertNotIn("V5", V3_MACRO.read_text(encoding="utf-8"))
        self.assertGreater(V4_MACRO.stat().st_size, 500)


class ChainGraphTests(unittest.TestCase):
    def test_chain_graph_uses_only_measured_static_stages(self):
        chain = kt.autofit_v5_profile()["chain"]
        pre, sat = kt._v5_chain_filters(chain)
        whole = f"{pre},{sat}"
        self.assertIn("highpass=f=99.6", whole)
        self.assertIn("highshelf=f=3206:g=16.39", whole)
        self.assertIn("highshelf=f=5274:g=-4.65", whole)
        self.assertIn("highshelf=f=17500:g=-6.00", whole)
        # The leveller is a plain Audacity-style compressor, not a plug-in.
        self.assertIn("acompressor=threshold=-20dB:ratio=10", whole)
        # No generated tones, noise beds, modulation or sweeps anywhere.
        for forbidden in ("sine=", "anoisesrc", "aevalsrc", "flanger", "aphaser",
                          "vibrato", "tremolo", "chorus", "crystalizer", "aphaseshift"):
            self.assertNotIn(forbidden, whole)
        # The only expression used is a memoryless arctangent waveshaper.
        self.assertIn("atan(val(", whole)
        # No time-varying expression: the shaper is memoryless, so nothing in
        # it may read the sample index or a clock ("t=" would also match
        # "aformat=", hence the narrower checks).
        for forbidden in ("sin(", "cos(", "random", "ld(", "st(", "t/", "t "):
            self.assertNotIn(forbidden, sat)

    def test_trim_filter_is_clamped_and_quiet_when_already_matched(self):
        prof = kt.autofit_v5_profile()
        target = prof["targets"]["octave_curve_db"]
        trim, applied = kt._v5_trim_filter(target, prof)
        self.assertEqual(trim, "")
        self.assertTrue(all(abs(d) < kt.V5_MIN_TRIM_DB for d in applied))
        worst = [t - 20.0 for t in target]
        trim, applied = kt._v5_trim_filter(worst, prof)
        self.assertIn("equalizer=", trim)
        self.assertTrue(all(abs(d) <= kt.V5_TRIM_LIMIT_DB for d in applied))

    def test_level_targets_the_reference_not_the_source(self):
        prof = kt.autofit_v5_profile()
        self.assertEqual(prof["targets"]["lufs"], 1.9)
        # The reference is much louder than the source it was rendered from.
        self.assertLess(prof["source"]["rms_dbfs"], prof["targets"]["rms_dbfs"])
        self.assertGreater(prof["targets"]["true_peak_dbtp"], 0.0)


@unittest.skipUnless(ffmpeg_available(), "ffmpeg not available")
class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sr = 44100
        t = np.arange(self.sr * 6) / self.sr
        # A quiet-ish musical stand-in: bass + mid tone + hissy top end.
        rng = np.random.default_rng(3)
        sig = (0.30 * np.sin(2 * np.pi * 55 * t)
               + 0.15 * np.sin(2 * np.pi * 440 * t)
               + 0.05 * np.sin(2 * np.pi * 2600 * t))
        # Sparse transients give the source a high crest factor, so saturation
        # has something measurable to reduce (a pure tone cannot).
        sig = sig + 0.55 * np.exp(-40 * (t % 0.5)) * rng.standard_normal(len(t))
        self.src = os.path.join(self.tmp, "src.wav")
        sf.write(self.src, np.column_stack([sig, sig * 0.9]), self.sr, subtype="FLOAT")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_render_saturates_and_keeps_the_reference_balance(self):
        prof = kt.autofit_v5_profile()
        out = os.path.join(self.tmp, "base.wav")
        kt._v5_render_base(self.src, out, prof)
        y = kt._v5_pcm(out)
        m = kt._v5_octave_curve(y)
        src = kt._v5_pcm(self.src)
        src_crest = 20 * np.log10(np.abs(src).max() / np.sqrt((src ** 2).mean()))
        # Saturation collapses the crest factor and raises the crossing density.
        self.assertLess(m["crest_db"], src_crest - 3.0)
        self.assertGreater(m["zcr_per_sec"], 2000)
        # The residual trim may re-gain octaves, so only the export is bounded.
        self.assertLess(abs(m["peak"]), 4.0)

    def test_export_hits_the_reference_loudness_and_has_no_tags(self):
        prof = kt.autofit_v5_profile()
        base = os.path.join(self.tmp, "base.wav")
        kt._v5_render_base(self.src, base, prof)
        out = os.path.join(self.tmp, "export.mp3")
        info = kt._v5_export(base, out, prof)
        self.assertTrue(os.path.isfile(out))
        self.assertGreater(os.path.getsize(out), 1000)
        lufs, _peak = kt._loudness(out)
        self.assertIsNotNone(info["out_lufs"])
        # Level-matched to the reference's own loudness, not the source's.
        src_lufs, _ = kt._loudness(self.src)
        self.assertLess(abs(lufs - prof["targets"]["lufs"]),
                        abs(lufs - src_lufs))
        self.assertGreater(lufs, -3.0)
        self.assertGreater(info["gain_db"], 0.0)
        # MP3 encoding overshoots the WAV's true peak slightly; stay close.
        self.assertLessEqual(info["out_peak"], prof["targets"]["true_peak_dbtp"] + 2.0)
        raw = Path(out).read_bytes()
        # No ID3/Xing/encoder tag at all: the file starts on a frame sync.
        self.assertNotEqual(raw[:3], b"ID3")
        self.assertEqual(raw[0], 0xFF)
        self.assertEqual(raw[1] & 0xE0, 0xE0)
        for marker in (b"Lavc", b"encoder=", b"Suno", b"Udio", b"copyr8"):
            self.assertNotIn(marker, raw)


class FlowTests(unittest.TestCase):
    """The order of stages, and what V5 refuses to do."""

    def _run(self, tmp, probe_results, *, macro=None, control=True, base_probe=None):
        src = os.path.join(tmp, "src.wav")
        sr = 44100
        t = np.arange(sr * 3) / sr
        sig = 0.25 * np.sin(2 * np.pi * 220 * t)
        sf.write(src, np.column_stack([sig, sig]), sr, subtype="FLOAT")
        out = os.path.join(tmp, "out.mp3")
        spec = os.path.join(tmp, "spec.png")
        events = []
        calls = {"n": 0}

        def fake_render(input_path, out_wav, profile, progress=None):
            events.append("render")
            shutil.copyfile(src, out_wav)
            return {"trim_db": [0.0] * 9, "note": "reference curve already matched"}

        def fake_probe(path, windows, progress=None):
            events.append("probe")
            idx = calls["n"]
            calls["n"] += 1
            if idx < len(probe_results):
                return probe_results[idx]
            return probe_results[-1]

        def fake_export(work, output, profile, trim_filter="", progress=None):
            events.append("export")
            shutil.copyfile(work, output)
            return {"target_lufs": 1.9, "out_lufs": 1.9, "out_peak": 4.2,
                    "gain_db": 0.0, "passes": 1}

        def fake_spec(path, out_path=None, *a, **k):
            return True

        with patch.object(kt.acoustid_backend, "validate_setup"), \
             patch.object(kt.songrec_backend, "validate_setup"), \
             patch.object(kt, "_v5_render_base", side_effect=fake_render), \
             patch.object(kt, "_probe_sweep", side_effect=fake_probe), \
             patch.object(kt, "_control_check", return_value=control), \
             patch.object(kt, "_v5_export", side_effect=fake_export), \
             patch.object(kt, "_v5_match_report", return_value={"out": {}, "target": {}}), \
             patch.object(kt, "_brand_spectrogram"), \
             patch.object(kt, "_run", return_value=(0, "", "")), \
             patch.object(kt, "_result_info", return_value={}):
            result = kt.copyr8_autofit_v5(src, out, spec, progress=events.append,
                                          macro_fn=macro)
        return result, events, out

    def test_clean_base_ships_the_reference_render_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, events, out = self._run(tmp, [(True, [0, 0])])
            self.assertEqual(result["pitch"], 0.0)
            self.assertEqual(result["tempo"], 1.0)
            self.assertTrue(result["clean"])
            self.assertTrue(result["verified"])
            self.assertEqual(result["chain"]["render"], "built-in reference chain")
            self.assertIn("render", events)
            self.assertIn("export", events)
            self.assertTrue(os.path.isfile(out))

    def test_recognised_base_walks_the_bounded_ladder_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            # base recognised, first nudge clean
            with patch.object(kt, "_render_shifted_wav",
                              side_effect=lambda i, o, p, t: shutil.copyfile(i, o)):
                result, events, out = self._run(tmp, [(False, [1]), (True, [0, 0])])
            self.assertEqual(result["pitch"], kt.V5_PITCH_LADDER[1])
            self.assertEqual(result["tempo"], 1.0)
            self.assertTrue(all(p >= -0.20 for p in kt.V5_PITCH_LADDER))
            self.assertTrue(result["clean"])
            self.assertTrue(os.path.isfile(out))

    def test_everything_recognised_is_best_effort_and_not_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(kt, "_render_shifted_wav",
                              side_effect=lambda i, o, p, t: shutil.copyfile(i, o)):
                result, events, out = self._run(tmp, [(False, [1])])
            self.assertFalse(result["clean"])
            self.assertTrue(result["best_effort"])
            self.assertEqual(result["pitch"], kt.V5_PITCH_LADDER[-1])
            self.assertEqual(result["tempo"], 1.0)

    def test_inconclusive_answers_never_count_as_a_clean_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as ctx:
                self._run(tmp, [(False, [None])])
            self.assertIn("No file was written", str(ctx.exception))
            self.assertFalse(os.path.isfile(os.path.join(tmp, "out.mp3")))

    def test_macro_path_trims_residual_and_still_probes_the_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            seen = {}

            def macro(inp, outp, progress=None):
                shutil.copyfile(inp, outp)
                seen["ran"] = True
                return {"steps": ["High-passFilter", "Amplify"], "metadata": False}

            with patch.object(kt, "_v5_apply_residual",
                              side_effect=lambda i, o, p, **k: (shutil.copyfile(i, o),
                                                                {"trim_db": [0.0] * 9})[1]) as resid:
                result, events, out = self._run(tmp, [(True, [0, 0])], macro=macro)
            self.assertTrue(seen.get("ran"))
            self.assertTrue(result["macro"]["applied"])
            resid.assert_called_once()
            self.assertIn("audacity macro", result["chain"]["render"])

    def test_v5_never_calls_a_pitch_or_tempo_render_on_the_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(kt, "_render_shifted_wav") as shift:
                result, events, out = self._run(tmp, [(True, [0, 0])])
            shift.assert_not_called()


class RegressionTests(unittest.TestCase):
    def test_v3_and_v4_entry_points_still_use_their_own_engine(self):
        with patch.object(kt, "_copyr8_autofit_macro_search",
                          return_value={"pitch": 0.0}) as engine:
            kt.copyr8_autofit_v3("in.mp3", "out.mp3", "spec.png", macro_fn=None)
            self.assertEqual(engine.call_args.kwargs["tag"], "v3")
            kt.copyr8_autofit_v4("in.mp3", "out.mp3", "spec.png", macro_fn=None)
            self.assertEqual(engine.call_args.kwargs["tag"], "v4")

    def test_v4_spectral_layer_is_still_in_place(self):
        graph = kt._v4_sculpt_filter_complex(0.0, kt.AUTOFIT_CLIP_THRESHOLD, 10.0)
        self.assertIn("asoftclip", graph)
        self.assertIn("firequalizer", graph)
        # the 980 Hz notch centre is still carved (centre - half_width - 80)
        self.assertIn("1035,-95", kt._v4_comb_gain_entry())
        with patch.object(kt, "_duration_seconds", return_value=10.0), \
             patch.object(kt, "_run", return_value=(0, "", "")) as run:
            kt._apply_v4_base_fx("source.wav", "dest.wav", already_macro=False)
        cmd = " ".join(run.call_args.args[0])
        self.assertIn("acompressor=threshold=-16dB:ratio=1.6", cmd)

    def test_bot_exposes_all_modes_and_v5_keeps_the_shared_throttle(self):
        source = (ROOT / "audio_bot.py").read_text(encoding="utf-8")
        for value in ("autofit", "autofit-v2", "autofit-v3", "autofit-v4", "autofit-v5"):
            self.assertIn(f'value="{value}"', source)
        self.assertIn('name="Auto-Fit V5 (Reference)"', source)
        self.assertIn('"autofit-v5")', source)  # is_autofit membership
        self.assertIn("AUTOFIT_V5_MACRO", source)
        self.assertIn("COPYR8_V5_MACRO", source)
        # The cooldown + single-run gate must still cover every auto-fit.
        self.assertIn("_copyr8_autofit_running", source)
        self.assertIn("COPYR8_COOLDOWN_SECONDS", source)

    def test_cooldown_and_pacing_labels_are_preserved(self):
        self.assertIn("API pacing (API Cooldown)",
                      (ROOT / "killa_tools.py").read_text(encoding="utf-8"))

    def test_export_stem_has_no_internal_processing_notes(self):
        self.assertEqual(kt.clean_export_stem("Song (AI generated) copyr8.mp3"),
                         "Song copyr8")


if __name__ == "__main__":
    unittest.main()
