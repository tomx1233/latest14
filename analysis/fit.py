"""Differential-evolution fit of the V5 chain to the measured reference profile."""
import numpy as np
import common as C
import candidates as K
import opt as O
from scipy.signal import butter, sosfilt
from scipy.optimize import differential_evolution

SR = 44100


def render_full(x, hp_fc, lo_fc, lo_db, pre_fc, pre_db, drive, kind, post_fc, post_db, post_lo_db,
                post_hp_fc=0.0):
    y = O.hp(x, hp_fc)
    if lo_db:
        y = O.fft_shelf(y, lo_fc, lo_db, kind="low")
    if pre_db:
        y = O.fft_shelf(y, pre_fc, pre_db, kind="high")
    y = y / max(np.abs(y).max(), 1e-9)
    d = O.sat(y, kind, drive)
    if post_db:
        d = O.fft_shelf(d, post_fc, post_db, kind="high")
    if post_lo_db:
        d = O.fft_shelf(d, lo_fc, post_lo_db, kind="low")
    if post_hp_fc:
        d = O.hp(d, post_hp_fc)
    return d / max(np.abs(d).max(), 1e-9)


def objective(params, x, ref):
    hp_fc, lo_fc, lo_db, pre_fc, pre_db, drive, kind, post_fc, post_db, post_lo_db = params
    kind = ["hard", "tanh", "atan"][int(np.clip(kind, 0, 2.999))]
    z = render_full(x, hp_fc, lo_fc, lo_db, pre_fc, pre_db, drive, kind, post_fc, post_db, post_lo_db)
    return O.score(z, ref)["score"]


def fit(x, ref, seed=0, maxiter=40, popsize=18):
    bounds = [(0, 80), (60, 220), (0, 18), (700, 6000), (0, 30),
              (1, 200), (0, 2.999), (700, 9000), (-24, 2), (0, 2400)]
    res = differential_evolution(
        objective, bounds, args=(x, ref), seed=seed, maxiter=maxiter,
        popsize=popsize, polish=False, tol=0.01, init="sobol", workers=1)
    return res
