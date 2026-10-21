"""flexload: tariff design for price-responsive loads, the memo transcribed.

    weeks    = windows(T=168, alpha=0.05, reserve_margin=0.10)   # ω and δ: the year in operating windows
    market   = Market(reserve="ercot")                           # the environment
    market   = replace(market, missing_money=missing_money(market, weeks))
    scenario = weeks[31]
    tau      = named_tariffs(scenario)["tau_0"]                  # τ, today's tariff
    theta    = named_types(scenario.T, "data_center")["mover"]   # θ
    b0       = market.clear(scenario, scenario.delta, 0, c_sigma(theta, scenario.delta))   # B0
    d, sigma = best_response(theta, tau, scenario, belief=b0)                              # R
    dispatch = market.clear(scenario, d, sigma, c_sigma(theta, scenario.delta))
    bill     = settle(tau, scenario, dispatch, b0)
    d1, s1, S_B1 = planner(theta, market, scenario)                                       # B1
"""

from .load import BETA, BUSINESS, P, PSI, LoadType, V, best_response, blocks, c_sigma, elect, feasible, fixed_point, named_types, payoff, planner
from .metrics import S, alignment, choose, fairness, learn, recovery, respond, settle, summary, table
from .system import DemandCurve, Dispatch, Market, Scenario, margin, missing_money, scenario, tighten, windows
from .tariff import Menu, Share, Tariff, TwoPart, all_hours, named_tariffs, peak_hour, share, total, two_part

__all__ = [
    "BETA", "BUSINESS", "DemandCurve", "Dispatch", "LoadType", "Market", "Menu", "P", "PSI", "S", "Scenario", "Share", "Tariff",
    "TwoPart", "V", "alignment", "all_hours", "best_response", "blocks", "c_sigma", "choose", "elect", "fairness", "feasible",
    "fixed_point", "learn", "margin", "missing_money", "named_tariffs", "named_types", "payoff", "peak_hour", "planner",
    "recovery", "respond", "scenario", "settle", "share", "summary", "table", "tighten", "total", "two_part", "windows",
]
