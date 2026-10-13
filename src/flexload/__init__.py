"""flexload: tariff design for price-responsive loads, the memo transcribed.

The working set, in the order a session uses them::

    scenario = build_scenario(week, alpha)            # ω and δ
    market   = Market(reserve="ercot")                # the environment
    tariffs  = named_tariffs(scenario)                # τ₀ … τ₆
    theta    = named_types(scenario.T)["mover"]       # θ
    offer    = c_s(theta, scenario.delta)             # cˢ
    b0       = market.clear(scenario, tau, delta, 0, offer)
    d, sigma = best_response(theta, tau, delta, lam, mu, C_res, C_inv, d_other, d_hat)
    dispatch = market.clear(scenario, tau, d, sigma, offer)
    bill     = tau.bill(dispatch.d, dispatch.sigma, lam, mu, C_res, C_inv, d_other)
    d1, s1, S_star = planner(theta, market, scenario)
"""

from .load import (
    LoadType,
    V,
    best_response,
    c_s,
    feasible,
    fixed_point,
    named_types,
    planner,
    windows_daily,
    windows_elastic,
    windows_inflexible,
    windows_weekly,
)
from .market import DemandCurve, Dispatch, Market
from .metrics import S, alignment, fairness, recovery, settle, summary
from .operator import choose, evaluate, respond
from .scenario import Scenario, build_scenario, reserve_margin, with_reserve_margin
from .simulate import Belief, Combined, PeakCounts, PriceAveraging, Static, simulate
from .tariff import (
    Firm,
    Menu,
    Tariff,
    all_hours,
    firm,
    hourly,
    marginal,
    named_tariffs,
    peak_hour,
    share,
    total,
    two_part,
)

__all__ = [
    "Belief", "Combined", "DemandCurve", "Dispatch", "Firm", "LoadType", "Market", "Menu",
    "PeakCounts", "PriceAveraging", "S", "Scenario", "Static", "Tariff", "V",
    "alignment", "all_hours", "best_response", "build_scenario", "c_s", "choose", "evaluate",
    "fairness", "feasible", "firm", "fixed_point", "hourly", "marginal", "named_tariffs",
    "named_types", "peak_hour", "planner", "recovery", "reserve_margin", "respond", "settle",
    "share", "simulate", "summary", "total", "two_part", "windows_daily", "windows_elastic",
    "windows_inflexible", "windows_weekly", "with_reserve_margin",
]
