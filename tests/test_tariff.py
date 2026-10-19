"""The bill on numbers you can check by hand. A ``Dispatch`` is built directly
from prices and pools; the clearing is not involved."""

from __future__ import annotations

import numpy as np

from flexload.system import Dispatch
from flexload.tariff import Tariff, all_hours, peak_hour, share, two_part

T = 4
d = np.array([10.0, 20.0, 30.0, 20.0])
d_other = np.array([85.0, 80.0, 75.0, 80.0])  # peak of d + d_other at hour 2
sigma = np.array([0.0, 2.0, 3.0, 0.0])
lam = np.array([20.0, 50.0, 200.0, 50.0])
mu = np.array([0.0, 5.0, 40.0, 5.0])
C_res = np.array([0.0, 500.0, 4000.0, 500.0])
C_inv = 10_000.0
peak = peak_hour(d + d_other)  # hour 2


def dispatch(d_realized=d, d_firm=None) -> Dispatch:
    z = np.zeros(T)
    return Dispatch(d=d_realized, sigma=sigma, u=np.zeros((1, T)), r=np.zeros((1, T)), shed=z, lam=lam, mu=mu, nu=np.zeros((1, T)),
                    eta=z, C_res=C_res, C_inv=C_inv, d_bid=d_realized, sigma_bid=sigma, d_firm=d_realized if d_firm is None else d_firm,
                    c_s=z, y=np.ones(1))


def values(bill) -> dict[str, float]:
    return {k: float(v.value) for k, v in bill.items()}


def test_energy_settles_at_lambda():
    tau = Tariff(share(all_hours(T)), share(peak))
    assert np.isclose(values(tau.bill(d, sigma, dispatch(), d_other))["energy"], lam @ d)


def test_share_splits_the_pool_by_base():
    tau = Tariff(share(all_hours(T)), share(peak))
    own = values(tau.bill(d, sigma, dispatch(), d_other))
    others = values(tau.bill(d_other, np.zeros(T), dispatch(), d, own=False))
    assert np.isclose(own["reserve"] + others["reserve"], C_res.sum())
    assert np.isclose(own["investment"] + others["investment"], C_inv)
    assert np.isclose(own["investment"], C_inv * d[2] / (d[2] + d_other[2]))


def test_two_part_collects_the_pool():
    tau = Tariff(two_part(all_hours(T), phi=0.03), two_part(peak, phi=0.0))
    own = values(tau.bill(d, sigma, dispatch(), d_other))
    others = values(tau.bill(d_other, np.zeros(T), dispatch(), d, own=False))
    assert np.isclose(own["reserve"] + others["reserve"], C_res.sum())
    assert np.isclose(own["investment"] + others["investment"], C_inv)
    assert np.isclose(own["investment"], C_inv * d[2] / (d[2] + d_other[2]))  # lump sum apportioned by share of base


def test_two_part_lump_sum_can_be_given():
    tau = Tariff(two_part(all_hours(T), phi=0.0, T=123.0), share(peak))
    assert np.isclose(values(tau.bill(d, sigma, dispatch(), d_other))["reserve"], 123.0)


def test_rate_taker_bill_is_linear_in_d_and_exact_at_d_hat():
    tau = Tariff(share(all_hours(T)), share(peak))
    x = d + np.array([1.0, -2.0, 3.0, -2.0])
    at_rate = values(tau.bill(x, sigma, dispatch(), d_other, d_hat=d))
    rate_res, rate_inv = C_res / (d + d_other), C_inv / (d[2] + d_other[2])
    assert np.isclose(at_rate["reserve"], rate_res @ x) and np.isclose(at_rate["investment"], rate_inv * x[2])
    assert np.isclose(values(tau.bill(d, sigma, dispatch(), d_other))["reserve"], rate_res @ d)


def test_marginal_charge_matches_the_derivative():
    tau = Tariff(share(all_hours(T)), share(peak))
    m = tau.marginal(d, dispatch(), d_other)
    assert np.allclose(m["energy"], lam)
    assert np.allclose(m["reserve"], C_res * d_other / (d + d_other) ** 2)
    expect_inv = np.zeros(T)
    expect_inv[2] = C_inv * d_other[2] / (d[2] + d_other[2]) ** 2
    assert np.allclose(m["investment"], expect_inv)
    tau2 = Tariff(two_part(all_hours(T), phi=0.03), share(peak))
    assert np.allclose(tau2.marginal(d, dispatch(), d_other)["reserve"], 0.03 * mu)


def test_reserve_payment_is_a_credit():
    tau = Tariff(share(all_hours(T)), share(peak))
    assert np.isclose(values(tau.bill(d, sigma, dispatch(), d_other))["credit"], -(mu @ sigma))


def test_exemption_applies_to_a_curtailable_load_only():
    tau = Tariff(share(all_hours(T)), share(peak), exempt_curtailable=True)
    curtailable = dispatch(d_firm=0.8 * d)
    assert values(tau.bill(d, sigma, curtailable, d_other))["reserve"] == 0.0
    assert values(tau.bill(d_other, np.zeros(T), curtailable, d, own=False))["reserve"] > 0.0
    assert values(tau.bill(d, sigma, dispatch(), d_other))["reserve"] > 0.0
