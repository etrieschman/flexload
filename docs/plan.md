# flexload — repo plan

Planning document, last revised 2026-10-13. Nothing in this repo is code until Erich
approves each piece in chat. The model's source of truth is
`~/dev/incubator/flexible_loads/overleaf/6_S974/wargame_master.tex` (the memo); this
file decides how the memo becomes a codebase that serves the 6.S974 wargame first and the
flexible-loads research stream after it. Notation is the memo's.

## 1. The ask

A reproducible Python testbed for the memo's game: the operator commits to a tariff τ,
the load best-responds under a belief about dispatch, the market clears, a bill settles,
four metrics are read. It must

- run the Workshop 1 instance: RTS-GMLC aggregated to one node, one week at hourly
  resolution, clearing in both reserve constructs, the load's best response under
  price-taking beliefs, B0/B1/R under τ₀ for one type;
- grow to the 20–50 configurations of the memo's experiment section, over 52 weeks and
  outage seeds, with means, spread and tails;
- include a learning component on the load's side (course requirement);
- meet the course deliverables: parameters editable, strategies selectable, single run or
  batch, actions and metrics saved, figures reproducible, an explicit game specification;
- outlive the class: new tariffs, layers, types, markets, data sources and a second
  strategic player are additions, not rewrites.

## 2. The concerns

1. Encoding the switches (reserve construct, horizon, tariff slots, type, price belief,
   curtailment belief, operator knowledge, peak window, cost basis) once each, in one
   obvious place, so the code reads like the memo.
2. Beliefs that are instantiable in a line and cannot leak what the player does not know.
3. One bill that serves the load's objective, settlement, and the alignment metric, with
   ex-ante versus realized handled cleanly.
4. Learning that lives in the belief without making the static case a second code path.
5. The peak window as the archetype: known ex ante; set ex post and revealed at bill time;
   set ex post and never revealed; learned.
6. Too many options. Each new option must be an enum value or a vector, never a code path,
   and is added only when a research question needs it.

## 3. Repos (decided)

- **flexload** (this repo), sibling of `ftr_align` and `ercot-mis`; uv, pyproject, pytest,
  polars, cvxpy with HiGHS/CLARABEL; a `CLAUDE.md` with the notation table and locked
  decisions; a toy oracle in tests. Overleaf stays where it is. The tariff catalog now
  lives in `docs/catalog/`.
- **rts-gmlc** (`~/dev/rts-gmlc`, public, `github.com/etrieschman/rts-gmlc`): data only.
  Pinned commit, SHA256 manifest, polars tables with snake_cased headers, one derived
  table `offer_blocks()`. ftr_align consumes it as of 2026-10-13; flexload will too. The
  node-breaker RTS-GMLC planned for winter 2026 is a second `Dataset` there.

## 4. The objects, in the memo's words

Parameter objects (enums and scalars that come from config grids) are pydantic models;
computational objects that hold arrays are frozen dataclasses. Computation is functions.
Polymorphism only where variants differ in computation: the reserve construct, the learner.

| object | memo | contents |
|---|---|---|
| `Scenario` | ω and δ | `d_other[t]`, generator `c_u, c_r, c_inv, cap[j]` after outages, renewable availability, the load's preferred profile `delta[t]`; one week |
| `Market` | ERCOT / PJM | reserve construct (`Hard` or `ORDC(curve)`), γ, VOLL, horizon (short / long run); `clear(scenario, tariff, bid) -> Dispatch` |
| `LoadType` | θ | ψ, β, window matrix `A`, p, `responds_to ⊆ {energy, reserve, investment}`, `sells_reserve`; named types from the catalog |
| `Tariff` | τ | per cost-share layer: `window`, `cost_basis`, `rate_form`; tariff-wide: `curtailment` (sets dᶠⁱʳᵐ), `structure`; named τ₀…τ₆; `Menu(options)` |
| `Bid` | (d, σ) | `d[t]`, `sigma[t]` |
| `Dispatch` | 𝓜_ω(d, σ) | `u, r, sigma, d, lam, mu, nu, eta` and the per-layer marginal system cost κ; `sigma` is cleared reserve, `d` realized consumption |
| `Belief` | 𝓜̃ | a `Dispatch`-shaped object whose entries are constants, the bid itself, a probability vector (the window), or the true map; plus the posted rates r̄ᵏ |
| `Bill` | B | per-layer charges including the reserve credit |
| `Operator` | — | tariff set, type set, information (full / partial / prior), announcement (the posted constants) |
| `Config` | one experiment row | everything above by name; serializable; hashed for caching |

**No suffixes for tildes or hats.** The container carries the decoration: `dispatch.lam`
is λ, `belief.lam` is λ̃, `ex_ante.lam` is the ex-ante value. One set of field names
everywhere. `lam` because `lambda` is a keyword.

**Clearing takes the tariff.** dᶠⁱʳᵐ is a tariff slot and whether the load may offer
reserve follows from type and tariff together, so `clear(scenario, tariff, bid)`.
Everything else in the tariff is a *reading* of a dispatch, not an input to it.

**The bill reads a dispatch; the tariff does the reading.** Pools Cᵏ are functions of
μ, r, σ, ν; bases xᵏ are functions of d and the window; other loads' bases x∘ are
functions of d° and the window. `bill(tariff, d, dispatch, d_other)` composes two small
readers on the tariff, pools-from-dispatch and bases-from-consumption, and returns a
`Bill` with components. The same call runs with a belief in the dispatch slot. The
reserve payment is a layer of the bill (a credit, the catalog's `supply` layer), so the
load's payoff is `V(d) − cˢᵀσ − B`, with cˢ the load's own cost and not a bill item.

**What the load is told.** The load does not know ω, so x∘ and the ex-ante pools it
needs come from the operator's announcement (what ERCOT posts as load-ratio shares), never
from the scenario. A `Belief` is built from an announcement; only `Belief.setter(scenario)`
takes the scenario, explicitly, for the price-setter.

## 5. Beliefs

The memo's three price cases are one object with three ways of filling it:

| case | λ̃, μ̃ | rate r̃ᵏ | how the constants are set |
|---|---|---|---|
| exogenous price-taker | constants | constants | from the clearing at (δ, 0) |
| consistent price-taker | constants | constants | fixed point: solve, clear at the response, update, repeat |
| price-setter | the true maps | the true map Cᵏ·xᵏ/(xᵏ+x∘ᵏ) | needs ω |

**Rate-taker (decided).** A price-taker takes the per-layer rate r̄ᵏ = Cᵏ/(x̄ᵏ + x∘ᵏ) as
given, exactly as it takes λ̄. Taking only C and x∘ as given leaves C·x/(x+x∘), concave
in x, and the load's problem stops being a QP. With rates given every layer is linear in d
and the best response is a QP; the consistent price-taker closes the fixed point on r̄ as
on λ̄. Two consequences: the ex-ante versus realized basis bites only through the fixed
point or the setter, as it already does for λ; and at settlement the true marginal charge
of the share form is C·x∘/(x+x∘)², not r̄, so the gap between the average rate the load
faced and the marginal it caused is an alignment result. This belongs in the memo as one
sentence. An exact route exists for the investment layer, whose base is a scalar: fix the
base, solve the QP, line-search over the base. Note it; do not build it until asked.

**Mixed beliefs.** Because the belief is per field, a load can be a price-taker on λ and
a setter on μ without any new structure. The cost is in the solver, not the
representation: all fields constant gives the QP path; any true-map field gives the
bilevel path. Supported by construction, not planned for.

**The peak window.** The window belief is a probability vector over hours. Known is
one-hot; a wrong forecast is a different one-hot; unknown is uniform or a prior; learned is
a running count. The expected investment charge is linear in the weights, so the QP
survives all four cases. In the memo's terms: the window 𝒲 is a tariff slot (ex ante or ex
post), 𝒲̃ is the load's belief, and learning updates 𝒲̃ between weeks.

**Curtailment belief** follows the memo's table unchanged: `belief.d` is the bid, the true
map, or dᶠⁱʳᵐ where κ̄ ≥ VOLL.

## 6. Scenario knobs (decided where marked)

- **Flexible share α (decided).** Carve-out: δ = α × profile and d° = total − δ, so the
  B0 system load equals the data and tightness does not move with α. `profile` is the
  system total by default, with an area's profile as the option (RTS-GMLC has three
  areas; bus profiles are area profiles scaled). No flat option until a question needs
  it, and then it is one more enum value, not a code path. The memo keeps α for the
  flexible share and drops αᵏ from the bill by writing the fraction out.
- **Tightness (proposed).** One knob with a target rather than a scale factor: the
  planning reserve margin at the weekly peak, `reserve_margin = Σⱼ capⱼ / max_t d^sys_t − 1`.
  Implemented by scaling d° (after the carve-out, so α is unaffected), not by derating
  capacity, because scaling load keeps unit sizes, the largest-unit contingency and the
  merit order intact. In the long run tightness is endogenous and the knob does not apply.
  Measure RTS-GMLC's actual weekly margins before choosing targets; the system is slack.
- **Outages.** Seeded draws from `for`, `mttf`, `mttr` in `gen`; derate `cap[j]` per hour.
- **Week.** 52 weekly slices of the day-ahead series; the real-time series is available
  for later.

## 7. Clearing

An LP with a pluggable reserve term and a horizon flag. The hard requirement and the ORDC
differ only in the reserve term: a constraint versus a piecewise-linear concave penalty.
The construct is a small object with `reserve_terms(vars) -> (objective terms,
constraints)`. The long run frees `y`. Mandatory curtailment adds the dᶠⁱʳᵐ ≤ d ≤ bid
block and the VOLL term. The LP is compiled once with cvxpy Parameters for the bid and
re-solved across the fixed point and the 52 weeks. Duals at degenerate points depend on
the solver; pick one and record it in `docs/assumptions.md`, as ftr_align does.

**The builder is not the solver.** The constraints are assembled by a function that
accepts numpy or cvxpy arguments; `clear` calls it and solves. The price-setter embeds
the same constraints as KKT conditions inside the load's problem, and if they only existed
inside `clear` the LP would be retyped. This is the ftr_align pattern.

## 8. The load's problem

One function assembles the objective and constraints given (θ, τ, belief) and returns
cvxpy pieces; `best_response` dispatches on the belief: all constants gives the QP, any
true map gives the bilevel path. The three price cases, the planner B1 and B0 enter through
that one door.

- Constant beliefs are cvxpy Parameters, not numbers, so the consistent fixed point and
  the weekly learner re-solve without recompiling.
- Per-hour terms and the coupling terms (`A`, and V if it ever stops being a sum of
  squares) are assembled separately. Under linear costs λₜ is a step function of dₜ, so
  the price-setter is hour-wise piecewise with coupling only through `A`, and regime
  enumeration is available before anyone touches an MPEC. Under ORDC μ is piecewise linear
  in d, so a smooth surrogate is the natural route there.
- Under a menu the load's response is the best over options: a loop, not a solver.

## 9. Learning

The load learns two things, both beliefs: hour-of-week price levels (recursive averaging
over observed weeks) and the window distribution (counts over observed peak hours). A
`Learner` has `update(belief, observation) -> belief`; `Static` returns its input. One loop:

```
for week in weeks:
    bid      = best_response(type, tariff, belief)
    dispatch = market.clear(scenario[week], tariff, bid)
    bill     = bill(tariff, dispatch.d, dispatch, d_other)
    belief   = learner.update(belief, observe(dispatch, bill, announcement))
```

What the load observes is a config choice (prices; the bill; the realized peak hour or
not), which is how "revealed at bill time" and "never revealed" differ. Two course
questions fall out: with an ex-post window and a large load the realized peak moves when
the load avoids its believed peak, so counts can cycle (the 4CP chase); and the operator's
announcement is an information-channel defense, implemented as a better initial belief.
The operator makes no sequential decision in this research; `Operator` gets an optional
`update(observation)` defaulting to static so a later study can add type inference without
touching the loop.

## 10. Operator

Enumeration: for each tariff in the set and each type in the type set, best response,
clearing, regret, recovery; min over tariffs of max over types with the recovery bound as a
filter; expected regret under a prior. Cache by config hash since (type, tariff, week)
triples recur across research questions.

## 11. Layout

```
flexload/
  pyproject.toml  CLAUDE.md  README.md
  docs/
    game_spec.md        the explicit game specification (course deliverable 2)
    catalog/            layers.yaml, schema.yaml, rate_structure.md, large_load_arrangements.md
    assumptions.md      every modeling assumption, status, how checked
  src/flexload/
    __init__.py         the working set, ~20 names
    scenario.py         Scenario; toy scenarios
    data.py             rts_gmlc tables -> weekly Scenario (aggregate, carve-out, outages, tightness)
    market.py           Market, reserve constructs, clear; the LP builder
    types.py            LoadType, window builders, named types
    tariff.py           enums, layer spec, Tariff, Menu, named tariffs; pools and bases readers
    bill.py             bill(tariff, d, dispatch, d_other) -> Bill; marginal charges
    belief.py           Belief: from_announcement, setter; Dispatch-shaped
    response.py         best_response (QP; bilevel later), planner B1, B0, consistent fixed point
    learn.py            Learner: Static, PriceAveraging, PeakCounts
    episode.py          the weekly loop -> Trace
    operator.py         regret, menus, min-max, expected regret
    metrics.py          the only module that labels rows and returns DataFrames
    experiments/        config grids for RQ1..RQ3, batch runner, cache
  notebooks/            jupytext scripts
  tests/                toy oracle; invariants
```

Tests encode the memo's propositions on the toy: B0 feasible for every type;
S* ≥ Sᴿ ≥ Sᴮ⁰; share-form recovery zero by construction; two-part lump sums restore
recovery; price-taking exact when the tolerance band sits inside one merit-order step; the
consistent fixed point reproduces its own prices and rates; a menu under full information
elects the intended option.

## 12. Seams for later

Node axis of length one in `Scenario` arrays; `clear` takes a list of bids; the layer enum
is open (adequacy, transmission, hedge from the catalog; the catalog's four rate forms map
onto `rate_form`); a second `data_*.py` for ERCOT via ercot-mis; storage and ramping as
constraint rows; retail interposition as a base transform; `Operator.update`.

## 13. Build order to Workshop 1

1. `Scenario` + toy; `Market` and `clear` for both constructs, short run, no curtailment.
2. `LoadType`, `Tariff`, named registries; `bill` and its marginals.
3. `Belief.from_announcement`, exogenous and consistent fills, `best_response` QP, B0/B1.
4. `episode` with `Static`; `metrics`; the first instance on RTS-GMLC.
5. Then curtailment, menus, learners, long run, operator enumeration, grids, setter last.

## 14. Decisions log

- 2026-10-13: new repo `flexload`; catalog moved here; `rts-gmlc` split out and public;
  tildes and hats on containers; `clear` takes the tariff; reserve payment is a bill
  credit; rate-taker reading of the price-taker; carve-out α with system profile default
  and area option, no flat; pydantic for parameters, dataclasses for arrays.
- Open: tightness knob (§6 proposal); mixed beliefs are supported but not planned.
