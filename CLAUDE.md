# flexload — working notes

Tariff design for price-responsive loads in wholesale electricity markets, built
for the 6.S974 wargame. **The spec is the Workshop I report** (`wargame_workshopI.tex`
in the Overleaf project, §3 Game formulation). This repo transcribes it: one class
per object, one function per equation, nothing else.

## To do

Confirmed bugs, from the audit (`docs/2026-11-11_audit.md`, findings 1 to 3):

1. Dispatch never curtails a curtailable load. Cutting it costs c^shed, the same as shedding other load, and also gives up its headroom, so other load is shed first. Price its curtailment below c^shed.
2. c^σ = 2pψβ leaves out the strike χ, so a controllable inference load offers reserve at zero cost.
3. C^energy bills load that was shed: in a shortage hour everyone else pays for MWh they did not receive.

Decide:

4. Which belief is the base. Every table so far uses the exogenous price-taker. Run the consistent one on the new model (`BELIEFS` in `notebooks/results.py`); the V test suggests the exogenous one over-responds at 10% of load.
5. The placeholder values: ψ, χ, β, β_min, κ. One small table each, showing what moves.

Build:

6. Learning: an operator that refits (m, v) each week with `fit()`, against a fixed curve.
7. What the operator believes about η, and nature's draw of the workload.
8. Table 3 in `results.py` (the V test, `docs/2026-11-11_v_test.md`), and the figures.
9. The 52-week run, once 4 to 7 are settled.

Clean:

10. The rest of the audit: delete `long_run`, `Maximum`, `Market.curve` and four unread `Dispatch` fields; give "realized", "belief" and "shed" one meaning each; split `summary`; write `rent` and `reserve` once.

Write:

11. The report's formulation section, which predates the ORDC object, the two prices, the strike, κ, the firm contract, realized dispatch and the two tariff forms. Add the new references. Get the final deliverable's date and format.

## Working rules

- Propose before editing. No code, file edits or commits without a go-ahead in chat
  for that piece of work. List the decisions a change needs, then stop.
- Use the report's terms. A capitalized class is a record for one of the report's
  objects, with no behavior. If a name needs explaining, it is wrong.
- Letters where the report has a letter, words where it has a word (table below).
- An option exists only if a research question varies it; an option is an enum value
  or a vector, never a branch in a solver; the report's base configuration is the
  default.
- No docs for their own sake. The walkthrough notebook is the documentation;
  `docs/assumptions.md` is one bulleted list: each modeling assumption in a clause,
  then one sentence on the gap with reality. Do not grow `docs/specifications.md`.


## Notation: report → code

| report | code | where |
|---|---|---|
| ω = (d°, cᵘ, cʳ, cⁱⁿᵛ, ū), δ = α × system load | `Scenario(delta, d_other, cost_gen, cost_res, cost_inv, capacity, nameplate, unit, names, start)` | `system.py` |
| operating window 𝒯, the year, α, tightness | `scenario(start, T, alpha, reserve_margin, reserve_offer)`; `windows(T, alpha, reserve_margin, reserve_offer)` (the year, one tightness scale); `tighten`; `margin` | `system.py` |
| the environment: a reserve construct, c^shed, Cⁱⁿᵛ (annual); cⱽᴼᴸᴸ a constant | `Market(ordc, c_shed=VOLL, long_run, C_inv, solver)`; `VOLL` | `system.py` |
| a reserve construct: ε_t = contingency + error, and the statistic that prices it. Contingency: the larger of R̲ and the largest online unit, each weighted by `units` (a multiple per physical unit: 0 leaves it out, 2 covers it twice). Error: `Normal(m, v)` or `Points(mw, probability)`. Statistic: `Expectation(c_pen)` or `Maximum()` (CVaR would be one more) | `ORDC(min_contingency, units, error, statistic, name)`; `steps(ordc, c_shed, n)` gives the curve π as (edges above the contingency, prices), top price below the contingency; `named_ordcs(scenario)`: `ercot`, `pjm` ($850 then $300, a two-point error), `n-1` (the hard row); `fit(error) -> Normal` | `system.py` |
| dispatch 𝓜_ω(d, σ) | `market.clear(scenario, d_bid, sigma_bid, c_sigma, d_firm) -> Dispatch` | `system.py` |
| (u, r, σᶜˡʳ, dᶜᵘʳᵗ, s), (λ, μ, ν), C^ORDC_t, Cᵏ | `Dispatch(d, sigma, u, r, shed, lam, mu, nu, C_ordc, C_energy, C_res, C_inv, d_bid, sigma_bid, ...)`: `d, sigma` are what cleared, `d_bid, sigma_bid` what the load offered. `C_ordc` is the ORDC's cost Σ_s π_s (w_st − z_st), a real cost in C_sys; `C_res` = μ × reserve bought is the pool the tariff bills; μ_t = −∂C^ORDC/∂R_t | `system.py` |
| Cⁱⁿᵛ := (T/8760) max{0, Σⱼ cⁱⁿᵛⱼ ūⱼ − the fleet's rent over the year} | `C_inv(market, windows)`, annual; `clear` prorates. Not "missing money": that needs a price cap, which there is none of | `system.py` |
| C_sys (the one cost formula: dispatch objective, planner, S), C^ORDC, ∂C_sys/∂dₜ by layer | `market.C_sys(scenario, u, r, sigma, c_sigma, shed, y, C_ordc)`; `market.C_ordc(scenario, u, r, z)`; `market.curve()`; `market.marginal_cost(dispatch)` | `system.py` |
| θ = (ψ, χ, β, A, κ, p, 𝕀{sells reserve}, firm); dᶠⁱʳᵐ = firm × minₜ δₜ with firm = 1 − β_min, the data center's contract | `LoadType(psi, chi, beta, A, kappa, p, sells_reserve, firm)`; `theta.curtailable`; `theta.d_firm(delta)` (a level; None if not curtailable); `BETA_MIN`, `FIRM` | `load.py` |
| A ∈ {1ᵀ, 0, I}; θ₀…θ₄ for a data center running training or inference | `np.ones((1, T))`, `np.zeros((0, T))`, `np.eye(T)` in `named_types(T, workload)` with `WORKLOAD`, `P` | `load.py` |
| V = −χ Σₜ max(δₜ − dₜ, 0) − Σₜ (ψ/δₜ)(dₜ − δₜ)² − c^σᵀσ: χ the strike, ψ a penalty per MW of load, both $/MWh; c^σ = 2pψβ, a rate; 𝒟_θ (a curtailable load bids d ≥ dᶠⁱʳᵐ) | `V`, `c_sigma`, `feasible` | `load.py` |
| 𝓜̃, a price-taker's belief: a dispatch and the Table 2 row | `Belief(dispatch, consistent)`; `consistent=False` is the exogenous price-taker, `True` the consistent one | `load.py` |
| the load's objective under a belief 𝓜̃ | `payoff(theta, tariff, scenario, belief, b0, d, sigma)` = V − B on the expected (d̃, σ̃); `b0` holds the ex-ante pools under every belief | `load.py` |
| R (QP) | `best_response(theta, tariff, scenario, belief, b0) -> (d_bid, sigma_bid)`; builds the tildes: σ̃ = σ_bid, constrained to 0 where μ̃ < c^σ; d̃ = dᶠⁱʳᵐ where the believed dispatch cut the load, if consistent | `load.py` |
| consistent price-taker | `fixed_point(theta, tariff, market, scenario, b0) -> (d, σ, dispatch, believed, history)`; `b0` given, as for `best_response` | `load.py` |
| B1 | `planner(theta, market, scenario) -> (d_bid, sigma_bid)`; S^B1 is read from its clearing, as for R | `load.py` |
| B0 | `market.clear(scenario, delta, zeros, c_sigma, d_firm)`; no function | — |
| the load's belief about curtailment | set by the belief (report Table 2): the exogenous price-taker consumes its bid; the consistent one expects dᶠⁱʳᵐ where the believed dispatch cut it, `belief.dispatch.d < belief.dispatch.d_bid`. Same as λ̃ at VOLL except at an exact tie, where the LP may shed others instead | `load.py` |
| τ: a charge form per layer, marginal / split pool / two-part; slots 𝒲ᵏ (`hours`, a 0/1 vector), ex ante, credit, exempt | `Tariff(energy, reserve, investment, credit, exempt_curtailable)`; `Marginal(hours)`, `Share(hours, ex_ante)`, `TwoPart(hours, ex_ante, phi, T)`; `np.ones(T)`, `peak_hour(d_sys)` | `tariff.py` |
| B = Σₖ Bᵏ, ∂Bᵏ/∂dₜ | `tariff.bill(d, sigma, realized, d_other, b0, d_hat, knows_share)`, `tariff.marginal(...)`; `realized` is the dispatch at the bid, `b0` the one at (δ, 0); the bill is the load's, and everyone else's is `settle(own=False)`: d and d° swapped, σ = 0, `replace(tariff, exempt_curtailable=False)`; every layer is hourly (the investment cost is spread over its hours); cvxpy expressions, `.value` for numbers. `marginal` holds Cᵏ fixed: exact ex ante, missing ∂Cᵏ/∂d ex post | `tariff.py` |
| τ₀ today, in each market's form | `named_tariffs(scenario)` returns `tau_0_pjm` (investment split on the peak hour, as a capacity charge) and `tau_0_ercot` (`investment=None`: the layer is not billed, since ERCOT does not pay for capacity; ρⁱⁿᵛ is then the fleet's unrecovered cost). Pair each with its construct; `n-1` takes PJM's. No other tariff, no menu, no election in the code | `tariff.py` |
| S, one formula: the planner's objective and the outcome | `S(theta, market, scenario, d, sigma, u, r, shed, y, C_ordc)`, a cvxpy expression | `load.py` |
| settlement; ρᵏ; Δᵏₜ; fairness = everyone else's bill at R less at B0; efficiency S^B1 − S^R | `settle`, `recovery`, `alignment`, `fairness(tariff, scenario, responding, b0)`; `summary` (columns `S_B0, S_B1, S_R, efficiency, price_error`; the fleet's capacity rent `rent_b0, rent, rent_b1`; bill and ρᵏ at R and at B1, `bill_b1_*`, `recovery_b1_*`; Δᵏₜ at R, signed, over the hours where it is nonzero: their count `alignment_hours_*`, mean `alignment_*`, p1 and p99 `alignment_p1_*`, `alignment_p99_*`; None when no hour has a wedge) | `metrics.py` |
| realized dispatch: ε_t = tripped units' output + net-load error + η_t, η_t ~ N(0, (κ dₜ)²); shed is what reserve does not cover | `shed(scenario, dispatch, theta, rng, n) -> (n, T)` MWh; `worst(scenario, dispatch, k)`; `reserve(dispatch)`; `Scenario.trip` (1/MTTF), `Scenario.error` (T, 12), `Scenario.error_fit` | `realized.py` |
| R under a belief; the operator's table | `respond(theta, tariff, market, scenario, belief) -> (dispatch, b0, believed, history)`; `summary` (adds reserve cost, C^ORDC, shed mean and worst-5% mean, worst-1 and worst-2, at B0 and R; `hours_at_bound`); `table(types, tariffs, markets, scenarios)` | `metrics.py` |
| the operator's rule: max-min / expected welfare s.t. g(ρ) ≤ 0 | not in the code; git 22257a4 has a `choose` | — |
| the learner (fourth belief) | not in the code; git 0d47d74 has the last version | — |

Conventions: capitalized = class holding data; lowercase = function; order is always
(d, σ). **One number system**: every formula is a cvxpy expression whether its
inputs are numbers or variables; read a number with `.value`. No wrapper layer.

## Design decisions (settled; do not relitigate)

| topic | decision |
|---|---|
| accounting | c^σᵀσ sits in V **and** in the LP objective (the load offers at cost). Welfare counts it once: `S = V − C_sys + c^σᵀσ`. The reserve payment μᵀσ is a **credit layer of the bill** (`Tariff.credit`); the load's payoff is V − B. |
| the tariff is a function | three charge forms (`Marginal`, `Share`, `TwoPart`), one per layer, energy included, plus the `credit` and `exempt_curtailable` slots. Every layer is hourly; the investment cost is spread over its hours. No enums, no strings, no lowercase wrappers: hours 𝒲ᵏ are 0/1 vectors, `ex_ante` is a bool, φ and T are computed from the pool unless `T` is given. τ ranges over a finite set; φ and ε are swept, not optimized (report §3). |
| what the bill reads | a `Dispatch` (λ, μ and the pools ride on it) plus d°. Each layer's `ex_ante` flag picks the ex-ante or realized dispatch. Inside the load's objective the dispatch is its belief; a price-setter's belief would be a dispatch whose prices are expressions. |
| own share | The exogenous price-taker takes the **posted average rate** at x̂ = δ (ERCOT posts a provisional share). The consistent price-taker **knows its share**: its charge is linearized at x̂ with the true slope Cᵏx°/(x̂+x°)², and the fixed point iterates x̂ with the prices, so it is exact at convergence. The exact charge is concave in x, so one QP cannot do it; the iteration can. x̂ is the bid the belief answered, `belief.dispatch.d_bid` (δ for the exogenous one); `Tariff.bill` keeps `d_hat` and `knows_share` since tariff.py cannot see the load. |
| beliefs | `Belief(dispatch, consistent)`, a frozen record with no methods. A price-taker reads λ, μ, the pools, x̂ and its expected curtailment off `dispatch`; `consistent` is the Table 2 row. A price-setter's belief is the market itself (bilevel, not built): its dispatch will carry prices that are expressions of the bid, and `payoff` reads it unchanged; `planner` already embeds dispatch with the load's bid as a variable, which is its shape. The operator knows which belief the load holds (report §3); RQ4 relaxes that. |
| clearing | `clear` takes dᶠⁱʳᵐ as a vector from the type (`theta.d_firm`), not a tariff. The cost `C_sys` and the `constraints` are written once and shared by `clear`, `planner` and `S`. Net reserve X is its own variable so per-unit rows stay sparse. `clear` clips a negative offer to zero (a solver's −1e-10 on σ ≥ 0); the QPs return the solver's value. Other load sheds at VOLL (`Dispatch.shed`), so λ and μ reach VOLL in shortage hours in both markets. |
| curtailment | a public contract on the data center, `LoadType.firm`: it keeps dᶠⁱʳᵐ = (1−β_min) minₜ δₜ firm whatever workload runs, constant over the window, as ERCOT SB6 and PJM Non-Firm Contract Demand use a MW level. A curtailable load bids at least dᶠⁱʳᵐ (training tolerates more than β_min, and headroom below zero would subtract from reserve). The LP curtails only where serving the load costs more than c^shed; unpaid, in exchange for connection. The reserve exemption is a tariff slot. |
| operating window | T hours from `start` (report: 𝒯); the week is the default instance, nothing is hard-coded to it. cⁱⁿᵛ is annual on the scenario and prorated by T/8760. A is one of the report's three matrices; a tariff's hours 𝒲ᵏ are a weight vector, `np.ones(T)` or `peak_hour(d_sys)`. |
| solver | Gurobi (academic license) for the LP and the QPs; about 3× HiGHS on the clearing. `Market(solver="HIGHS")` and `best_response(..., solver=)` switch. Clearing ≈ 1.3 s, planner ≈ 2–3 s. |
| scenario knobs | carve-out α with the system's shape; **no flat or area profile** until an RQ needs it; tightness by `reserve_margin` at the tightest hour, scaling load not capacity; over a year one scale factor (`windows`), so only the annual peak window is at the margin. Outages are not modeled; git history has them. Reserve offers are cʳⱼ = `reserve_offer` × cᵘⱼ, 0.1 in the notebooks (with cʳ = 0 the reserve price is zero outside scarcity). |
| investment pool | annual, from the B0 run over the year, spread evenly (× T/8760), floored at zero. Not per window (negative in peak weeks, where it would pay the load to consume at the peak), not allocated to scarcity weeks. The rent is the fleet's profit on available capacity, ν_jt ū_jt, including the reserve row's dual. |
| calibration | Dispatch clears on RTS-GMLC's real-time series at hourly means; the error is each five-minute net-load value less its hour's mean (sd 132 MW, 1.3% of peak), one series for the curve's fit and the realized path. A contingency is a thermal unit; the largest is 400 MW. Both markets hold their top price up to `CONTINGENCY_MULTIPLE` = 2 times the largest unit (PJM's memo gives 1.95, ERCOT's 3,000 MW level is 2.2 of its 1,375 MW unit): PJM at $850 on the largest online unit, then $300 for 12% of a unit more; ERCOT at VOLL less the highest fuel cost on nameplate, then a normal curve with its mean shifted up half a standard deviation. Renewables do not offer reserve. The year is 8,760 h with February 29 dropped; the base window is week 29, the year's tightest hour. Investment costs are round placeholders (1,757 M$). The reserve margin is 0.06, where ERCOT's rent (1,796 M$) pays the fleet; PJM's rent is 683 M$, leaving about 1,070 M$. Neither market sheds load in dispatch there. Dispatch does not model outages. χ = 500 for inference and κ = 0.2 for both workloads (placeholders). `notebooks/tune_reserve_margin.py` is the sweep. |
| operator's objective | max-min welfare over Θ **without the inflexible load** (its welfare does not move with τ), or expected welfare under a prior; subject to g(ρ) ≤ 0 per layer or in total. No regret; `efficiency` = S^B1 − S^R is reported, not optimized. |
| named types | θ₀ inflexible, θ₁ mover, θ₂ controllable, θ₃ emergency, θ₄ curtailable; each for a data center running **training** (ψ, energy conserved over the window, β 0.5) or **inference** (strike χ, nothing conserved, β 0.1); the emergency row is fixed. Values are placeholders. The bitcoin mine is in git history; it is inference's form with a low strike. |
| repos | data from `rts-gmlc` (github.com/etrieschman/rts-gmlc, public, data only); never re-add a fetcher here. Tariff catalog lives in `docs/catalog/`. |
| parameter objects | frozen dataclasses throughout (arrays inside parameter objects); pydantic when a YAML config layer arrives with the experiment grids. |

## Layout

```
src/flexload/
  system.py   Scenario; Normal, fit; scenario, windows, tighten, margin; Points, Expectation, Maximum, ORDC, steps, named_ordcs; Dispatch; Market (curve, C_ordc, C_sys, constraints, clear, marginal_cost); C_inv
  tariff.py   peak_hour; Marginal, Share, TwoPart; Tariff (bill, marginal); total; named_tariffs (τ₀)
  load.py     LoadType; WORKLOAD, BETA_MIN, FIRM, P; named_types; c_sigma; V; feasible; S; Belief; payoff; best_response; fixed_point; planner
  realized.py reserve; shed; worst
  metrics.py  settle; recovery; alignment; fairness; respond; summary; table; tex
notebooks/walkthrough.py          jupytext cells; the documentation
notebooks/results.py              the results tables, in cells: settings at the top (weeks, constructs, workloads, beliefs); rows cached in notebooks/tables/rows.csv; writes .csv and .tex to notebooks/tables and copies .tex to FLEXLOAD_OUT (`.env`, gitignored)
notebooks/tune_reserve_margin.py  the reserve-margin sweep behind the calibration
tests/        conftest (3-generator, 4-hour scenario); test_system, test_tariff, test_load, test_realized
docs/         assumptions.md (each assumption and its gap with reality); specifications.md (frozen); catalog/large_load_arrangements.md (designations), catalog/bill_decomposition.md (every ERCOT charge)
```

Imports run one way: system ← tariff ← load ← realized ← metrics. 51 tests.

## What is built and what is not

Built: the reserve construct as one object (ERCOT, PJM, hard N−1); the curtailable
contract; the two workloads; the three charge forms with ex-ante and ex-post pools;
today's tariff in each market's form; the price-taker QP (posted rate or known share);
the consistent fixed point; the planner; realized dispatch; the outcomes; the results
workbook.

Not built: the price-setter (bilevel); an operator that learns; the operator's choice
of tariff; a run over 52 weeks and seeds. See "To do" at the top.

Two findings to keep in mind:

1. **The consistent price-taker can cycle under ERCOT.** The load leaves the scarcity
   hours, scarcity vanishes, prices fall, the load returns. The map from prices to
   response to prices does not have a pure-strategy fixed point when the load's tolerance band
   straddles a merit-order step at the peak: the load is large enough to change the
   marginal unit. `fixed_point(damping=None)` averages the iteration and `history`
   shows whether it settled; `damping=0.5` converges in ~17 steps on PJM.
2. `C_sys` carries the ORDC as a cost, C^ORDC, under every construct, so welfare levels
   are costs; each construct still prices its own model of ε, so compare constructs on
   realized shed, not on C^ORDC.
