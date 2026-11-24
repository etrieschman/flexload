"""flexload: reserve constructs and tariffs for a price-responsive load, the report transcribed.

    weeks    = windows(T=168, alpha=0.1, reserve_margin=0.06)   # ω and δ: the year in operating windows
    market   = Market(named_ordcs(weeks[29])["ercot"])           # the environment: a reserve construct
    market   = replace(market, C_inv_year=C_inv(market, weeks))                      # annual cost of the investment layer
    scenario = weeks[29]
    tau      = named_tariffs(scenario)["tau_0"]                  # τ, today's tariff
    theta    = named_types(scenario.T, "training")["mover"]            # θ
    b0       = market.clear(scenario, scenario.delta, 0, c_sigma(theta, scenario.delta))   # B0
    d, sigma = best_response(theta, tau, scenario, Belief(b0, False), b0)                   # R, exogenous price-taker
    dispatch = market.clear(scenario, d, sigma, c_sigma(theta, scenario.delta))
    bill     = settle(tau, scenario, dispatch, b0)
    d1, s1 = planner(theta, market, scenario)                                             # B1
"""

from .load import FIRM, P, WORKLOAD, Belief, LoadType, S, V, best_response, c_sigma, feasible, fixed_point, named_types, payoff, planner
from .realized import outcomes, shed, worst
from .metrics import alignment, alignment_summary, fairness, recovery, respond, settle, summary, table, tex, welfare
from .system import HOURS_PER_YEAR, VOLL, C_inv, Dispatch, Expectation, Market, Maximum, Normal, ORDC, Points, Scenario, fit, margin, marginal_cost, named_ordcs, rent, reserve, scenario, steps, tighten, windows
from .system import baseline
from .tariff import LAYERS, Marginal, Share, Tariff, TwoPart, named_tariffs, peak_hour

__all__ = [
    "Belief", "C_inv", "Dispatch", "Expectation", "FIRM", "HOURS_PER_YEAR", "LAYERS", "LoadType", "Marginal", "Market", "Maximum", "Normal", "ORDC", "P", "Points", "S", "Scenario", "Share", "Tariff",
    "TwoPart", "V", "VOLL", "WORKLOAD", "alignment", "alignment_summary", "baseline", "best_response", "c_sigma", "fairness", "feasible", "fit",
    "fixed_point", "margin", "marginal_cost", "named_ordcs", "named_tariffs", "named_types", "outcomes", "payoff", "peak_hour", "planner",
    "recovery", "rent", "reserve", "respond", "scenario", "settle", "shed", "steps", "summary", "table", "tex", "tighten", "welfare", "windows", "worst",
]
