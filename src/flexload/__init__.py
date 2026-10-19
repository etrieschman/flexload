"""flexload: tariff design for price-responsive loads, the memo transcribed.

    weeks    = periods(T=168, alpha=0.05, reserve_margin=0.10)   # ω and δ, the year
    market   = Market(reserve="ercot")                           # the environment
    market   = replace(market, missing_money=missing_money(market, weeks))
    scenario = weeks[31]
    tau      = named_tariffs(scenario)["tau_0"]                  # τ
    theta    = named_types(scenario.T)["mover"]                  # θ
    b0       = market.clear(scenario, scenario.delta, 0, c_s(theta, scenario.delta))
    d, sigma = best_response(theta, tau, scenario, belief=b0)
    dispatch = market.clear(scenario, d, sigma, c_s(theta, scenario.delta))
    bill     = settle(tau, scenario, dispatch, b0)
    d1, s1, S_star = planner(theta, market, scenario)
"""

from .load import LoadType, V, best_response, c_s, elect, feasible, fixed_point, named_types, payoff, planner, windows
from .metrics import S, alignment, choose, fairness, learn, recovery, respond, settle, summary, table
from .system import DemandCurve, Dispatch, Market, Scenario, margin, missing_money, periods, scenario, tighten
from .tariff import Menu, Share, Tariff, TwoPart, all_hours, named_tariffs, peak_hour, share, total, two_part

__all__ = [
    "DemandCurve", "Dispatch", "LoadType", "Market", "Menu", "S", "Scenario", "Share", "Tariff", "TwoPart", "V",
    "alignment", "all_hours", "best_response", "c_s", "choose", "elect", "fairness", "feasible", "fixed_point", "learn",
    "margin", "missing_money", "named_tariffs", "named_types", "payoff", "peak_hour", "periods", "planner", "recovery",
    "respond", "scenario", "settle", "share", "summary", "table", "tighten", "total", "two_part", "windows",
]
