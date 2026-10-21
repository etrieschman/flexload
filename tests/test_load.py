from __future__ import annotations

from dataclasses import replace

import numpy as np

from flexload.load import LoadType, best_response, c_sigma, fixed_point, named_types, planner, blocks
from flexload.metrics import S, choose, recovery, respond, summary, table
from flexload.system import Dispatch, Market
from flexload.tariff import Tariff, all_hours, named_tariffs, peak_hour, share


def belief(lam, mu, delta) -> Dispatch:
    """A price-taker's belief with empty pools, so the bill is λᵀd − μᵀσ."""
    T = lam.shape[0]
    z = np.zeros(T)
    return Dispatch(d=delta, sigma=z, u=np.zeros((1, T)), r=np.zeros((1, T)), shed=z, lam=lam, mu=mu, nu=np.zeros((1, T)), eta=z, Pi=z,
                    C_energy=z, C_res=z, C_inv=0.0, d_bid=delta, sigma_bid=z, d_firm=delta, c_sigma=z, y=np.ones(1))


def energy_only(T) -> Tariff:
    return Tariff(share(all_hours(T)), share(peak_hour(np.arange(T))))


def small_scenario(T, delta):
    from flexload.system import Scenario

    return Scenario(delta, np.full(T, 100.0), np.array([1.0]), np.zeros(1), np.zeros(1), np.ones((1, T)), np.ones(1), np.zeros(1, dtype=int))


def test_best_response_first_order_condition_elastic():
    T, psi = 4, 1.0
    delta, lam = np.full(T, 50.0), np.array([10.0, 20.0, 30.0, 40.0])
    theta = LoadType(psi, 0.5, blocks(T, None), 0.0)
    d, sigma = best_response(theta, energy_only(T), small_scenario(T, delta), belief(lam, np.zeros(T), delta))
    assert np.allclose(d, delta - lam / (2 * psi), atol=1e-4)  # max −ψ(d−δ)² − λd → d = δ − λ/2ψ
    assert np.allclose(sigma, 0.0)


def test_best_response_conserves_energy_over_the_period():
    T, psi = 4, 1.0
    delta, lam = np.full(T, 50.0), np.array([10.0, 20.0, 30.0, 40.0])
    theta = LoadType(psi, 0.5, blocks(T, T), 0.0)
    d, _ = best_response(theta, energy_only(T), small_scenario(T, delta), belief(lam, np.zeros(T), delta))
    assert np.isclose(d.sum(), delta.sum(), atol=1e-4)
    assert np.allclose(d, delta - (lam - lam.mean()) / (2 * psi), atol=1e-4)


def test_tolerance_binds():
    T = 4
    delta, lam = np.full(T, 50.0), np.array([0.0, 0.0, 0.0, 1000.0])
    theta = LoadType(1.0, 0.1, blocks(T, None), 0.0)
    d, _ = best_response(theta, energy_only(T), small_scenario(T, delta), belief(lam, np.zeros(T), delta))
    assert np.isclose(d[3], 45.0, atol=1e-4)


def test_reserve_offer_where_price_beats_cost():
    T = 4
    delta = np.full(T, 50.0)
    theta = LoadType(1.0, 0.2, blocks(T, None), 0.05, sells_reserve=True)
    assert np.allclose(c_sigma(theta, delta), 1.0)  # 2 · .05 · 1 · .2 · 50
    mu = np.array([0.0, 0.5, 2.0, 5.0])
    d, sigma = best_response(theta, energy_only(T), small_scenario(T, delta), belief(np.zeros(T), mu, delta))
    assert np.allclose(sigma[:2], 0.0, atol=1e-6)  # the offer does not clear there
    assert sigma[3] > sigma[2] > 0.0
    assert np.all(d - sigma >= (1 - theta.beta) * delta - 1e-6)


def test_welfare_ordering_B0_R_B1(pjm, small):
    tau = named_tariffs(small)["tau_0"]
    for name in ("mover", "controllable", "inflexible", "curtailable"):
        theta = named_types(small.T)[name]
        d1, s1, S_star = planner(theta, pjm, small)
        b1 = pjm.clear(small, d1, s1, c_sigma(theta, small.delta), theta.d_firm(small.delta))
        dispatch, ex_ante, _, _ = respond(theta, tau, pjm, small)
        assert S_star >= S(theta, pjm, small, dispatch) - 1e-4, name
        assert S_star >= S(theta, pjm, small, ex_ante) - 1e-4, name
        assert np.isclose(S_star, S(theta, pjm, small, b1), rtol=1e-4), name  # B1 re-cleared reproduces S*


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
    realized = Tariff(share(all_hours(small.T), ex_ante=False), share(peak_hour(small.d_sys), ex_ante=False))
    dispatch, ex_ante, _, _ = respond(theta, realized, pjm, small)
    rho = recovery(realized, small, dispatch, ex_ante)
    assert abs(rho["reserve"]) < 1e-6 and abs(rho["investment"]) < 1e-6


def test_menu_election_and_summary(pjm, small):
    tau_5 = named_tariffs(small)["tau_5"]
    for name in ("mover", "curtailable"):
        theta = named_types(small.T)[name]
        _, _, _, elected = respond(theta, tau_5, pjm, small)
        assert elected.name in ("tau_0", "tau_5_curtailable")
        row = summary(theta, tau_5, pjm, small)
        assert row["efficiency"] >= -1e-4


def test_table_and_choice(small):
    market = Market(reserve="ercot", gamma=0.0, C_inv=520_000.0)
    tariffs = {k: v for k, v in named_tariffs(small).items() if k in ("tau_0", "tau_2", "tau_4")}
    types = {k: v for k, v in named_types(small.T).items() if k in ("mover", "controllable")}
    t = table(types, tariffs, [market], [small])
    assert t.shape[0] == 6 and (t["efficiency"] >= -1e-4).all()
    assert choose(t) in tariffs and choose(t, g="total", epsilon=1e9) in tariffs


def test_curtailable_planner_is_not_hurt_by_the_instrument(pjm, small):
    tight = replace(small, d_other=small.d_other + np.array([0.0, 0.0, 60.0, 0.0]))
    types = named_types(tight.T)
    S_curtailable = planner(types["curtailable"], pjm, tight)[2]
    S_mover = planner(types["mover"], pjm, tight)[2]
    assert S_curtailable >= S_mover - 1e-4
    dispatch, _, _, _ = respond(types["curtailable"], named_tariffs(tight)["tau_0"], pjm, tight)
    assert S_curtailable >= S(types["curtailable"], pjm, tight, dispatch) - 1e-4
