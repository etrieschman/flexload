# flexload — working notes

Tariff design for price-responsive loads in wholesale electricity markets, built
for the 6.S974 wargame. **The spec is the Workshop I report** (`wargame_workshopI.tex`
in the Overleaf project, §3 Game formulation). This repo transcribes it: one class
per object, one function per equation, nothing else.

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
  `docs/specifications.md` records every choice the report does not state.

## Notation: report → code

| report | code | where |
|---|---|---|
| ω = (d°, cᵘ, cʳ, cⁱⁿᵛ, ū), δ = α × system load | `Scenario(delta, d_other, cost_gen, cost_res, cost_inv, capacity, nameplate, unit, names, start)` | `system.py` |
| operating window 𝒯, the year, α, tightness | `scenario(start, T, alpha, reserve_margin, reserve_offer)`; `windows(T, alpha, reserve_margin, reserve_offer)` (the year, one tightness scale); `tighten`; `margin` | `system.py` |
| PJM / ERCOT, γ, cⱽᴼᴸᴸ, Cⁱⁿᵛ (annual) | `Market(reserve, gamma, voll, long_run, ordc, C_inv, solver)` | `system.py` |
| ORDC steps (w_s, π_s), π(z) = VOLL·Pr[ε > z − R̲]; ε ~ N(0, σ²) from day-ahead vs real-time net load, one σ for the year | `ORDC.from_lolp(voll, min_contingency, epsilon_std, steps)`; `Scenario.epsilon_std`; `market.ordc_for(scenario)` with R̲ = the largest thermal unit's nameplate (`Scenario.renewable` marks wind, solar, hydro: no reserve, no contingency) | `system.py` |
| dispatch 𝓜_ω(d, σ) | `market.clear(scenario, d_bid, sigma_bid, c_sigma, d_firm) -> Dispatch` | `system.py` |
| (u, r, σᶜˡʳ, dᶜᵘʳᵗ, s), (λ, μ, ν), Π_t, Cᵏ | `Dispatch(d, sigma, u, r, shed, lam, mu, nu, eta, Pi, C_energy, C_res, C_inv, d_bid, sigma_bid, ...)`: `d, sigma` are what cleared, `d_bid, sigma_bid` what the load offered | `system.py` |
| Cⁱⁿᵛ := (T/8760) max{0, Σⱼ cⁱⁿᵛⱼ ūⱼ − the fleet's rent over the year} | `C_inv(market, windows)`, annual; `clear` prorates. Not "missing money": that needs a price cap, which there is none of | `system.py` |
| C_sys (the one cost formula: dispatch objective, planner, S), ∂C_sys/∂dₜ by layer | `market.C_sys(scenario, u, r, sigma, c_sigma, shed, y, Pi)`; `market.marginal_cost(dispatch)` | `system.py` |
| θ = (ψ, β, A, p, 𝕀{sells reserve}, 𝕀{curtailable}); dᶠⁱʳᵐ = (1−β) minₜ δₜ | `LoadType(psi, beta, A, p, sells_reserve, curtailable)`; `theta.d_firm(delta)` (a level; None if not curtailable) | `load.py` |
| A ∈ {1ᵀ, 0, I}; θ₀…θ₄ as a data center or a bitcoin mine | `np.ones((1, T))`, `np.zeros((0, T))`, `np.eye(T)` in `named_types(T, business)` with `PSI`, `BETA`, `P`, `BUSINESS` | `load.py` |
| V = −Σₜ (ψ/δₜ)(dₜ − δₜ)² − c^σᵀσ, value per MW of load, ψ in $/MWh; c^σ = 2pψβ, a rate; 𝒟_θ | `V`, `c_sigma`, `feasible` | `load.py` |
| 𝓜̃, a price-taker's belief: a dispatch and the Table 2 row | `Belief(dispatch, consistent)`; `consistent=False` is the exogenous price-taker, `True` the consistent one | `load.py` |
| the load's objective under a belief 𝓜̃ | `payoff(theta, tariff, scenario, belief, b0, d, sigma)` = V − B on the expected (d̃, σ̃); `b0` holds the ex-ante pools under every belief | `load.py` |
| R (QP) | `best_response(theta, tariff, scenario, belief, b0) -> (d_bid, sigma_bid)`; builds the tildes: σ̃ = σ_bid, constrained to 0 where μ̃ < c^σ; d̃ = dᶠⁱʳᵐ where the believed dispatch cut the load, if consistent | `load.py` |
| consistent price-taker | `fixed_point(theta, tariff, market, scenario, b0) -> (d, σ, dispatch, believed, history)`; `b0` given, as for `best_response` | `load.py` |
| B1 | `planner(theta, market, scenario) -> (d_bid, sigma_bid)`; S^B1 is read from its clearing, as for R | `load.py` |
| B0 | `market.clear(scenario, delta, zeros, c_sigma, d_firm)`; no function | — |
| the load's belief about curtailment | set by the belief (report Table 2): the exogenous price-taker consumes its bid; the consistent one expects dᶠⁱʳᵐ where the believed dispatch cut it, `belief.dispatch.d < belief.dispatch.d_bid`. Same as λ̃ at VOLL except at an exact tie, where the LP may shed others instead | `load.py` |
| τ: a charge form per layer, marginal / split pool / two-part; slots 𝒲ᵏ (`hours`, a 0/1 vector), ex ante, credit, exempt | `Tariff(energy, reserve, investment, credit, exempt_curtailable)`; `Marginal(hours)`, `Share(hours, ex_ante)`, `TwoPart(hours, ex_ante, phi, T)`; `np.ones(T)`, `peak_hour(d_sys)` | `tariff.py` |
| B = Σₖ Bᵏ, ∂Bᵏ/∂dₜ | `tariff.bill(d, sigma, realized, d_other, b0, d_hat, knows_share)`, `tariff.marginal(...)`; `realized` is the dispatch at the bid, `b0` the one at (δ, 0); the bill is the load's, and everyone else's is `settle(own=False)`: d and d° swapped, σ = 0, `replace(tariff, exempt_curtailable=False)`; every layer is hourly (the investment cost is spread over its hours); cvxpy expressions, `.value` for numbers. `marginal` holds Cᵏ fixed: exact ex ante, missing ∂Cᵏ/∂d ex post | `tariff.py` |
| τ₀ today | `named_tariffs(scenario)` returns τ₀ only, every slot spelled out. No other tariff, no menu, no election in the code; Workshop II adds them | `tariff.py` |
| S, one formula: the planner's objective and the outcome | `S(theta, market, scenario, d, sigma, u, r, shed, y, Pi)`, a cvxpy expression | `load.py` |
| settlement; ρᵏ; Δᵏₜ; fairness = everyone else's bill at R less at B0; efficiency S^B1 − S^R | `settle`, `recovery`, `alignment`, `fairness(tariff, scenario, responding, b0)`; `summary` (columns `S_B0, S_B1, S_R, efficiency, price_error`; the fleet's capacity rent `rent_b0, rent, rent_b1`; bill and ρᵏ at R and at B1, `bill_b1_*`, `recovery_b1_*`; Δᵏₜ at R, signed, over the hours where it is nonzero: their count `alignment_hours_*`, mean `alignment_*`, p1 and p99 `alignment_p1_*`, `alignment_p99_*`; None when no hour has a wedge) | `metrics.py` |
| R under a belief; the operator's table | `respond(theta, tariff, market, scenario, belief) -> (dispatch, b0, believed, history)`; `summary`; `table(types, tariffs, markets, scenarios)` | `metrics.py` |
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
| curtailment | **a load type**, not a tariff: `LoadType.curtailable` declares a firm **level** dᶠⁱʳᵐ = (1−β) minₜ δₜ, constant over the window, as ERCOT SB6 and PJM Non-Firm Contract Demand use a MW level. The LP curtails only where serving the load costs more than VOLL; unpaid, in exchange for connection. The planner holds the headroom instrument but consumes what it bids (letting it consume below its bid let it dodge energy conservation). The reserve exemption is a tariff slot. |
| operating window | T hours from `start` (report: 𝒯); the week is the default instance, nothing is hard-coded to it. cⁱⁿᵛ is annual on the scenario and prorated by T/8760. A is one of the report's three matrices; a tariff's hours 𝒲ᵏ are a weight vector, `np.ones(T)` or `peak_hour(d_sys)`. |
| solver | Gurobi (academic license) for the LP and the QPs; about 3× HiGHS on the clearing. `Market(solver="HIGHS")` and `best_response(..., solver=)` switch. Clearing ≈ 1.3 s, planner ≈ 2–3 s. |
| scenario knobs | carve-out α with the system's shape; **no flat or area profile** until an RQ needs it; tightness by `reserve_margin` at the tightest hour, scaling load not capacity; over a year one scale factor (`windows`), so only the annual peak window is at the margin. Outages are not modeled; git history has them. Reserve offers are cʳⱼ = `reserve_offer` × cᵘⱼ, 0.1 in the notebooks (with cʳ = 0 the reserve price is zero outside scarcity). |
| investment pool | annual, from the B0 run over the year, spread evenly (× T/8760), floored at zero. Not per window (negative in peak weeks, where it would pay the load to consume at the peak), not allocated to scarcity weeks. The rent is the fleet's profit on available capacity, ν_jt ū_jt, including the reserve row's dual. |
| calibration | R̲ is the largest thermal unit (400 MW); renewables hold no reserve; σ_ε scales with the load; the year is 8,760 h with February 29 dropped; the base window is week 32, the year's tightest hour. Investment costs are round placeholders (1,757 M$) and the reserve margin is 0.08, the tightest at which PJM's requirement is slack; there ERCOT's rents (1,768 M$) pay the fleet, so its investment pool is zero, and PJM's pool is 1,194 M$. `notebooks/tune_reserve_margin.py` is the sweep. Not tracked: the ORDC's first step and tail, hydro reserve, the TwoPart lump sum. |
| operator's objective | max-min welfare over Θ **without the inflexible load** (its welfare does not move with τ), or expected welfare under a prior; subject to g(ρ) ≤ 0 per layer or in total. No regret; `efficiency` = S^B1 − S^R is reported, not optimized. |
| named types | θ₀ inflexible, θ₁ mover, θ₂ controllable, θ₃ emergency, θ₄ curtailable; each run as a **data center** (ψ medium, β medium, A = 1ᵀ) or a **bitcoin mine** (ψ low, β high, A = 0); the emergency row is fixed (ψ medium, β low, A = 0, p high). Level values are placeholders. |
| repos | data from `rts-gmlc` (github.com/etrieschman/rts-gmlc, public, data only); never re-add a fetcher here. Tariff catalog lives in `docs/catalog/`. |
| parameter objects | frozen dataclasses throughout (arrays inside parameter objects); pydantic when a YAML config layer arrives with the experiment grids. |

## Layout

```
src/flexload/
  system.py   Scenario; scenario, windows, tighten, margin; ORDC.from_lolp; Dispatch; Market (ordc_for, C_sys, constraints, clear, marginal_cost); C_inv
  tariff.py   peak_hour; Marginal, Share, TwoPart; Tariff (bill, marginal); total; named_tariffs (τ₀)
  load.py     LoadType; PSI, BETA, P, BUSINESS; named_types; c_sigma; V; feasible; S; Belief; payoff; best_response; fixed_point; planner
  metrics.py  settle; recovery; alignment; fairness; respond; summary; table; tex
notebooks/walkthrough.py          jupytext cells; the documentation
notebooks/workshopI.py            the report's figures and tables (§4) at the base configuration, exogenous price-taker; writes notebooks/figures, notebooks/tables and copies to FLEXLOAD_OUT (`.env`, gitignored)
notebooks/tune_reserve_margin.py  the reserve-margin sweep behind the calibration
tests/        conftest (3-generator, 4-hour scenario); test_system, test_tariff, test_load
docs/         specifications.md (every choice the report does not state); assumptions.md; catalog/large_load_arrangements.md (designations), catalog/bill_decomposition.md (every ERCOT charge)
```

Imports run one way: system ← tariff ← load ← metrics. 38 tests.

## What is built and what is not

Built: both reserve constructs, the curtailable type, the three charge forms, ex-ante
and ex-post pools, the price-taker QP (posted rate or known share), the consistent
fixed point, the planner, the outcomes, and the operator's table. Only τ₀ is defined.

Not built: the price-setter (bilevel); 𝒦ʳᵉˢᵖ, a filter over the bill's layers; the
learner; the operator's choice of tariff; experiment grids over 52 weeks and seeds.

Two findings to keep in mind:

1. **The consistent price-taker can cycle under ERCOT.** The load leaves the scarcity
   hours, scarcity vanishes, prices fall, the load returns. The map from prices to
   response to prices has no pure-strategy fixed point when the load's tolerance band
   straddles a merit-order step at the peak: the load is large enough to change the
   marginal unit. `fixed_point(damping=None)` averages the iteration and `history`
   shows whether it settled; `damping=0.5` converges in ~17 steps on PJM.
2. Under ERCOT, `C_sys` includes −Σ∫π, which is large and negative when reserve is
   free. Differences in welfare are comparable across markets; levels are not.

## Next steps, in order

1. `experiments/`: config grids for RQ1–RQ3 over 52 weeks; cache by config hash; the
   figure list. pydantic configs arrive here.
2. Price-setter: embed `market.constraints` as KKT conditions in the load's problem
   (regime enumeration first, hour-wise under linear costs, coupled through A).
3. 𝒦ʳᵉˢᵖ as a filter over the bill's layers in `best_response`.
4. Replace placeholders: investment costs by category, the ORDC from LOLP, the
   named-type values.
5. The learner and the operator's rule, when a study needs them.
