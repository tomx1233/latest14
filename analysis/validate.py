"""Render TestSong with V5 and measure it against NewTest.ogg.

Produces analysis/results/TestSong_v5_reference.mp3 (the delivered sound),
analysis/results/compare_*.png figures and analysis/results/summary.json.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common as C
import candidates as K
import killa_tools as kt


def curves(path):
    x = kt._v5_pcm(path)
    m = kt._v5_octave_curve(x)
    return x, m


def main():
    prof = kt.autofit_v5_profile()
    src_wav = os.path.join(C.OUT, "validate_base.wav")
    out_mp3 = os.path.join(C.OUT, "TestSong_v5_reference.mp3")
    out_wav = os.path.join(C.OUT, "validate_out.wav")

    print("rendering the V5 chain over the full track...")
    trim = kt._v5_render_base(C.SRC, src_wav, prof, progress=print)
    print("trim:", trim["note"], [round(d, 2) for d in trim["trim_db"]])
    print("exporting...")
    exp = kt._v5_export(src_wav, out_mp3, prof, progress=print)
    print("export:", exp)

    from scipy.signal import resample_poly
    # decode the mp3 back for measurement at the same rate as the reference
    os.system(f'"{kt._FFMPEG_BIN}" -y -hide_banner -loglevel error -i "{out_mp3}" '
              f'-ac 2 -ar 44100 -c:a pcm_f32le "{out_wav}"')

    src_x = kt._v5_pcm(C.SRC)
    ref_x = kt._v5_pcm(C.REF)
    out_x = kt._v5_pcm(out_wav)
    n = min(len(ref_x), len(out_x))
    ref_x, out_x = ref_x[:n], out_x[:n]

    rows = {}
    for name, x in (("source", src_x), ("reference", ref_x), ("output", out_x)):
        m = kt._v5_octave_curve(x)
        lufs, tp = kt._loudness(C.SRC if name == "source" else
                                (C.REF if name == "reference" else out_mp3))
        m.update(lufs=lufs, true_peak=tp)
        m["band_levels_db"] = [round(float(v), 2) for v in
                               20 * np.log10(np.maximum(K.band_levels(x.mean(1)), 1e-12))]
        rows[name] = m

    # The pre-encode render, so codec overshoot is not mistaken for the render.
    base_x = kt._v5_pcm(src_wav)
    base = kt._v5_octave_curve(base_x)
    base_lufs, base_tp = kt._loudness(src_wav)
    rows["render_wav"] = dict(base, lufs=base_lufs, true_peak=base_tp,
                              note="pre-encode, before the export gain")

    # Control: what MP3 encoding alone does to the reference's own dynamics.
    enc = os.path.join(C.OUT, "ref_roundtrip.mp3")
    import subprocess as sp
    sp.run([kt._FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "error", "-i", C.REF]
           + kt._CLEAN_MP3_FLAGS + ["-c:a", "libmp3lame", "-b:a", "320k", enc], check=True)
    rt = kt._v5_octave_curve(kt._v5_pcm(enc))
    rows["codec_control"] = {
        "note": "NewTest.ogg re-encoded to MP3 320k and decoded again",
        "reference_crest_db": rows["reference"]["crest_db"],
        "reencoded_crest_db": rt["crest_db"],
        "reference_peak": rows["reference"]["peak"],
        "reencoded_peak": rt["peak"],
    }

    delta = np.array(rows["output"]["octave_curve_db"]) - np.array(rows["reference"]["octave_curve_db"])
    rows["output_minus_reference_band_db"] = [round(float(v), 2) for v in delta]
    rows["output_minus_reference_band_rmse_db"] = round(float(np.sqrt((delta ** 2).mean())), 2)

    # waveform/spectrum correlation (honest statement about what can match)
    a, b = rows, None
    from scipy.signal import csd, welch
    def coh(x, y, nperseg=16384):
        f, Cxy = csd(x.mean(1), y.mean(1), 44100, nperseg=nperseg, noverlap=nperseg // 2)
        _, Cxx = welch(x.mean(1), 44100, nperseg=nperseg, noverlap=nperseg // 2)
        _, Cyy = welch(y.mean(1), 44100, nperseg=nperseg, noverlap=nperseg // 2)
        return f, np.abs(Cxy) ** 2 / (Cxx * Cyy + 1e-30)
    f, c_src = coh(src_x[:n], ref_x)
    f, c_out = coh(out_x, ref_x)
    rows["coherence"] = {
        "source_vs_reference_lo": round(float(np.median(c_src[(f > 40) & (f < 400)])), 3),
        "output_vs_reference_lo": round(float(np.median(c_out[(f > 40) & (f < 400)])), 3),
        "source_vs_reference_hi": round(float(np.median(c_src[(f > 1000) & (f < 16000)])), 4),
        "output_vs_reference_hi": round(float(np.median(c_out[(f > 1000) & (f < 16000)])), 4),
    }

    with open(os.path.join(C.OUT, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)

    # ---- figures: identical settings for both files ------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.signal import spectrogram

    def plot_spec(ax, x, title):
        f_, t_, S = spectrogram(x.mean(1), 44100, nperseg=4096, noverlap=2048, mode="magnitude")
        S = 20 * np.log10(np.maximum(S, 1e-7))
        ax.pcolormesh(t_, f_, S, vmin=-110, vmax=-20, shading="auto")
        ax.set_ylim(0, 16000)
        ax.set_title(title)
        ax.set_ylabel("Hz")

    fig, ax = plt.subplots(2, 1, figsize=(16, 9), sharex=True, sharey=True)
    plot_spec(ax[0], ref_x, "NewTest.ogg (reference)")
    plot_spec(ax[1], out_x, "TestSong -> V5 render (output)")
    ax[1].set_xlabel("time (s)")
    plt.tight_layout()
    plt.savefig(os.path.join(C.OUT, "compare_spec.png"), dpi=100)
    plt.close()

    fig, ax = plt.subplots(3, 1, figsize=(16, 9), sharex=True)
    for a_, (name, x) in zip(ax, (("TestSong.ogg", src_x), ("NewTest.ogg", ref_x),
                                  ("V5 output", out_x))):
        env = np.abs(x).max(1)
        h = 441
        k = len(env) // h
        a_.plot(np.arange(k) / 100.0, 20 * np.log10(np.maximum(
            env[:k * h].reshape(k, h).max(1), 1e-6)), lw=0.4, color="k")
        a_.set_ylabel(name)
        a_.set_ylim(-60, 8)
        a_.grid(alpha=.3)
    ax[-1].set_xlabel("time (s)")
    plt.tight_layout()
    plt.savefig(os.path.join(C.OUT, "compare_wave.png"), dpi=100)
    plt.close()

    fig, ax = plt.subplots(figsize=(14, 6))
    fa, la = C.ltas(src_x.mean(1), 44100, n_fft=16384, hop=8192)
    _, lb = C.ltas(ref_x.mean(1), 44100, n_fft=16384, hop=8192)
    _, lo = C.ltas(out_x.mean(1), 44100, n_fft=16384, hop=8192)
    for lab, y, style in (("TestSong", la, ":"), ("NewTest (ref)", lb, "-"),
                          ("V5 output", lo, "--")):
        ax.semilogx(fa, y - np.median(y[(fa > 200) & (fa < 2000)]), style, label=lab)
    ax.set_xlim(30, 20000)
    ax.set_xlabel("Hz")
    ax.set_ylabel("dB (level-matched at 200-2000 Hz)")
    ax.grid(alpha=.3)
    ax.legend()
    ax.set_title("Long-term average spectra")
    plt.tight_layout()
    plt.savefig(os.path.join(C.OUT, "compare_ltas.png"), dpi=100)
    plt.close()

    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
