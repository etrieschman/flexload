"""A hand-sized scenario for the tests: three generators, four hours, numbers
you can check on paper. No data download."""

from __future__ import annotations

import numpy as np
import pytest

from flexload.scenario import Scenario


@pytest.fixture
def small() -> Scenario:
    T = 4
    delta = np.array([20.0, 20.0, 20.0, 20.0])
    d_other = np.array([60.0, 100.0, 130.0, 80.0])  # d_sys = 80, 120, 150, 100
    cost_gen = np.array([20.0, 50.0, 200.0])
    nameplate = np.array([100.0, 100.0, 60.0])
    return Scenario(
        delta=delta,
        d_other=d_other,
        cost_gen=cost_gen,
        cost_res=np.zeros(3),
        cost_inv=np.array([3000.0, 1500.0, 1000.0]),  # $/MW per week
        capacity=np.repeat(nameplate[:, None], T, axis=1),
        nameplate=nameplate,
        unit=np.array([0, 1, 2]),
        names=("base", "mid", "peaker"),
    )
