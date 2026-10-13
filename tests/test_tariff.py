from __future__ import annotations

import cvxpy as cp
import numpy as np

from flexload.tariff import Menu, Tariff, firm, hourly, marginal, named_tariffs, peak_hour, share, total, two_part

T = 4
d = np.array([18.0, 22.0, 20.0, 21.0])
d_other = np.array([60.0, 100.0, 130.0, 80.0])
lam = np.array([20.0, 50.0, 200.0, 50.0])
mu = np.array([0.0, 5.0, 30.0, 5.0])
sigma = np.zeros(T)
C_res = mu * 50.0
C_inv = 10_000.0
peak = peak_hour(d + d_other)


def _tau(reserve, investment, curtail=None):
    return Tariff(marginal(), reserve, investment, curtail)


def test_energy_is_marginal():
    tau = _tau(share(hourly(T)), share(peak))
    assert np.isclose(tau.bill(d, sigma, lam, mu, C_res, C_inv, d_other)["energy"], lam @ d)


def test_share_recovers_pool_exactly():
    tau = _tau(share(hourly(T)), share(peak))
    own = tau.bill(d, sigma, lam, mu, C_res, C_inv, d_other)
    others = tau.bill(d_other, sigma, lam, mu, C_res, C_inv, d, own=False)
    assert np.isclose(own["reserve"] + others["reserve"], C_res.sum())
    assert np.isclose(own["investment"] + others["investment"], C_inv)
    # by hand: reserve share each hour is d_t / (d_t + d_other_t)
    assert np.isclose(own["reserve"], np.sum(C_res * d / (d + d_other)))
    assert np.isclose(own["investment"], C_inv * d[2] / (d[2] + d_other[2]))


def test_two_part_recovers_pool_at_expected_base():
    tau = _tau(two_part(hourly(T), phi=0.03), two_part(peak, phi=0.0))
    own = tau.bill(d, sigma, lam, mu, C_res, C_inv, d_other)
    others = tau.bill(d_other, sigma, lam, mu, C_res, C_inv, d, own=False)
    assert np.isclose(own["reserve"] + others["reserve"], C_res.sum())
    assert np.isclose(own["investment"] + others["investment"], C_inv)
    # the investment layer is all lump sum: the load's share of δ-like base
    assert np.isclose(own["investment"], C_inv * d[2] / (d[2] + d_other[2]))


def test_two_part_explicit_lump_sum():
    tau = _tau(two_part(hourly(T), phi=0.0, T=123.0), share(peak))
    assert np.isclose(tau.bill(d, sigma, lam, mu, C_res, C_inv, d_other)["reserve"], 123.0)


def test_rate_taker_is_linear_in_d():
    tau = _tau(share(hourly(T)), share(peak))
    x = cp.Variable(T)
    bill = tau.bill(x, sigma, lam, mu, C_res, C_inv, d_other, d_hat=d)
    assert total(bill).is_affine()
    x.value = d
    # at x = d_hat the linearized bill equals the exact bill
    exact = tau.bill(d, sigma, lam, mu, C_res, C_inv, d_other)
    assert np.isclose(total(bill).value, total(exact))


def test_marginal_charges():
    tau = _tau(share(hourly(T)), share(peak))
    m = tau.marginal(d, sigma, lam, mu, C_res, C_inv, d_other)
    assert np.allclose(m["energy"], lam)
    assert np.allclose(m["reserve"], C_res * d_other / (d + d_other) ** 2)
    expect_inv = np.zeros(T)
    expect_inv[2] = C_inv * d_other[2] / (d[2] + d_other[2]) ** 2
    assert np.allclose(m["investment"], expect_inv)
    tau2 = _tau(two_part(hourly(T), phi=0.03), two_part(peak))
    assert np.allclose(tau2.marginal(d, sigma, lam, mu, C_res, C_inv, d_other)["reserve"], 0.03 * mu)


def test_credit_is_reserve_payment():
    tau = _tau(share(hourly(T)), share(peak))
    s = np.array([1.0, 2.0, 3.0, 4.0])
    assert np.isclose(tau.bill(d, s, lam, mu, C_res, C_inv, d_other)["credit"], -(mu @ s))


def test_firm_level_and_exemption():
    delta = np.full(T, 20.0)
    hours = np.array([False, False, True, False])
    tau = _tau(share(hourly(T)), share(peak), firm(0.5, hours, exempt_reserve=True))
    d_firm = tau.d_firm(delta, d)
    assert np.allclose(d_firm, [18.0, 22.0, 10.0, 21.0])
    assert tau.bill(d, sigma, lam, mu, C_res, C_inv, d_other)["reserve"] == 0.0
    assert tau.bill(d_other, sigma, lam, mu, C_res, C_inv, d, own=False)["reserve"] > 0.0


def test_with_window_and_menu(small):
    tariffs = named_tariffs(small)
    assert set(tariffs) == {f"tau_{i}" for i in range(7)}
    assert isinstance(tariffs["tau_6"], Menu) and len(tariffs["tau_6"].options) == 2
    w = np.ones(small.T) / small.T
    believed = tariffs["tau_0"].with_window("investment", w)
    assert np.allclose(believed.investment.w, w) and np.allclose(tariffs["tau_0"].investment.w.sum(), 1.0)
