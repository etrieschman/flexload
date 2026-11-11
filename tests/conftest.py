"""A hand-sized scenario for the tests: three generators, four hours, numbers
you can check on paper. No data download."""

from __future__ import annotations

import numpy as np
import pytest

from flexload.system import Market, Normal, Scenario, named_ordcs

C_INV = 520_000.0  # annual cost of the investment layer, $, arbitrary


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
        error_fit=Normal(0.0, 10.0),  # MW; sets the ERCOT curve
        trip=np.full(3, 0.01),  # each unit trips in 1 hour of 100
        error=np.zeros((T, 12)),  # the realized net-load error: none
    )


@pytest.fixture(params=["n-1", "pjm", "ercot"])
def market(request, small) -> Market:
    return Market(named_ordcs(small)[request.param], C_inv=C_INV)


@pytest.fixture
def n1(small) -> Market:
    """The hard requirement on the largest unit."""
    return Market(named_ordcs(small)["n-1"], C_inv=C_INV)
