# Assumptions

Every modeling choice that is not in the memo, with its status. Update in the
same commit as the code that changes it.

| # | assumption | where | status |
|---|---|---|---|
| 1 | **Investment costs** by RTS-GMLC category are placeholders ($/kW-yr: nuclear 600, coal 350, CC 110, CT 80, oil ST 300, hydro 300, wind 140, PV 90, CSP 500), prorated to the week by /52. RTS-GMLC has no capital costs. | `scenario.INVESTMENT_COST_PER_KW_YEAR` | placeholder; replace with a cited table before any result depends on the investment layer |
| 2 | **Missing money** is weekly: Σⱼ (cⁱⁿᵛⱼ/52 − Σₜ νⱼₜ) ūⱼ. In a peak week scarcity rents exceed the weekly cost share and the pool is negative. The memo's todo on proration is open. | `Market.pools` | decision needed (see CLAUDE.md) |
| 3 | **Default ORDC** is a step curve at fractions of the largest unit's nameplate (0.25, 0.25, 0.5, 1.0, ∞) priced at fractions of VOLL (1, 0.5, 0.2, 0.05, 0). Not derived from LOLP. Under ERCOT, C_sys includes −Σₜ∫π, which is large and negative when reserve is free. | `DemandCurve.default` | placeholder; build from LOLP |
| 4 | **ERCOT formulation**: no per-unit contingency row; load-following γ d_sys is hard and only reserve above it is valued by the curve. PJM: one row per unit, largest running unit plus γ d_sys, hard. | `Market.constraints` | as the memo; the "vertical-curve limit" equivalence is not exact across the two |
| 5 | **Reserve offer cost** cʳ = 0 by default (`reserve_cost_fraction`). RTS-GMLC has none. | `build_scenario` | default |
| 6 | **Excluded units**: Storage, Sync_Cond, CSP (no single-period model). Hydro is treated as a variable unit capped by its day-ahead series. | `scenario.EXCLUDED_CATEGORIES` | default |
| 7 | **Outages**: a two-state Markov chain per thermal unit per hour with rates 1/mttf and 1/mttr, started from the stationary distribution implied by `for`; none unless `outage_seed` is set. | `scenario._availability` | default |
| 8 | **Carve-out**: δ = α × weekly system energy × profile shape; d° = total − δ. System load at B0 equals the data. | `build_scenario` | decided 2026-10-13 |
| 9 | **Tightness**: `reserve_margin` scales both loads so the *tightest hour* has that margin. Feasibility needs margin ≥ γ + (PJM) largest unit share of load, since other load cannot be shed. | `with_reserve_margin` | decided; the PJM band between slack and infeasible is narrow |
| 10 | **Rate-taker**: a price-taker takes each cost-share layer's average rate as given at `d_hat` (δ for the exogenous case, the previous iterate for the consistent case). At settlement `d_hat = d` and the share form is exact. | `Tariff.bill` | decided 2026-10-13; one sentence due in the memo |
| 11 | **Two-part lump sum** T = (share of expected base) × (pool − φ × expected total base), with the expected base at `d_hat`. φʳᵉˢ = γμₜ, φⁱⁿᵛ = 0 as the memo sets them. `T` may be given explicitly. | `TwoPart.lump_sum` | decided; apportionment rule is the memo's open todo |
| 12 | **Everyone else's bill** Φ∘ is the same tariff with d and d° swapped, no credit, no exemption. | `metrics.settle(own=False)` | default |
| 13 | **Offer where it will not clear**: the load offers σ = 0 in hours where μ̄ < cˢ, as the memo states, rather than leaving the QP indifferent. | `best_response` | as the memo |
| 14 | **Curtailment anticipation** uses κ̄ ≥ VOLL from the belief's prices, the memo's price-taker row. | `fixed_point`, `respond` | as the memo |
| 15 | **Solvers**: HiGHS (simplex, vertex duals) for the LP; CLARABEL for the QP and the planner. Duals at degenerate merit-order points are solver-dependent. | `Market.solver`, `best_response` | default; record if changed |
| 16 | **Named types** (ψ=1, β, p): inflexible (0, 0), mover (0.2, 0), CLR (0.2, 0.02, sells), ERS (0.05, 0.2, sells). Weekly energy conservation for all but inflexible. | `named_types` | placeholder values |
| 17 | **Named tariffs** use β_firm = 0.2 and the ex-ante peak hour from the B0 path as the curtailable hour and the investment window. | `named_tariffs` | as the memo |
| 18 | **Long run**: y ≥ 0 per offer block against the block's availability shape; no minimum build, no retirement cost. | `Market.constraints` | default |
