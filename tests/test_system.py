from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from flexload.system import HOURS_PER_YEAR, C_inv, Market, ORDC, margin, tighten


def b0(market, small, d_firm=None):
    return market.clear(small, small.delta, np.zeros(small.T), np.zeros(small.T), d_firm)


def test_balance_and_capacity(market, small):
    dp = b0(market, small)
    assert np.allclose(dp.u.sum(axis=0), small.d_sys, atol=1e-6)
    assert np.all(dp.u + dp.r <= small.capacity + 1e-6)
    assert dp.status == "optimal"


def test_energy_price_is_a_marginal_cost(market, small):
    dp = b0(market, small)
    assert np.all(dp.lam >= -1e-6)
    for t in range(small.T):
        assert np.any(np.isclose(dp.lam[t], small.cost_gen, atol=1e-4)) or dp.lam[t] > small.cost_gen.max()


def test_pjm_reserve_covers_largest_unit(pjm, small):
    dp = b0(pjm, small)
    u_unit, r_unit = small.units @ dp.u, small.units @ dp.r
    R = dp.r.sum(axis=0)
    for t in range(small.T):
        assert np.all(R[t] - r_unit[:, t] >= u_unit[:, t] - 1e-6)
    assert np.all(dp.mu >= -1e-6)


def test_ercot_demand_curve_price_reads_off_curve(small):
    curve = ORDC(widths=np.array([10.0, 10.0, np.inf]), prices=np.array([100.0, 40.0, 0.0]))
    market = Market(reserve="ercot", gamma=0.0, ordc=curve, C_inv=0.0)
    dp = b0(market, small)
    # reserve is free (no reserve cost, slack capacity): the LP fills the curve until the price is zero
    assert np.allclose(dp.mu, 0.0, atol=1e-6)
    assert np.isclose(dp.Pi.sum(), small.T * (1000.0 + 400.0), rtol=1e-6)


def test_C_sys_is_generation_cost_when_reserve_free(pjm, small):
    dp = b0(pjm, small)
    assert np.isclose(float(pjm.C_sys(small, dp.u, dp.r, dp.sigma, dp.c_sigma, dp.shed, dp.y, dp.Pi).value), float((small.cost_gen[:, None] * dp.u).sum()), rtol=1e-6)


def test_pools_on_the_dispatch(market, small):
    dp = b0(market, small)
    assert np.allclose(dp.C_res, dp.mu * (dp.r.sum(axis=0) + dp.sigma))
    assert np.isclose(dp.C_inv, market.C_inv * small.T / HOURS_PER_YEAR)


def test_short_run_needs_C_inv(small):
    with pytest.raises(ValueError):
        b0(Market(reserve="pjm", gamma=0.0), small)


def test_long_run_builds_capacity(small):
    market = Market(reserve="pjm", gamma=0.0, long_run=True)
    dp = b0(market, small)
    assert np.all(dp.y >= -1e-6)
    assert dp.y.sum() >= small.d_sys.max() - 1e-3
    assert dp.C_inv == 0.0


def test_firm_level_is_respected(pjm, small):
    d_firm = 0.5 * small.delta
    dp = b0(pjm, small, d_firm)
    assert dp.curtailable
    assert np.all(dp.d >= dp.d_firm - 1e-6) and np.all(dp.d <= small.delta + 1e-6)
    assert np.allclose(dp.d, small.delta)  # no scarcity here, so nothing is curtailed


def test_load_offer_clears_when_cheap(pjm, small):
    sigma = np.full(small.T, 5.0)
    dp = pjm.clear(small, small.delta, sigma, np.zeros(small.T))
    assert np.all(dp.sigma <= sigma + 1e-6)
    assert np.all(dp.eta >= -1e-6)


def test_other_load_sheds_at_voll_when_short(pjm, small):
    tight = replace(small, d_other=small.d_other + np.array([0.0, 0.0, 200.0, 0.0]))
    dp = b0(pjm, tight)
    assert dp.shed[2] > 0.0 and np.allclose(dp.shed[[0, 1, 3]], 0.0, atol=1e-6)
    assert np.isclose(dp.lam[2], 5000.0, rtol=1e-6)
    assert np.isclose(float(pjm.C_sys(tight, dp.u, dp.r, dp.sigma, dp.c_sigma, dp.shed, dp.y, dp.Pi).value), float((tight.cost_gen[:, None] * dp.u).sum()) + 5000.0 * dp.shed.sum(), rtol=1e-6)


def test_C_inv_is_annual_cost_less_rents(pjm, small):
    annual = C_inv(pjm, [small] * 3, cache=False)
    dp = b0(pjm, small)
    profit = float(np.sum((dp.lam - small.cost_gen[:, None]) * dp.u + (dp.mu - small.cost_res[:, None]) * dp.r))
    cost = float(np.sum(small.cost_inv * small.nameplate))
    assert np.isclose(annual, max(cost - 3 * profit * HOURS_PER_YEAR / (3 * small.T), 0.0))


def test_rent_is_on_available_capacity_not_nameplate(pjm, small):
    """A wind column at half its nameplate: its rent is λ on what it produced, not on nameplate,
    and it holds no reserve."""
    windy = replace(
        small,
        capacity=np.vstack([small.capacity, 0.5 * np.full(small.T, 40.0)]),
        nameplate=np.append(small.nameplate, 40.0),
        cost_gen=np.append(small.cost_gen, 0.0),
        cost_res=np.append(small.cost_res, 0.0),
        cost_inv=np.append(small.cost_inv, 100_000.0),
        unit=np.append(small.unit, 3),
        names=(*small.names, "wind"),
    )
    assert windy.renewable.tolist() == [False, False, False, True]
    dp = b0(pjm, windy)
    assert np.allclose(dp.r[3], 0.0, atol=1e-6)
    wind_rent = float(np.sum(dp.lam * dp.u[3]))
    assert np.isclose(float(np.sum(dp.nu[3] * windy.capacity[3])), wind_rent, rtol=1e-6)
    assert wind_rent < float(np.sum(dp.lam * windy.nameplate[3]))
    from flexload.metrics import rent
    assert np.isclose(rent(windy, dp), float(np.sum((dp.lam - windy.cost_gen[:, None]) * dp.u)), rtol=1e-6)


def test_ordc_contingency_is_the_largest_thermal_unit(small):
    windy = replace(
        small,
        capacity=np.vstack([small.capacity, np.full(small.T, 300.0)]),
        nameplate=np.append(small.nameplate, 900.0),
        cost_gen=np.append(small.cost_gen, 0.0),
        cost_res=np.append(small.cost_res, 0.0),
        cost_inv=np.append(small.cost_inv, 100_000.0),
        unit=np.append(small.unit, 3),
        names=(*small.names, "wind"),
    )
    curve = Market(reserve="ercot", C_inv=0.0).ordc_for(windy)
    edges = np.cumsum(curve.widths[:-1])
    assert edges.max() < 100.0 + 5 * windy.epsilon_std  # centred on the 100 MW unit, not the 900 MW wind farm


def test_tighten_sets_the_annual_tightest_hour(small):
    slack = replace(small, d_other=0.5 * small.d_other)
    out = tighten([small, slack], 0.10)
    assert np.isclose(min(margin(s) for s in out), 0.10)
    assert np.isclose(out[0].delta.sum() / out[0].d_sys.sum(), small.delta.sum() / small.d_sys.sum())  # α unchanged
