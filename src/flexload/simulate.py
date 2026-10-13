"""The repeated game across weeks, with the load learning.

Weeks are independent given ω, so the only state that carries across them is
the load's belief: the constants its QP takes as given. A :class:`Learner`
updates that belief from what the load observed; :class:`Static` never does,
which makes the one-shot game a special case of the same loop.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

import numpy as np
import polars as pl

from .load import LoadType, best_response, c_s
from .market import Dispatch, Market
from .metrics import S, pools_for, settle
from .scenario import Scenario
from .tariff import Menu, Tariff, peak_hour, total


@dataclass(frozen=True)
class Belief:
    """What a price-taker takes as given: λ̄, μ̄, the pools, the consumption its
    rate is set at, and its belief about the peak hour as a probability vector
    (``None``: it uses the tariff's window as announced)."""

    lam: np.ndarray
    mu: np.ndarray
    C_res: np.ndarray
    C_inv: float
    d_hat: np.ndarray
    w_peak: np.ndarray | None = None

    @classmethod
    def announced(cls, market: Market, scenario: Scenario, tariff, theta: LoadType) -> "Belief":
        """The exogenous price-taker's belief: the clearing at (δ, 0)."""
        tau = tariff.options[0] if isinstance(tariff, Menu) else tariff
        dispatch = market.clear(scenario, tau, scenario.delta, np.zeros(scenario.T), c_s(theta, scenario.delta))
        C_res, C_inv = market.pools(dispatch, scenario)
        return cls(dispatch.lam, dispatch.mu, C_res, C_inv, scenario.delta.copy())


@dataclass(frozen=True)
class Observation:
    """What the load sees after a week."""

    dispatch: Dispatch
    C_res: np.ndarray
    C_inv: float
    peak: int | None  # the realized peak hour, if revealed


class Learner(Protocol):
    def update(self, belief: Belief, observation: Observation) -> Belief: ...


@dataclass(frozen=True)
class Static:
    def update(self, belief: Belief, observation: Observation) -> Belief:
        return belief


@dataclass(frozen=True)
class PriceAveraging:
    """Exponential averaging of hour-of-week prices, pools and own consumption."""

    eta: float = 0.3

    def update(self, belief: Belief, observation: Observation) -> Belief:
        e, dp = self.eta, observation.dispatch
        return replace(
            belief,
            lam=(1 - e) * belief.lam + e * dp.lam,
            mu=(1 - e) * belief.mu + e * dp.mu,
            C_res=(1 - e) * belief.C_res + e * observation.C_res,
            C_inv=(1 - e) * belief.C_inv + e * observation.C_inv,
            d_hat=(1 - e) * belief.d_hat + e * dp.d,
        )


@dataclass(frozen=True)
class PeakCounts:
    """Empirical distribution of the revealed peak hour; a prior of ``strength``
    pseudo-counts on the announced window."""

    strength: float = 1.0

    def update(self, belief: Belief, observation: Observation) -> Belief:
        if observation.peak is None:
            return belief
        T = belief.lam.shape[0]
        counts = self.strength * (belief.w_peak if belief.w_peak is not None else np.ones(T) / T) * T
        counts = counts.copy()
        counts[observation.peak] += 1.0
        return replace(belief, w_peak=counts / counts.sum())


@dataclass(frozen=True)
class Combined:
    learners: tuple[Learner, ...]

    def update(self, belief: Belief, observation: Observation) -> Belief:
        for learner in self.learners:
            belief = learner.update(belief, observation)
        return belief


def simulate(
    theta: LoadType,
    tariff: Tariff | Menu,
    market: Market,
    scenarios: list[Scenario],
    learner: Learner = Static(),
    belief: Belief | None = None,
    reveal_peak: bool = True,
    ex_post_peak: bool = False,
) -> tuple[pl.DataFrame, list[Dispatch]]:
    """Week after week: respond under the belief, clear, settle, observe, learn.
    ``ex_post_peak`` settles the investment layer on the realized peak hour
    instead of the announced one. Returns one row per week and the dispatches."""
    rows, dispatches = [], []
    for scenario in scenarios:
        offer = c_s(theta, scenario.delta)
        if belief is None:
            belief = Belief.announced(market, scenario, tariff, theta)
        believed = tariff
        if belief.w_peak is not None:
            believed = _with_peak(tariff, belief.w_peak)
        d, sigma = best_response(theta, believed, scenario.delta, belief.lam, belief.mu, belief.C_res, belief.C_inv, scenario.d_other, belief.d_hat)
        elected = _elected(theta, believed, scenario, belief, d, sigma)
        actual = elected
        ex_ante = market.clear(scenario, actual, scenario.delta, np.zeros(scenario.T), offer)
        dispatch = market.clear(scenario, actual, d, sigma, offer)
        realized_peak = int(np.argmax(dispatch.d + scenario.d_other))
        if ex_post_peak:
            actual = actual.with_window("investment", peak_hour(dispatch.d + scenario.d_other))
        bill = settle(actual, market, scenario, dispatch, ex_ante)
        C_res, C_inv = pools_for(actual, market, scenario, dispatch, ex_ante)
        rows.append(
            {
                "week": scenario.week,
                "S": S(theta, market, scenario, dispatch),
                "bill_total": float(total(bill)),
                "bill_investment": float(bill["investment"]),
                "believed_peak": int(np.argmax(belief.w_peak)) if belief.w_peak is not None else int(np.argmax(actual.investment.w)),
                "realized_peak": realized_peak,
                "energy_shifted": float(np.abs(d - scenario.delta).sum()),
            }
        )
        dispatches.append(dispatch)
        belief = learner.update(belief, Observation(dispatch, C_res, C_inv, realized_peak if reveal_peak else None))
    return pl.DataFrame(rows), dispatches


def _with_peak(tariff, w):
    if isinstance(tariff, Menu):
        return Menu(tuple(t.with_window("investment", w) for t in tariff.options), tariff.name)
    return tariff.with_window("investment", w)


def _elected(theta, tariff, scenario, belief, d, sigma) -> Tariff:
    """Under a menu, the option the load's bid came from."""
    if not isinstance(tariff, Menu):
        return tariff
    best, best_payoff = None, -np.inf
    from .load import V

    for option in tariff.options:
        bill = option.bill(d, sigma, belief.lam, belief.mu, belief.C_res, belief.C_inv, scenario.d_other, d_hat=belief.d_hat)
        payoff = float(V(theta, scenario.delta, d, sigma) - total(bill))
        if payoff > best_payoff:
            best, best_payoff = option, payoff
    return best
