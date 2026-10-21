from __future__ import annotations

from dataclasses import replace

import numpy as np

from flexload.load import LoadType, S, best_response, c_sigma, fixed_point, named_types, planner
from flexload.metrics import choose, recovery, respond, summary, table
from flexload.system import Dispatch, Market
from flexload.tariff import Marginal, Share, Tariff, named_tariffs, peak_hour


def belief(lam, mu, delta) -> Dispatch:
    """A price-taker's belief with empty pools, so the bill is λᵀd − μᵀσ."""
    T = lam.shape[0]
    z = np.zeros(T)
    return Dispatch(d=delta, sigma=z, u=np.zeros((1, T)), r=np.zeros((1, T)), shed=z, lam=lam, mu=mu, nu=np.zeros((1, T)), eta=z, Pi=z,
                    C_energy=z, C_res=z, C_inv=0.0, d_bid=delta, sigma_bid=z, d_firm=delta, c_sigma=z, y=np.ones(1))


def welfare(theta, market, scenario, x) -> float:
    """S read off a dispatch."""
    return float(S(theta, market, scenario, x.d, x.sigma, x.u, x.r, x.shed, x.y, x.Pi).value)


def energy_only(T) -> Tariff:
    return Tariff(Marginal(np.ones(T)), Share(np.ones(T)), Share(peak_hour(np.arange(T))))


def small_scenario(T, delta):
    from flexload.system import Scenario

    return Scenario(delta, np.full(T, 100.0), np.array([1.0]), np.zeros(1), np.zeros(1), np.ones((1, T)), np.ones(1), np.zeros(1, dtype=int))


def test_best_response_first_order_condition_elastic():
    T, psi = 4, 1.0
    delta, lam = np.full(T, 50.0), np.array([10.0, 20.0, 30.0, 40.0])
    theta = LoadType(psi, 0.5, np.zeros((0, T)), 0.0)
    b = belief(lam, np.zeros(T), delta)
    d, sigma = best_response(theta, energy_only(T), small_scenario(T, delta), b, b)
    assert np.allclose(d, delta - lam / (2 * psi), atol=1e-4)  # max −ψ(d−δ)² − λd → d = δ − λ/2ψ
    assert np.allclose(sigma, 0.0)


def test_best_response_conserves_energy_over_the_period():
    T, psi = 4, 1.0
    delta, lam = np.full(T, 50.0), np.array([10.0, 20.0, 30.0, 40.0])
    theta = LoadType(psi, 0.5, np.ones((1, T)), 0.0)
    b = belief(lam, np.zeros(T), delta)
    d, _ = best_response(theta, energy_only(T), small_scenario(T, delta), b, b)
    assert np.isclose(d.sum(), delta.sum(), atol=1e-4)
    assert np.allclose(d, delta - (lam - lam.mean()) / (2 * psi), atol=1e-4)


def test_tolerance_binds():
    T = 4
    delta, lam = np.full(T, 50.0), np.array([0.0, 0.0, 0.0, 1000.0])
    theta = LoadType(1.0, 0.1, np.zeros((0, T)), 0.0)
    b = belief(lam, np.zeros(T), delta)
    d, _ = best_response(theta, energy_only(T), small_scenario(T, delta), b, b)
    assert np.isclose(d[3], 45.0, atol=1e-4)


def test_reserve_offer_where_price_beats_cost():
    T = 4
    delta = np.full(T, 50.0)
    theta = LoadType(1.0, 0.2, np.zeros((0, T)), 0.05, sells_reserve=True)
    assert np.allclose(c_sigma(theta, delta), 1.0)  # 2 · .05 · 1 · .2 · 50
    mu = np.array([0.0, 0.5, 2.0, 5.0])
    b = belief(np.zeros(T), mu, delta)
    d, sigma = best_response(theta, energy_only(T), small_scenario(T, delta), b, b)
    assert np.allclose(sigma[:2], 0.0, atol=1e-6)  # the offer does not clear there
    assert sigma[3] > sigma[2] > 0.0
    assert np.all(d - sigma >= (1 - theta.beta) * delta - 1e-6)


def test_welfare_ordering_B0_R_B1(pjm, small):
    tau = named_tariffs(small)["tau_0"]
    for name in ("mover", "controllable", "inflexible", "curtailable"):
        theta = named_types(small.T)[name]
        d1, s1 = planner(theta, pjm, small)
        b1 = pjm.clear(small, d1, s1, c_sigma(theta, small.delta), theta.d_firm(small.delta))
        dispatch, b0, _ = respond(theta, tau, pjm, small)
        S_B1, S_R, S_B0 = (welfare(theta, pjm, small, x) for x in (b1, dispatch, b0))
        assert S_B1 >= S_R - 1e-4, name
        assert S_B1 >= S_B0 - 1e-4, name


def test_fixed_point_converges_within_one_merit_order_step(pjm, small):
    theta = named_types(small.T)["mover"]
    d, sigma, dispatch, _, history = fixed_point(theta, named_tariffs(small)["tau_0"], pjm, small)
    assert history[-1] < 1e-3
    assert np.isclose(d.sum(), small.delta.sum(), atol=1e-3)


def test_fixed_point_cycles_when_the_band_straddles_a_step(pjm, small):
    """Hour 3 at 80 + 20 MW: the mover's band [16, 24] crosses the 100 MW base
    unit, λ flips between 20 and 50, and the map has no fixed point (memo, RQ3b)."""
    straddling = replace(small, d_other=small.d_other + np.array([0.0, 0.0, 0.0, 10.0]))
    theta = named_types(small.T)["mover"]
    _, _, _, _, history = fixed_point(theta, named_tariffs(straddling)["tau_0"], pjm, straddling, max_iter=30)
    assert history[-1] > 1e-3


def test_share_on_realized_pools_recovers_exactly(pjm, small):
    theta = named_types(small.T)["mover"]
    realized = Tariff(Marginal(np.ones(small.T)), Share(np.ones(small.T), ex_ante=False), Share(peak_hour(small.d_sys), ex_ante=False))
    dispatch, b0, _ = respond(theta, realized, pjm, small)
    rho = recovery(realized, small, dispatch, b0)
    assert abs(rho["reserve"]) < 1e-6 and abs(rho["investment"]) < 1e-6


def test_summary_row(pjm, small):
    for name in ("mover", "curtailable"):
        theta = named_types(small.T)[name]
        row = summary(theta, named_tariffs(small)["tau_0"], pjm, small)
        assert row["efficiency"] >= -1e-4 and row["tariff"] == "tau_0"


def test_table_and_choice(small):
    market = Market(reserve="ercot", gamma=0.0, C_inv=520_000.0)
    tariffs = named_tariffs(small)
    types = {k: v for k, v in named_types(small.T).items() if k in ("mover", "controllable")}
    t = table(types, tariffs, [market], [small])
    assert t.shape[0] == 2 and (t["efficiency"] >= -1e-4).all()
    assert choose(t) in tariffs and choose(t, g="total", epsilon=1e9) in tariffs


def test_curtailable_planner_is_not_hurt_by_the_instrument(pjm, small):
    tight = replace(small, d_other=small.d_other + np.array([0.0, 0.0, 60.0, 0.0]))
    types = named_types(tight.T)
    cleared = {}
    for name in ("curtailable", "mover"):
        theta = types[name]
        d1, s1 = planner(theta, pjm, tight)
        cleared[name] = welfare(theta, pjm, tight, pjm.clear(tight, d1, s1, c_sigma(theta, tight.delta), theta.d_firm(tight.delta)))
    assert cleared["curtailable"] >= cleared["mover"] - 1e-4
    dispatch, _, _ = respond(types["curtailable"], named_tariffs(tight)["tau_0"], pjm, tight)
    assert cleared["curtailable"] >= welfare(types["curtailable"], pjm, tight, dispatch) - 1e-4
