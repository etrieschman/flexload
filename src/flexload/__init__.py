"""flexload: tariff design for price-responsive loads, the memo transcribed.

    weeks    = windows(T=168, alpha=0.05, reserve_margin=0.08)   # ω and δ: the year in operating windows
    market   = Market(named_ordcs(weeks[31])["ercot"])           # the environment: a reserve construct
    market   = replace(market, C_inv=C_inv(market, weeks))                      # annual cost of the investment layer
    scenario = weeks[31]
    tau      = named_tariffs(scenario)["tau_0"]                  # τ, today's tariff
    theta    = named_types(scenario.T, "training")["mover"]            # θ
    b0       = market.clear(scenario, scenario.delta, 0, c_sigma(theta, scenario.delta))   # B0
    d, sigma = best_response(theta, tau, scenario, Belief(b0, False), b0)                   # R, exogenous price-taker
    dispatch = market.clear(scenario, d, sigma, c_sigma(theta, scenario.delta))
    bill     = settle(tau, scenario, dispatch, b0)
    d1, s1 = planner(theta, market, scenario)                                             # B1
"""

from .load import BETA_MIN, FIRM, P, WORKLOAD, Belief, LoadType, S, V, best_response, c_sigma, feasible, fixed_point, named_types, payoff, planner
from .realized import reserve, shed, worst
from .metrics import alignment, fairness, recovery, respond, settle, summary, table, tex
from .system import VOLL, C_inv, Dispatch, Expectation, Market, Maximum, Normal, ORDC, Points, Scenario, fit, margin, named_ordcs, scenario, steps, tighten, windows
from .tariff import LAYERS, Marginal, Share, Tariff, TwoPart, named_tariffs, peak_hour

__all__ = [
    "BETA_MIN", "Belief", "C_inv", "Dispatch", "Expectation", "FIRM", "LAYERS", "LoadType", "Marginal", "Market", "Maximum", "Normal", "ORDC", "P", "Points", "S", "Scenario", "Share", "Tariff",
    "TwoPart", "V", "VOLL", "WORKLOAD", "alignment", "best_response", "c_sigma", "fairness", "feasible", "fit",
    "fixed_point", "margin", "named_ordcs", "named_tariffs", "named_types", "payoff", "peak_hour", "planner",
    "recovery", "reserve", "respond", "scenario", "settle", "shed", "steps", "summary", "table", "tex", "tighten", "windows", "worst",
]
