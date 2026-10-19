"""A hand-sized scenario for the tests: three generators, four hours, numbers
you can check on paper. No data download."""

from __future__ import annotations

import numpy as np
import pytest

from flexload.system import Market, Scenario

MISSING_MONEY = 520_000.0  # annual $, arbitrary


@pytest.fixture
def small() -> Scenario:
    T = 4
    nameplate = np.array([100.0, 100.0, 60.0])
    return Scenario(
        delta=np.array([20.0, 20.0, 20.0, 20.0]),
        d_other=np.array([60.0, 100.0, 130.0, 70.0]),  # d_sys = 80, 120, 150, 90; the mover's band never crosses the 100 MW step
        cost_gen=np.array([20.0, 50.0, 200.0]),
        cost_res=np.zeros(3),
        cost_inv=np.array([156_000.0, 78_000.0, 52_000.0]),  # $/MW per year
        capacity=np.repeat(nameplate[:, None], T, axis=1),
        nameplate=nameplate,
        unit=np.array([0, 1, 2]),
        names=("base", "mid", "peaker"),
    )


@pytest.fixture(params=["pjm", "ercot"])
def market(request) -> Market:
    return Market(reserve=request.param, gamma=0.0, voll=5000.0, missing_money=MISSING_MONEY)


@pytest.fixture
def pjm() -> Market:
    return Market(reserve="pjm", gamma=0.0, voll=5000.0, missing_money=MISSING_MONEY)
