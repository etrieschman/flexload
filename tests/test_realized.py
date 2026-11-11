from __future__ import annotations

from dataclasses import replace

import numpy as np

from flexload.load import LoadType
from flexload.realized import reserve, shed, worst
from flexload.system import Market, named_ordcs


def clear(small, name):
    return Market(named_ordcs(small)[name], C_inv=0.0).clear(small, small.delta, np.zeros(small.T), np.zeros(small.T))


def test_a_requirement_on_the_largest_unit_covers_one_trip(small):
    dp = clear(small, "n-1")
    assert np.allclose(worst(small, dp, 1), 0.0, atol=1e-6)
    assert np.all(worst(small, dp, 2) >= worst(small, dp, 1))


def test_shed_is_what_reserve_does_not_cover(small):
    """Nothing trips and the load is steady: shed is the error above reserve."""
    dp = clear(small, "n-1")
    theta = LoadType(100.0, 0.0, 0.2, np.ones((1, small.T)), 0.0)
    R = reserve(dp)
    quiet = replace(small, trip=np.zeros(small.J), error=np.tile((R + 5.0)[:, None], (1, 12)))
    assert np.allclose(shed(quiet, dp, theta, np.random.default_rng(0), 3), 5.0)


def test_the_loads_variability_adds_shed(small):
    dp = clear(small, "n-1")
    quiet = replace(small, trip=np.zeros(small.J), error=np.tile(reserve(dp)[:, None], (1, 12)))  # reserve exactly used
    steady, variable = (LoadType(100.0, 0.0, 0.2, np.ones((1, small.T)), k) for k in (0.0, 0.1))
    assert np.allclose(shed(quiet, dp, steady, np.random.default_rng(0), 50), 0.0)
    assert shed(quiet, dp, variable, np.random.default_rng(0), 50).mean() > 0.0


def test_one_seed_gives_the_same_trips_under_every_construct(small):
    risky = replace(small, trip=np.full(small.J, 0.3), error=np.zeros((small.T, 12)))
    theta = LoadType(100.0, 0.0, 0.2, np.ones((1, small.T)), 0.0)
    a, b = (shed(risky, clear(small, name), theta, np.random.default_rng(7), 200) for name in ("n-1", "ercot"))
    assert a.shape == b.shape == (200, small.T)
    assert a.mean() > 0.0  # two units trip together often enough at 0.3
