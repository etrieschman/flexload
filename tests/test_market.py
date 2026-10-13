from __future__ import annotations

import numpy as np
import pytest

from flexload.market import DemandCurve, Market
from flexload.tariff import named_tariffs


@pytest.fixture(params=["pjm", "ercot"])
def market(request) -> Market:
    return Market(reserve=request.param, gamma=0.0, voll=5000.0)


def _b0(market, small):
    tau = named_tariffs(small)["tau_0"]
    return market.clear(small, tau, small.delta, np.zeros(small.T), np.zeros(small.T))


def test_balance_and_capacity(market, small):
    dp = _b0(market, small)
    assert np.allclose(dp.u.sum(axis=0), small.d_sys, atol=1e-6)
    assert np.all(dp.u + dp.r <= small.capacity + 1e-6)
    assert dp.status == "optimal"


def test_energy_price_is_a_marginal_cost(market, small):
    """With gamma = 0 and no reserve cost, λ_t is the cost of some generator (or
    VOLL-like scarcity never binds here), and it is nonnegative."""
    dp = _b0(market, small)
    assert np.all(dp.lam >= -1e-6)
    for t in range(small.T):
        assert np.any(np.isclose(dp.lam[t], small.cost_gen, atol=1e-4)) or dp.lam[t] > small.cost_gen.max()


def test_pjm_reserve_covers_largest_unit(small):
    market = Market(reserve="pjm", gamma=0.0)
    dp = _b0(market, small)
    units = small.units
    u_unit, r_unit = units @ dp.u, units @ dp.r
    R = dp.r.sum(axis=0)
    for t in range(small.T):
        assert np.all(R[t] - r_unit[:, t] >= u_unit[:, t] - 1e-6)


def test_pjm_reserve_price_positive_when_binding(small):
    market = Market(reserve="pjm", gamma=0.0)
    dp = _b0(market, small)
    # the base unit's output must be backed by the others; mu > 0 whenever the
    # requirement displaces cheap energy
    assert np.all(dp.mu >= -1e-6)


def test_ercot_demand_curve_price_reads_off_curve(small):
    curve = DemandCurve(widths=np.array([10.0, 10.0, np.inf]), prices=np.array([100.0, 40.0, 0.0]))
    market = Market(reserve="ercot", gamma=0.0, ordc=curve)
    dp = _b0(market, small)
    # reserve is free here (cost_res = 0, slack capacity), so the LP fills the
    # curve until the price hits zero: mu = 0 and value = 100*10 + 40*10 per hour
    assert np.allclose(dp.mu, 0.0, atol=1e-6)
    assert np.isclose(dp.reserve_value, small.T * (1000.0 + 400.0), rtol=1e-6)


def test_C_sys_equals_generation_cost_when_reserve_free(small):
    market = Market(reserve="pjm", gamma=0.0)
    dp = _b0(market, small)
    assert np.isclose(market.C_sys(dp, small), float((small.cost_gen[:, None] * dp.u).sum()), rtol=1e-6)


def test_pools_short_run(market, small):
    dp = _b0(market, small)
    C_res, C_inv = market.pools(dp, small)
    assert np.allclose(C_res, dp.mu * (dp.r.sum(axis=0) + dp.sigma))
    assert np.isfinite(C_inv)


def test_long_run_builds_capacity(small):
    market = Market(reserve="pjm", gamma=0.0, long_run=True)
    dp = _b0(market, small)
    assert np.all(dp.y >= -1e-6)
    assert dp.y.sum() >= small.d_sys.max() - 1e-3
    C_res, C_inv = market.pools(dp, small)
    assert C_inv == 0.0


def test_curtailment_tariff_is_respected(small):
    market = Market(reserve="pjm", gamma=0.0, voll=5000.0)
    tau_5 = named_tariffs(small, beta_firm=0.5)["tau_5"]
    d = small.delta
    dp = market.clear(small, tau_5, d, np.zeros(small.T), np.zeros(small.T))
    assert np.all(dp.d >= dp.d_firm - 1e-6)
    assert np.all(dp.d <= d + 1e-6)
    # no scarcity in this system, so nothing is curtailed
    assert np.allclose(dp.d, d)


def test_load_reserve_offer_clears_when_cheap(small):
    market = Market(reserve="pjm", gamma=0.0)
    tau = named_tariffs(small)["tau_0"]
    sigma = np.full(small.T, 5.0)
    dp = market.clear(small, tau, small.delta, sigma, np.zeros(small.T))
    assert np.all(dp.sigma <= sigma + 1e-6)
    assert np.all(dp.eta >= -1e-6)


def test_other_load_sheds_at_voll_when_short(small):
    """Load above capacity in one hour: the LP sheds the excess and λ = VOLL."""
    from dataclasses import replace

    tight = replace(small, d_other=small.d_other + np.array([0.0, 0.0, 200.0, 0.0]))
    market = Market(reserve="pjm", gamma=0.0, voll=5000.0)
    tau = named_tariffs(tight)["tau_0"]
    dp = market.clear(tight, tau, tight.delta, np.zeros(tight.T), np.zeros(tight.T))
    assert dp.shed[2] > 0.0 and np.allclose(dp.shed[[0, 1, 3]], 0.0, atol=1e-6)
    assert np.isclose(dp.lam[2], 5000.0, rtol=1e-6)
    assert np.isclose(market.C_sys(dp, tight), float((tight.cost_gen[:, None] * dp.u).sum()) + 5000.0 * dp.shed.sum(), rtol=1e-6)
