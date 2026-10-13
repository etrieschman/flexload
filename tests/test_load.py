from __future__ import annotations

import numpy as np
import pytest

from flexload.load import LoadType, V, best_response, c_s, fixed_point, named_types, planner, windows_elastic, windows_weekly
from flexload.market import Market
from flexload.metrics import S, recovery, summary
from flexload.operator import evaluate, respond
from flexload.tariff import Tariff, hourly, marginal, named_tariffs, peak_hour, share, two_part


def _flat(T):
    """Energy only: zero pools, so the bill is λᵀd."""
    return Tariff(marginal(), share(hourly(T)), share(peak_hour(np.arange(T))))


def test_best_response_first_order_condition_elastic():
    T, psi = 4, 1.0
    delta = np.full(T, 50.0)
    lam = np.array([10.0, 20.0, 30.0, 40.0])
    theta = LoadType(psi, 0.5, windows_elastic(T), 0.0)
    d, sigma = best_response(theta, _flat(T), delta, lam, np.zeros(T), np.zeros(T), 0.0, np.full(T, 100.0))
    # max -psi (d-δ)² - λ d  ->  d = δ - λ / (2 psi)
    assert np.allclose(d, delta - lam / (2 * psi), atol=1e-4)
    assert np.allclose(sigma, 0.0)


def test_best_response_conserves_weekly_energy():
    T, psi = 4, 1.0
    delta = np.full(T, 50.0)
    lam = np.array([10.0, 20.0, 30.0, 40.0])
    theta = LoadType(psi, 0.5, windows_weekly(T), 0.0)
    d, _ = best_response(theta, _flat(T), delta, lam, np.zeros(T), np.zeros(T), 0.0, np.full(T, 100.0))
    assert np.isclose(d.sum(), delta.sum(), atol=1e-4)
    assert np.allclose(d, delta - (lam - lam.mean()) / (2 * psi), atol=1e-4)


def test_tolerance_binds():
    T = 4
    delta = np.full(T, 50.0)
    lam = np.array([0.0, 0.0, 0.0, 1000.0])
    theta = LoadType(1.0, 0.1, windows_elastic(T), 0.0)
    d, _ = best_response(theta, _flat(T), delta, lam, np.zeros(T), np.zeros(T), 0.0, np.full(T, 100.0))
    assert np.isclose(d[3], 45.0, atol=1e-4)


def test_reserve_offer_where_price_beats_cost():
    T = 4
    delta = np.full(T, 50.0)
    theta = LoadType(1.0, 0.2, windows_elastic(T), 0.05, sells_reserve=True)
    cs = c_s(theta, delta)  # 2 * .05 * 1 * .2 * 50 = 1.0
    assert np.allclose(cs, 1.0)
    mu = np.array([0.0, 0.5, 2.0, 5.0])
    d, sigma = best_response(theta, _flat(T), delta, np.zeros(T), mu, np.zeros(T), 0.0, np.full(T, 100.0))
    assert np.allclose(sigma[:2], 0.0, atol=1e-6)  # offer does not clear, nothing to gain
    assert sigma[3] > sigma[2] > 0.0
    assert np.all(d - sigma >= (1 - theta.beta) * delta - 1e-6)


def test_B0_is_feasible_and_welfare_ordering(small):
    market = Market(reserve="pjm", gamma=0.0)
    tariffs = named_tariffs(small)
    for name in ("mover", "clr", "inflexible"):
        theta = named_types(small.T)[name]
        d1, s1, S_star = planner(theta, market, small)
        b1 = market.clear(small, None, d1, s1, c_s(theta, small.delta))
        d, sigma, dispatch, ex_ante, _ = respond(theta, tariffs["tau_0"], market, small)
        S_R, S_B0, S_B1 = S(theta, market, small, dispatch), S(theta, market, small, ex_ante), S(theta, market, small, b1)
        assert S_star >= S_R - 1e-4, (name, S_star, S_R)
        assert S_star >= S_B0 - 1e-4
        assert np.isclose(S_star, S_B1, rtol=1e-4), (name, S_star, S_B1)  # B1 re-cleared reproduces S*


def test_fixed_point_converges(small):
    market = Market(reserve="pjm", gamma=0.0)
    theta = named_types(small.T)["mover"]
    d, sigma, dispatch, history = fixed_point(theta, named_tariffs(small)["tau_0"], market, small)
    assert history[-1] < 1e-3
    assert np.isclose(d.sum(), small.delta.sum(), atol=1e-3)


def test_share_recovery_is_zero_by_construction(small):
    market = Market(reserve="pjm", gamma=0.0)
    theta = named_types(small.T)["mover"]
    T = small.T
    realized = Tariff(marginal(), share(hourly(T), ex_ante=False), share(peak_hour(small.d_sys), ex_ante=False))
    d, sigma, dispatch, ex_ante, _ = respond(theta, realized, market, small)
    rho = recovery(realized, market, small, dispatch, ex_ante)
    assert abs(rho["reserve"]) < 1e-6 and abs(rho["investment"]) < 1e-6
    # tau_1 keeps the ex-ante investment basis, so its investment recovery is the
    # ex-ante pool's miss and is not zero in general
    tau_1 = named_tariffs(small)["tau_1"]
    d, sigma, dispatch, ex_ante, _ = respond(theta, tau_1, market, small)
    rho_1 = recovery(tau_1, market, small, dispatch, ex_ante)
    assert abs(rho_1["reserve"]) < 1e-6


def test_menu_election_and_summary(small):
    market = Market(reserve="pjm", gamma=0.0)
    theta = named_types(small.T)["mover"]
    tau_6 = named_tariffs(small)["tau_6"]
    d, sigma, dispatch, ex_ante, elected = respond(theta, tau_6, market, small)
    assert elected.name in ("tau_0", "tau_6b")
    d1, s1, S_star = planner(theta, market, small)
    b1 = market.clear(small, None, d1, s1, c_s(theta, small.delta))
    row = summary(theta, tau_6, market, small, dispatch, b1, S_star, ex_ante, elected)
    assert row.shape[0] == 1 and row["regret"][0] >= -1e-4


def test_evaluate_table(small):
    market = Market(reserve="ercot", gamma=0.0)
    tariffs = {k: v for k, v in named_tariffs(small).items() if k in ("tau_0", "tau_2", "tau_4")}
    types = {k: v for k, v in named_types(small.T).items() if k in ("mover", "clr")}
    table = evaluate(tariffs, types, market, [small])
    assert table.shape[0] == 6
    assert (table["regret"] >= -1e-4).all()
