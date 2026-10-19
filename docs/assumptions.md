# Assumptions

Every modeling choice that is not in the memo, with its status. Update in the
same commit as the code that changes it.

| # | assumption | where | status |
|---|---|---|---|
| 1 | **Investment costs** by RTS-GMLC category are placeholders ($/kW-yr: nuclear 600, coal 350, CC 110, CT 80, oil ST 300, hydro 300, wind 140, PV 90, CSP 500), annual on the scenario, prorated by T/8760 where used. RTS-GMLC has no capital costs. | `system.INVESTMENT_COST_PER_KW_YEAR` | placeholder; replace with a cited table before any result depends on the investment layer |
| 2 | **Missing money** is annual: Ĉⁱⁿᵛ = Σⱼ (cⁱⁿᵛⱼ − Σ_{t∈year} νⱼₜ) ūⱼ on the B0 path over `periods(...)`; the period's investment pool is Ĉⁱⁿᵛ·T/8760, the same in every period. Cached in `~/.cache/flexload/missing_money` by market fields and the year's loads. Rejected: the week's own missing money (a peak week's rents exceed its cost share and the pool goes negative, −$178M on week 31) and allocating to scarcity weeks (keep in reserve if an RQ needs it). | `Market.missing_money`, `system.missing_money` | decided 2026-10-19 (Erich) |
| 3 | **Default ORDC** is a step curve at fractions of the largest unit's nameplate (0.25, 0.25, 0.5, 1.0, ∞) priced at fractions of VOLL (1, 0.5, 0.2, 0.05, 0). Not derived from LOLP. Under ERCOT, C_sys includes −Σₜ∫π, which is large and negative when reserve is free. | `DemandCurve.default` | placeholder; build from LOLP |
| 4 | **ERCOT formulation**: no per-unit contingency row; load-following γ d_sys is hard and only reserve above it is valued by the curve. PJM: one row per unit, largest running unit plus γ d_sys, hard. | `Market.constraints` | as the memo; the "vertical-curve limit" equivalence is not exact across the two |
| 5 | **Reserve offer cost** cʳ = 0. RTS-GMLC has none; the knob was removed 2026-10-19. | `scenario` | default |
| 6 | **Excluded units**: Storage, Sync_Cond, CSP (no single-period model). Hydro is treated as a variable unit capped by its day-ahead series. | `system.EXCLUDED` | default |
| 7 | **Outages**: none. The Markov-chain option was removed 2026-10-19 (git 171cf6e has it); restore when an RQ replicates over outage seeds. | — | removed |
| 8 | **Carve-out**: δ = α × system load, hour by hour; d° = total − δ. System load at B0 equals the data. Area profiles removed 2026-10-19. | `scenario` | decided 2026-10-13 |
| 9 | **Tightness**: `reserve_margin` scales both loads so the *tightest hour* has that margin. In `periods(...)` one scale factor serves the year, so the annual tightest hour has the margin and other periods keep their seasonal slack; `scenario(reserve_margin=)` on one period scales that period alone. | `tighten`, `periods` | decided; annual scaling 2026-10-19 |
| 9b | **Other load sheds at VOLL** when capacity is short (`Dispatch.shed`), a real cost in C_sys; λ and μ reach VOLL in those hours. | `Market.clear` | decided 2026-10-13 |
| 10 | **Rate-taker**: a price-taker takes each cost-share layer's average rate as given at `d_hat` (the belief's consumption: δ for the exogenous case, the previous iterate for the consistent case, the averaged path for the learner). At settlement `d_hat = d` and the share form is exact. | `Tariff.bill` | decided 2026-10-13; one sentence due in the memo |
| 11 | **Two-part lump sum** T = (share of expected base) × (pool − φ × expected total base), with the expected base at `d_hat`. φʳᵉˢ = γμₜ, φⁱⁿᵛ = 0 as the memo sets them. `T` may be given explicitly. | `TwoPart.lump_sum` | decided; apportionment rule is the memo's open todo |
| 12 | **Everyone else's bill** Φ∘ is the same tariff with d and d° swapped, no credit, no exemption. | `settle(own=False)` | default |
| 13 | **Offer where it will not clear**: the load offers σ = 0 in hours where μ̄ < cˢ, as the memo states, rather than leaving the QP indifferent. | `best_response` | as the memo |
| 14 | **Curtailment anticipation** uses κ̄ ≥ VOLL from the belief's prices, the memo's price-taker row. | `respond(anticipate=True)`, `fixed_point` | as the memo |
| 15 | **Solvers**: Gurobi for the LP and the QPs (academic license; 3× HiGHS on the clearing, identical duals on week 31). Duals at degenerate merit-order points are solver-dependent. | `Market.solver`, `best_response(solver=)`, `planner(solver=)` | changed 2026-10-19 |
| 16 | **Named types** (ψ=1, β, p): inflexible (0, 0), mover (0.2, 0), CLR (0.2, 0.02, sells), ERS (0.05, 0.2, sells), curtailable (0.2, 0, curtailable). Energy conserved over the period for all but inflexible. | `named_types` | placeholder values; Erich to set from the ERCOT rules |
| 17 | **Named tariffs** use the ex-ante peak hour from the B0 path as the investment window. τ₅ is gone: the firm level is the curtailable type's. | `named_tariffs` | as the memo, less τ₅ |
| 19 | **Planner for a curtailable type** holds the headroom instrument, d − (1−β)δ toward reserve in every hour, but consumes what it bids: letting it consume below the bid let it dodge energy conservation (S* exceeded any realized S by 5% on the test scenario). Curtailment below the bid is the operator's scarcity action only. | `planner` | revised 2026-10-19 |
| 20 | **Curtailable firm level** dᶠⁱʳᵐ = (1−β)δ in every hour, β the type's own tolerance; the LP curtails only where κ > VOLL. Not a peak-hour mask, not a separate β_firm. | `LoadType.d_firm` | decided 2026-10-19 (Erich: curtailment is a type) |
| 18 | **Long run**: y ≥ 0 per offer block against the block's availability shape; no minimum build, no retirement cost. | `Market.constraints` | default |
