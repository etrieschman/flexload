# flexload — working notes for Claude

Tariff design for price-responsive loads in wholesale electricity markets: the
6.S974 wargame and Erich's flexible-loads research stream after it. **The spec is
the Workshop I report** (`wargame_report.tex` in the Overleaf project, §3 Game
formulation), which supersedes the memo `wargame_master.tex` where they differ.
This repo transcribes it: one class per object, one function per equation,
nothing else. Aligned 2026-10-21. Private repo.

## Rules of engagement (Erich's, 2026-10-13)

- **No code, file edits, repos or commits without an explicit yes in chat** for that
  piece of work. "Feel free" in a planning conversation is not a yes. Propose, list the
  decisions needed, stop.
- Use the memo's terms. Do not invent abstractions (no "PriceView", "truth rule"). A
  capitalized class is a record for one of the report's objects, with no behavior. If a
  name needs explaining, it is wrong.
- Letters where the memo has a letter, words where it has a word (table below).
- An option exists only if a research question in the memo varies it; an option is an
  enum value or a vector, never a branch in a solver; the memo's base configuration is
  the default. Erich is "very bad at narrowing down" and asked to be held to this.
- No docs for their own sake. The walkthrough notebook is the documentation.

## Notation: report → code

| report | code | where |
|---|---|---|
| ω = (d°, cᵘ, cʳ, cⁱⁿᵛ, ū), δ = α × system load | `Scenario(delta, d_other, cost_gen, cost_res, cost_inv, capacity, nameplate, unit, names, start)` | `system.py` |
| operating window 𝒯, the year, α, tightness | `scenario(start, T, alpha, reserve_margin)`; `windows(T, alpha, reserve_margin)` (the year, one tightness scale); `tighten`; `margin` | `system.py` |
| PJM / ERCOT, γ, cⱽᴼᴸᴸ, Cⁱⁿᵛ (annual) | `Market(reserve, gamma, voll, long_run, ordc, C_inv, solver)` | `system.py` |
| ORDC steps (w_s, π_s), π(z) = VOLL·Pr[ε > z − R̲]; ε ~ N(0, σ²) from day-ahead vs real-time net load, one σ for the year | `ORDC.from_lolp(voll, min_contingency, epsilon_std, steps)`; `Scenario.epsilon_std`; `market.ordc_for(scenario)` with R̲ = the largest unit | `system.py` |
| dispatch 𝓜_ω(d, σ) | `market.clear(scenario, d_bid, sigma_bid, c_sigma, d_firm) -> Dispatch` | `system.py` |
| (u, r, σᶜˡʳ, dᶜᵘʳᵗ, s), (λ, μ, ν), Π_t, Cᵏ | `Dispatch(d, sigma, u, r, shed, lam, mu, nu, eta, Pi, C_energy, C_res, C_inv, d_bid, sigma_bid, ...)`: `d, sigma` are what cleared, `d_bid, sigma_bid` what the load offered | `system.py` |
| Cⁱⁿᵛ := (T/8760) Σⱼ(cⁱⁿᵛⱼ − Σ_year νⱼₜ)ūⱼ | `C_inv(market, windows)`, annual; `clear` prorates. Not "missing money": that needs a price cap, which there is none of yet | `system.py` |
| C_sys (the one cost formula: dispatch objective, planner, S), ∂C_sys/∂dₜ by layer | `market.C_sys(scenario, u, r, sigma, c_sigma, shed, y, Pi)`; `market.marginal_cost(dispatch)` | `system.py` |
| θ = (ψ, β, A, p, 𝕀{sells reserve}, 𝕀{curtailable}); dᶠⁱʳᵐ = (1−β) minₜ δₜ | `LoadType(psi, beta, A, p, sells_reserve, curtailable)`; `theta.d_firm(delta)` (a level; None if not curtailable) | `load.py` |
| A ∈ {1ᵀ, 0, I}; θ₀…θ₄ as a data center or a bitcoin mine | `np.ones((1, T))`, `np.zeros((0, T))`, `np.eye(T)` in `named_types(T, business)` with `PSI`, `BETA`, `P`, `BUSINESS` | `load.py` |
| c^σₜ = 2pψβδₜ; V(d, σ); 𝒟_θ | `c_sigma`, `V`, `feasible` | `load.py` |
| 𝓜̃, a price-taker's belief: a dispatch and the Table 2 row | `Belief(dispatch, consistent)`; `consistent=False` is the exogenous price-taker, `True` the consistent one | `load.py` |
| the load's objective under a belief 𝓜̃ | `payoff(theta, tariff, scenario, belief, b0, d, sigma)` = V − B on the expected (d̃, σ̃); `b0` holds the ex-ante pools under every belief | `load.py` |
| R (QP) | `best_response(theta, tariff, scenario, belief, b0) -> (d_bid, sigma_bid)`; builds the tildes: σ̃ = σ_bid, constrained to 0 where μ̃ < c^σ; d̃ = dᶠⁱʳᵐ where the believed dispatch cut the load, if consistent | `load.py` |
| consistent price-taker | `fixed_point(theta, tariff, market, scenario) -> (d, σ, dispatch, believed, history)` | `load.py` |
| B1 | `planner(theta, market, scenario) -> (d_bid, sigma_bid)`; S^B1 is read from its clearing, as for R | `load.py` |
| B0 | `market.clear(scenario, delta, zeros, c_sigma, d_firm)`; no function | — |
| the load's belief about curtailment | set by the belief (report Table 2): the exogenous price-taker consumes its bid; the consistent one expects dᶠⁱʳᵐ where the believed dispatch cut it, `belief.dispatch.d < belief.dispatch.d_bid` (`best_response` when `belief.consistent`; `fixed_point` passes `Belief(dispatch, True)`). Same as λ̃ at VOLL except at an exact tie, where the LP may shed others instead (2026-10-23) | `load.py` |
| τ: a charge form per layer, marginal / split pool / two-part; slots 𝒲ᵏ (`hours`, a 0/1 vector), ex ante, credit, exempt | `Tariff(energy, reserve, investment, credit, exempt_curtailable)`; `Marginal(hours)`, `Share(hours, ex_ante)`, `TwoPart(hours, ex_ante, phi, T)`; `np.ones(T)`, `peak_hour(d_sys)` | `tariff.py` |
| B = Σₖ Bᵏ, ∂Bᵏ/∂dₜ | `tariff.bill(d, sigma, realized, d_other, b0, d_hat, own, knows_share)`, `tariff.marginal(...)`; `realized` is the dispatch at the bid, `b0` the one at (δ, 0); every layer is hourly (the investment cost is spread over its hours); cvxpy expressions, `.value` for numbers. `marginal` holds Cᵏ fixed: exact ex ante, missing ∂Cᵏ/∂d ex post | `tariff.py` |
| τ₀ today | `named_tariffs(scenario)` returns τ₀ only, every slot spelled out (Erich, 2026-10-21). No other tariff, no menu, no election in the code; Workshop II adds them. | `tariff.py` |
| S, one formula: the planner's objective and the outcome | `S(theta, market, scenario, d, sigma, u, r, shed, y, Pi)`, a cvxpy expression | `load.py` |
| settlement; ρᵏ; Δᵏₜ; fairness; efficiency S^B1 − S^R | `settle`, `recovery`, `alignment`, `fairness`; `summary` (columns `S_B0, S_B1, S_R, efficiency, price_error`) | `metrics.py` |
| R under a belief; the operator's table | `respond(theta, tariff, market, scenario, belief) -> (dispatch, b0, believed, history)`; `summary`; `table(types, tariffs, markets, scenarios)` | `metrics.py` |
| the operator's rule: max-min / expected welfare s.t. g(ρ) ≤ 0 | deleted 2026-10-23 (Erich: not yet); git 22257a4 has `choose` | — |
| the learner (fourth belief) | deleted 2026-10-21 (Erich: not thought through yet); git 0d47d74 has the last version | — |

Conventions: capitalized = class holding data; lowercase = function; order is always
(d, σ). **One number system**: every formula is a cvxpy expression whether its
inputs are numbers or variables; read a number with `.value`. No wrapper layer.

## Locked design (settled 2026-10-13 over a long planning pass; do not relitigate)

| topic | decision |
|---|---|
| accounting | c^σᵀσ sits in V **and** in the LP objective (the load offers at cost). Welfare counts it once: `S = V − C_sys + c^σᵀσ`. The reserve payment μᵀσ is a **credit layer of the bill** (`Tariff.credit`); the load's payoff is V − B. |
| the tariff is a function | three charge forms (`Marginal`, `Share`, `TwoPart`), one per layer, energy included (Erich, 2026-10-21: energy is a layer like the others), plus the `credit` and `exempt_curtailable` slots. Every layer is hourly; the investment cost is spread over its hours. No enums, no strings, no lowercase wrappers: hours 𝒲ᵏ are 0/1 vectors, `ex_ante` is a bool, φ and T are computed from the pool unless `T` is given. τ ranges over a finite set; φ and ε are swept, not optimized (report §3). |
| what the bill reads | a `Dispatch` (λ, μ and the pools ride on it) plus d°. Each layer's `ex_ante` flag picks the ex-ante or realized dispatch. Inside the load's objective the dispatch is its belief; a price-setter's belief would be a dispatch whose prices are expressions. Revised 2026-10-19 from "explicit arguments": the nine-argument signatures were the cost. |
| own share (was: rate-taker) | revised 2026-10-21. The exogenous price-taker takes the **posted average rate** at x̂ = δ (ERCOT posts a provisional share). The consistent price-taker **knows its share**: its charge is linearized at x̂ with the true slope Cᵏx°/(x̂+x°)², and the fixed point iterates x̂ with the prices, so it is exact at convergence. The exact charge is concave in x, so one QP cannot do it; the iteration can. x̂ is the bid the belief answered, `belief.dispatch.d_bid` (δ for the exogenous one); the Table 2 row is `Belief.consistent` (2026-10-23; it replaced the flags `d_hat`, `anticipate`, `voll`, `knows_share` on `best_response`); `Tariff.bill` keeps `d_hat` and `knows_share` since tariff.py cannot see the load. |
| beliefs | `Belief(dispatch, consistent)`, a frozen record with no methods (2026-10-23; the 2026-10-13 "no belief class" ruled out a class with behavior, not the report's 𝓜̃). A price-taker reads λ, μ, the pools, x̂ and its expected curtailment off `dispatch`; `consistent` is the Table 2 row. A price-setter's belief is the market itself (bilevel, not built): its dispatch will carry prices that are expressions of the bid, and `payoff` reads it unchanged; `planner` already embeds dispatch with the load's bid as a variable, which is its shape. The operator knows which belief the load holds (report §3); RQ4 relaxes that. |
| clearing | `clear` takes dᶠⁱʳᵐ as a vector from the type (`theta.d_firm`), not a tariff. The cost `C_sys` and the `constraints` are written once and shared by `clear`, `planner` and `S`. Net reserve X is its own variable so per-unit rows stay sparse. `clear` clips a negative offer to zero (a solver's −1e-10 on σ ≥ 0); the QPs return the solver's value. |
| curtailment | **a load type**, not a tariff (Erich, 2026-10-19): `LoadType.curtailable` declares a firm **level** dᶠⁱʳᵐ = (1−β) minₜ δₜ, constant over the window, as ERCOT SB6 and PJM Non-Firm Contract Demand use a MW level (2026-10-21; was a profile). The LP curtails only where κ > VOLL; unpaid, in exchange for connection. The planner holds the headroom instrument but consumes what it bids. τ₅'s reserve exemption is a tariff slot. |
| operating window | T hours from `start` (report: 𝒯); the week is the default instance, nothing is hard-coded to it. cⁱⁿᵛ is annual on the scenario and prorated by T/8760. A is one of the report's three matrices; a tariff's hours 𝒲ᵏ are a weight vector, `np.ones(T)` or `peak_hour(d_sys)`. |
| solver | Gurobi (academic license) for the LP and the QPs; 3× HiGHS on the clearing. `Market(solver="HIGHS")` and `best_response(..., solver=)` switch. |
| scenario knobs | carve-out α with the system's shape; **no flat or area profile** until an RQ needs it; tightness by `reserve_margin` at the tightest hour, scaling load not capacity; over a year one scale factor (`windows`), so only the annual peak window is at the margin. Outages and reserve offer costs were removed 2026-10-19; restore from git when an RQ needs them. |
| investment pool | annual missing money from the B0 run over the year, spread evenly (× T/8760); decided 2026-10-19. Not per window (negative in peak weeks), not allocated to scarcity weeks. |
| operator's objective | max-min welfare over Θ **without the inflexible load** (its welfare does not move with τ), or expected welfare under a prior; subject to g(ρ) ≤ 0 per layer or in total. **No regret** (Erich, 2026-10-21); `efficiency` = S^B1 − S^R is reported, not optimized. |
| named types | θ₀ inflexible, θ₁ mover, θ₂ controllable, θ₃ emergency, θ₄ curtailable; each run as a **data center** (ψ high, β medium, A = 1ᵀ) or a **bitcoin mine** (ψ low, β high, A = 0); the emergency row is fixed (ψ medium, β low, A = 0, p high). Level values are placeholders (#16). |
| repos | data from `rts-gmlc` (github.com/etrieschman/rts-gmlc, public, data only); never re-add a fetcher here. Tariff catalog lives in `docs/catalog/`. |
| parameter objects | frozen dataclasses throughout for now (arrays inside parameter objects); pydantic when a YAML config layer arrives with the experiment grids. |

## Layout

```
src/flexload/
  system.py   Scenario; scenario, windows, tighten, margin; ORDC.from_lolp; Dispatch; Market (ordc_for, C_sys, constraints, clear, marginal_cost); C_inv
  tariff.py   peak_hour; Marginal, Share, TwoPart; Tariff (bill, marginal); total; named_tariffs (τ₀)
  load.py     LoadType; PSI, BETA, P, BUSINESS; named_types; c_sigma; V; feasible; S; Belief; payoff; best_response; fixed_point; planner
  metrics.py  settle; recovery; alignment; fairness; respond; summary; table; tex
notebooks/walkthrough.py   jupytext cells; the documentation
tests/        conftest (3-generator, 4-hour scenario); test_system, test_tariff, test_load
docs/         assumptions.md (every non-report choice, one line each); catalog/large_load_arrangements.md (designations), catalog/bill_decomposition.md (every ERCOT charge)
```

Imports run one way: system ← tariff ← load ← metrics.

## Status (2026-10-23)

- 2026-10-23: `Belief(dispatch, consistent)` replaces the flag beside the dispatch;
  `payoff` is V − B on the expected outcome and `best_response` builds the tildes;
  the σ clip moved from the QPs into `clear`. 36 tests pass.
- Evening 2026-10-21: Erich read load.py and metrics.py. `C_inv` is floored at zero
  (a market whose prices overpay the fleet bills zero on the investment layer); the
  reserve margin default is 0.15, where ERCOT's annual rents pay the fleet's fixed cost
  (2,516 vs 2,500 M$) and PJM is short 1,057 M$; `payoff` and `best_response` take
  `b0` so ex-ante pools are fixed at C(δ, 0) under every belief. At 15% week 31 has a
  0.229 margin and one hour of μ > 0; the scarcity story lives in week 32 or at a
  higher α. Results for §4 are not yet run.
- 36 tests pass. Refactored 2026-10-19 (four files, one number system, the bill reads a
  dispatch, curtailment is a type, window not week, Gurobi) and aligned to the report
  2026-10-21 (firm level, named types by business, c^σ, C_energy, credit slot, τ₅,
  welfare rules, efficiency and price_error columns). Erich's system.py review
  2026-10-21: one cost formula `C_sys`, Π on the dispatch, bid/outcome names, `C_inv`
  not missing money, ORDC fit from the data's forecast error, κ and single-use helpers gone.
  With Gurobi: clearing ≈ 1.3 s, planner ≈ 2–3 s.
- Built: both reserve constructs, short and long run, the curtailable type, the three
  charge forms, ex-ante and ex-post costs, the price-taker QP (posted rate or known
  share), the consistent fixed point, the planner, the outcomes, the operator table
  and two welfare rules with a recovery constraint. Only
  τ₀ is defined. Erich's reviews of system.py, tariff.py (2026-10-21) applied; load.py
  and metrics.py cleaned to the same criticisms before his read.
- Not built: the price-setter (bilevel); 𝒦ʳᵉˢᵖ (a filter over bill layers); experiment
  grids over 52 weeks and seeds; figures beyond the walkthrough's one.

### Findings from the first run (worth the memo's attention)

1. **The consistent price-taker cycles under ERCOT.** The load leaves the 32 scarcity
   hours, scarcity vanishes, prices fall, the load returns. The map from prices to
   response to prices has no fixed point in pure strategies when the load's tolerance
   band straddles a merit-order step at the peak, which is the memo's own condition
   for price-taking to stop being exact (Section "Load's beliefs"): the load is large
   enough to change the marginal unit. `fixed_point(damping=None)` averages the
   iteration and `history` shows whether it settled. Erich (2026-10-13): nothing wrong
   with the cycle; it is the point of RQ3(b).
2. **Resolved 2026-10-19: the investment pool is annual.** Weekly missing money went
   negative in the peak week (rents ≈$195M against a ≈$16M weekly cost share, pool
   −$178M), so under every tariff with an investment layer, τ₀ included, the layer
   paid the load to consume at the peak. Now Ĉⁱⁿᵛ comes from a 52-week B0 run under
   one tightness scale and is spread evenly. Allocation to scarcity weeks stays an
   option for a later RQ.
3. **Resolved: other load now sheds at VOLL** (`Dispatch.shed`, in `C_sys`). Before
   this, PJM's hard requirement was slack above ~7% margin and infeasible below, so
   the tightness sweep had no room. Now λ and μ reach VOLL in shortage hours in both
   markets.
4. Under ERCOT, `C_sys` includes −Σ∫π, which is large and negative when reserve is
   free; regret is a difference, so it cancels there, but absolute welfare numbers
   under ERCOT are not comparable to PJM's.
5. **Resolved, revised 2026-10-19: B1 for a curtailable type holds the headroom
   instrument** (d − dᶠⁱʳᵐ counts toward reserve) but consumes what it bids. Letting
   the planner consume below its bid let it dodge energy conservation (S^B1 exceeded
   any realized S by 5% on the test scenario). Curtailment below the bid is the
   operator's scarcity action only.
6. The fixed point: `damping=0.5` (default) converges in ~17 steps on PJM; under
   scarcity use `damping=None` (harmonic), ~1 MW in 20 steps at 3.5 s each.
7. Week 31, ERCOT, exogenous price-taker: τ₄ (two-part investment) wins both choice
   rules for the mover; the menu τ₆ wins for the mover and loses for the CLR, which
   must give up reserve sales to elect the curtailable option.

## Next steps, in order

1. Decisions from Erich (below), then the memo sentences they imply (now also: Ĉⁱⁿᵛ is
   annual on the B0 path, prorated 1/52; tightness is set at the annual peak).
2. `experiments/`: config grids for RQ1–RQ3 over 52 weeks and outage seeds; cache by
   config hash; the figure list. pydantic configs arrive here.
3. Price-setter: embed `market.constraints` as KKT conditions in the load's problem
   (regime enumeration first, hour-wise under linear costs, coupled through A).
4. 𝒦ʳᵉˢᵖ as a filter over the bill's layers in `best_response`.
5. Replace placeholders: investment costs (#1), ORDC from LOLP (#3), named-type values (#16).
6. Operator learning slot (`Operator.update`) only when a study needs it.
7. Rewrite finding 1 as a proposition in the memo: the fixed point exists iff the tolerance band lies within one merit-order step at every hour it binds.

## Decisions needed from Erich

1. Resolved 2026-10-21: the investment pool is annual, spread evenly, floored at zero;
   the margin is calibrated so ERCOT's prices pay the fleet. A memo sentence each.
2. Placeholders to replace before the paper: investment costs by category, the ORDC
   shape (from LOLP), named-type values (ψ, β, p), β_firm. Fine for Workshop 1.
3. Two memo sentences: the rate-taker reading of the price-taker, and V(d, σ) with the
   reserve payment as a bill credit.
