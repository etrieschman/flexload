# How a wholesale load's bill is built

Every charge on the bill, one layer at a time, for ERCOT. Each layer is a pool of dollars, a base that is measured, and the charge that results. Every formula is taken from source text and carries a citation and a quotation. Protocol vintage **1 August 2026** unless a record says otherwise; status not re-verified since. The companion inventory of load designations is `large_load_arrangements.md`.

This file replaces `layers.yaml`, `schema.yaml`, `render.py`, `index.html` and `rate_structure.md` (all in git before 2026-10-21); the records below were generated from the yaml once and are now maintained here.

---

## 1. Notation

The unit is the entity the market bills, written $e$: the scheduling entity for almost every layer, the distribution utility for transmission. Every formula indexes by that entity and every determinant is computed across its whole portfolio, so a truncation at zero or a load-ratio share applies to the portfolio, not to one load inside it. How a charge then reaches an individual load is a retail question this document excludes.

| symbol | meaning |
|---|---|
| $k$ | The layer. Superscript on the base, the charge and the pool, so x^k, Phi^k and C^k always belong to the same record. |
| $e$ | The entity the market bills - the scheduling entity for almost every layer, the distribution utility for transmission. Not an individual load. |
| $e^{\prime}$ | Another such entity. Appears only in the denominators that turn a pool into a share. |
| $n$ | A node - a single point on the transmission network. ERCOT calls these Electrical Buses; node is used here because that is the term the wider literature uses for the same object. |
| $z$ | A Load Zone - a group of nodes ERCOT prices together. Load settles against the zone rather than the node, so the zone is also the settlement point for load. Used bare, z ranges over the whole zone, which is what prices are averaged across; determinants instead range over the entity's own zones, written Z_e. |
| $\mathcal{N}_{z},\; \mathcal{T}_{t},\; \mathcal{M},\; \mathcal{A},\; \mathcal{V},\; \mathcal{E}$ | Sets are calligraphic capitals, their elements the matching lowercase letter. In order: the nodes making up zone z; the intervals making up a span, written T_t for the dispatch intervals inside settlement period t and T_{m,y} for the settlement intervals inside month m of year y; the four summer peak months; the ancillary service products; the real-time money flows; and all billed entities. A sum over any of these ranges over the whole system. |
| $\mathcal{N}_{e,z},\; \mathcal{Z}_{e},\; \mathcal{P}$ | The entity-scoped sets: the nodes inside zone z at which entity e serves load, the zones in which it serves load, and the service periods of a contract it is billed across. Determinants sum over these, never over the system-wide sets - an entity is billed on its own load, not on everything inside a zone it happens to occupy. The distinction carries the content of the energy layer, where the base sums the entity's own nodes while the price multiplying it is averaged over every node in the zone, whoever serves load there. |
| $t,\; s$ | The settlement period being billed, and a dispatch interval inside it (s in T_t). Settlement period length varies by layer - fifteen minutes, an hour, a month - and each record states which under its measurement window. ERCOT redispatches roughly every five minutes, so several s fall inside one t and prices must be averaged across them. |
| $m,\; y$ | Calendar month and year. Used only by the annual peak-demand layer. |
| $a$ | An ancillary service product. ERCOT procures five of them. |
| $\mathrm{AML}_{e,z,t}$ | Adjusted Metered Load - the quantity nearly every determinant in this inventory is built from, and not the same thing as metered consumption. ERCOT defines it as retail usage adjusted for unaccounted-for energy, transmission losses, distribution losses and DC tie exports, so it is larger than what the meter recorded. Losses are recovered by inflating this quantity rather than by any separate charge, which is why the loss layer is marked absorbed. Written with a node subscript instead of a zone subscript, as AML_{e,n,t}, in the one layer that works nodally. |
| $\mathrm{LRS}_{e,t}$ | Load Ratio Share - the entity's fraction of total truncated metered load in the same period, x^k_{e,t} divided by the sum of x^k over all entities. This one ratio allocates most pooled costs in ERCOT, which is why so many layers share a determinant: once an entity's consumption share is known, so is its share of nearly every pool. Shares sum to one by construction, because the denominator is the sum of the same truncated quantities that form each numerator. Contemporaneous unless a record says otherwise. |
| $\max(0,\;\cdot)$ | The truncation ERCOT applies to an entity's metered load in each of its zones before summing them. An entity whose load nets negative in one zone is treated as zero there rather than credited, so shares are built from truncated quantities and not from net load. |
| $x^{k},\; \Phi^{k},\; C^{k}$ | The base (what is measured), the charge (what is billed) and the pool (the dollars being recovered), for layer k. |

## 2. How every charge is built

One layer of the bill, for one entity, in one billing period. Every record in §4 is an instance of this.

$$\Phi^{k}_{e,t} \;=\; \underbrace{\sigma^{k}}_{\text{sign}}\; \underbrace{r^{k}_{t}}_{\text{rate}}\; \underbrace{x^{k}_{e,\,\mathcal{W}^{k}(t)}\!\left(d_{e}\right)}_{\text{base}}$$

$d_e$ is the entity's demand path, the only thing it controls. $t$ is the period billed; $\mathcal W^k(t)$ is the window the base is measured over. For most layers those coincide; where they do not is where the interesting layers live.

**The rate is a pool over an estimate of the base.**

$$r^{k}_{t} \;=\; \frac{C^{k}_{t}}{\hat{X}^{k}_{t}} \qquad\text{where}\qquad \hat{X}^{k}_{t} \;=\; \text{the total base the rate was built on}$$

That one choice, which denominator the rate was built on, decides recovery. Collections and the residual both fall out of it:

$$\sum_{e\in\mathcal{E}}\Phi^{k}_{e,t} \;=\; C^{k}_{t}\,\frac{X^{k}_{t}}{\hat{X}^{k}_{t}} \qquad\Longrightarrow\qquad R^{k}_{t} \;=\; C^{k}_{t}\left(1-\frac{X^{k}_{t}}{\hat{X}^{k}_{t}}\right)$$

So there is no separate true-up mechanism. A true-up is a rate whose denominator is revised to the realised base.

**Five ways the denominator is chosen.** Figures in the examples are illustrative.

| denominator | form | residual | example | layers |
|---|---|---|---|---|
| $\hat{X}=X$ | **Realised base.** Rate is built from the same period it bills, so shares sum to one. | $R = 0$ | Black start. Pool $50,000 for the hour; ERCOT load 45,000 MWh; yours 90 MWh. Rate $1.11/MWh, you pay $100. Nothing left over. | reactive supply, black start, firm fuel, reliability must-run |
| $\hat{X}\to X$ | **Provisional, then revised.** Rate is set on an estimate, then recomputed on the realised base and the difference settled. | $R \to 0$ | Ancillary services. Day-ahead you are billed on last week's comparable hour, say a 0.24% share. Settlement recomputes on the realised 0.20% and refunds the gap. | ancillary services, emergency response, congestion rights |
| $\hat{X}\ \text{frozen}$ | **Stale denominator.** Rate stays in force while the billing base is refreshed, so the two drift apart. | $R \neq 0$, deferred | Transmission. Rate set when ERCOT peak was 80 GW; billed on this summer's 85 GW. Collections run 6.25% above the cost of service until the next rate case. | transmission network service |
| $\text{no}\ \hat{X}$ | **Posted rate.** A published per-unit figure. No denominator was ever divided, so nothing ties collections to the pool. | $R \neq 0$, never reconciled | System administration. $0.55/MWh times whatever load turns out to be, against whatever ERCOT spent. The fee is reset going forward, not backward. | system administration |
| $r \neq C/\hat{X}$ | **Capped share.** The rate is deliberately not the pool over the base, so a remainder is guaranteed. | $R > 0$ by design, transferred | Reliability commitment shortfall. Your shortfall share implies $1M but the cap holds you to $400k. The $600k becomes the uplift layer's pool and is spread over all load. | reliability commitment shortfall |

**Where a residual goes.** It is not absorbed into the rate. ERCOT disposes of it three ways, and two of them are separate bill items: it is recomputed away (the same charge, revised: ancillary services); it becomes another layer's pool (a new line item: the shortfall cap's remainder becomes uplift, and the market's imbalance becomes the surplus credit); or it persists, rolled forward or never reconciled (transmission until the next rate case; system administration, ever).

**The dominant case.** Eleven of the fourteen charged ERCOT layers are this one expression, with the residual identically zero:

$$\Phi^{k}_{e,t} \;=\; \sigma^{k}\,C^{k}_{t}\,\frac{x^{k}_{e,\,\mathcal{W}^{k}(t)}}{\sum_{e^{\prime}\in\mathcal{E}}x^{k}_{e^{\prime},\,\mathcal{W}^{k}(t)}}$$

The form is the first choice and decides whether the other dials exist. Only the average-cost form uses all of them: the sign $\sigma^k \in \{+1, -1\}$ (charge or credit); the base $x^k_e(d_e)$ (metered energy, peak demand, shortfall); the window (interval, hour, month, prior-year peaks); the pool $C^k$; and the residual (zero, a new layer, or unreconciled). A cleared price has no pool; a posted rate has a pool the charge never divides.

**What the space leaves out.** Theory points at a two-part tariff, a marginal part that carries the signal and a fixed part that recovers the rest without touching the margin, $\Phi_e = \lambda_t x_e + F_e$. ERCOT's shape has the marginal part and then recovers everything else on a usage share, $\Phi_e = \lambda_t x_e + \sum_k \sigma^k C^k x^k_e / \sum_{e'} x^k_{e'}$. The second term is never fixed: every pooled layer loads back onto usage. The vocabulary has the slots a fixed part would need, fixed, contracted capacity, non-coincident peak, and ERCOT uses none of them; eleven of its fourteen charged layers sit on metered energy.

---

## 3. The layers at a glance

| layer | status | billed to | base | timing | rate | exact recovery |
|---|---|---|---|---|---|---|
| [Energy and congestion](#energy-and-congestion) | charged | scheduling entity | metered energy | known as it happens | market clearing | n/a |
| [Marginal losses](#marginal-losses) | charged elsewhere (in energy and congestion) | scheduling entity | — | known as it happens | — | n/a |
| [Reliability commitment shortfall](#reliability-commitment-shortfall) | charged | scheduling entity | deviation | known as it happens | average cost | no |
| [Scarcity adder](#scarcity-adder) | charged elsewhere (in energy and congestion) | scheduling entity | — | known as it happens | — | n/a |
| [Ancillary services](#ancillary-services) | charged | scheduling entity | metered energy | known as it happens | average cost | yes |
| [Reactive supply](#reactive-supply) | charged | scheduling entity | metered energy | known as it happens | average cost | yes |
| [Black start](#black-start) | charged | scheduling entity | metered energy | known as it happens | average cost | yes |
| [Emergency Response Service](#emergency-response-service) | charged | scheduling entity | metered energy | known as it happens | average cost | yes |
| [Firm fuel supply](#firm-fuel-supply) | charged | scheduling entity | metered energy | known as it happens | average cost | yes |
| [Uplift](#uplift) | charged | scheduling entity | metered energy | known as it happens | average cost | yes |
| [Capacity obligation](#capacity-obligation) | no such charge | scheduling entity | — | known as it happens | — | n/a |
| [Transmission network service](#transmission-network-service) | charged | distribution utility | coincident peak | known only afterwards | average cost | no |
| [Interconnection upgrade assignment](#interconnection-upgrade-assignment) | charged | scheduling entity | TODO | known as it happens | TODO | TODO |
| [Regional project cost allocation](#regional-project-cost-allocation) | charged elsewhere (in transmission network service) | distribution utility | — | known as it happens | — | n/a |
| [Reliability must-run](#reliability-must-run) | charged | scheduling entity | metered energy | known as it happens | average cost | yes |
| [System administration](#system-administration) | charged | scheduling entity | metered energy | known as it happens | posted | no |
| [Congestion rights allocation](#congestion-rights-allocation) | charged | scheduling entity | metered energy | known as it happens | average cost | yes |
| [Loss and congestion surplus credit](#loss-and-congestion-surplus-credit) | charged | scheduling entity | metered energy | known as it happens | average cost | yes |

Fields still marked TODO were not yet read from source text when the yaml was frozen.

---

## 4. The layers

### Energy and congestion

**Charged.** Billed to the scheduling entity.

**Base** (metered energy; measured: The 15-minute Settlement Interval being billed.; billed: The same 15-minute Settlement Interval.; known as it happens).

$$x^{k}_{e,z,t} \;=\; \sum_{n \,\in\, \mathcal{N}_{e,z}} \mathrm{AML}_{e,n,t}$$

- $x^{k}_{e,z,t}$ (MWh per 15-min interval): The entity's own adjusted metered withdrawal inside one Load Zone, accumulated over one settlement interval. Zone-level because the price is set per zone - an entity holding load in several zones has one of these for each, and the charge sums over the zones it serves.
- $\mathcal{N}_{e,z}$ (—): The nodes inside Load Zone z at which this entity actually serves load - not every node in the zone. Contrast the price below, which is averaged over N_z, every node in the zone, regardless of who serves load there.

The protocol writes this determinant as an imbalance rather than as gross load: metered load net of whatever the load already bought in the day-ahead market, plus or minus self-schedules and energy trades. It is recorded here as gross metered load instead, because the day-ahead purchase is a fixed financial position that does not change with real-time behaviour. An extra MWh consumed in real time costs the load one times the real-time price no matter what it bought the day before.


**Pool.** —

**Rate** (market clearing; exact recovery: n/a).

$$\Phi^{k}_{e,t} \;=\; \sum_{z \,\in\, \mathcal{Z}_{e}} \mathrm{RTSPP}^{\mathrm{EW}}_{z,t}\; x^{k}_{e,z,t} \qquad\qquad \mathrm{RTSPP}^{\mathrm{EW}}_{z,t} \;=\; \max\!\left(\underline{\pi},\;\; \sum_{n \,\in\, \mathcal{N}_{z}}\ \sum_{s \,\in\, \mathcal{T}_{t}} \mathrm{LMP}_{n,s}\,\mathrm{LZWF}_{n,s} \;+\; \mathrm{RTRDP}_{t}\right) \qquad \mathrm{LZWF}_{n,s} \;=\; \frac{\mathrm{SEL}_{n,s}\,\mathrm{TLMP}_{s}}{\sum_{n^{\prime} \in \mathcal{N}_{z}}\sum_{s^{\prime} \in \mathcal{T}_{t}}\mathrm{SEL}_{n^{\prime},s^{\prime}}\,\mathrm{TLMP}_{s^{\prime}}} \qquad \mathrm{RTRDP}_{t} \;=\; \sum_{s \,\in\, \mathcal{T}_{t}}\mathrm{RNWF}_{s}\,\mathrm{RTRDPA}_{s}$$

- $\Phi^{k}_{e,t}$ ($): The QSE's energy charge for the interval.
- $\mathrm{RTSPP}^{\mathrm{EW}}_{z,t}$ ($/MWh): The energy-weighted zonal settlement price. This, not the plain zonal price, is what multiplies metered load - the plain one applies to scheduled and day-ahead positions. An average across the whole zone, never the price at the QSE's own location.
- $\mathrm{LMP}_{n,s}$ ($/MWh): Locational Marginal Price at node n in dispatch interval s - the cost of serving one more MWh at that specific point on the network.
- $\mathrm{LZWF}_{n,s}$ (—): The weight collapsing every node in the zone and every dispatch interval into one zonal price. Combines load at each node with the duration of each dispatch interval, so the average is both load-weighted and time-weighted. Ranges over the whole zone, not over the entity's own nodes.
- $\mathrm{SEL}_{n,s}$ (MW): State Estimated Load at node n during dispatch interval s.
- $\mathrm{TLMP}_{s}$ (seconds): Duration of dispatch interval s. Dispatch runs about every five minutes inside a fifteen-minute settlement interval, and intervals are not equal length, so they are weighted by how long each one lasted.
- $\mathrm{RTRDP}_{t}$ ($/MWh): Reliability Deployment Price for Energy - the settlement-interval aggregate, not the adder itself.
- $\mathrm{RTRDPA}_{s}$ ($/MWh): Reliability Deployment Price Adder for dispatch interval s. Compensates for the price-suppressing effect of out-of-market reliability actions. Administrative, not a clearing outcome.
- $\mathrm{RNWF}_{s}$ (—): The time weight that aggregates per-dispatch-interval adders up to the settlement interval - each dispatch interval counts in proportion to how long it lasted.
- $\underline{\pi}$ ($/MWh): Administrative price floor, set at -$251/MWh.

**True-up.** none

**Notes.** The base and the price range over different sets, which is the whole point of this record. The base sums only the nodes where the entity actually serves load; the price is a load-weighted average across every node in the zone, whoever serves load there. A single entity's own location enters that average only through its share of zonal load, which is negligible. So the cost of an extra MWh to the entity is the zone average price, while the cost to the system is the price at the node it withdrew from. Those differ whenever there is congestion inside the zone. Two administrative terms also sit inside what is nominally a clearing price: a floor at -$251/MWh, and the Reliability Deployment Price Adder. Neither comes out of the optimisation. Since December 2025 this price also carries all scarcity value - see the Scarcity Adder record. One layer sits hidden inside the base. Turning a meter reading into Adjusted Metered Load requires allocating unaccounted-for energy and network losses across loads, and each of those is a cost allocation with its own rule. Candidate for its own record.

**Sources.**

- ERCOT Nodal Protocols, Section 6 - Adjustment Period and Real-Time Operations, 6.6.1.2, Real-Time Settlement Point Price for a Load Zone, paras (1) and (2), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/06-080126_Nodal.docx))
  > The Real-Time Settlement Point Price for a Load Zone Settlement Point is based on the state-estimated Load in MW and the time-weighted average Real-Time LMPs at Electrical Buses that are included in the Load Zone.
- ERCOT Nodal Protocols, Section 6 - Adjustment Period and Real-Time Operations, 6.6.3.2, Real-Time Energy Imbalance Payment or Charge at a Load Zone, para (2), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/06-080126_Nodal.docx))
  > RTEIAMT q, p = (-1) * {[RTSPP p * [(SSSK q, p * 1/4) + (DAEP q, p * 1/4) + (RTQQEP q, p * 1/4) - (SSSR q, p * 1/4) - (DAES q, p * 1/4) - (RTQQES q, p * 1/4)]] + [RTSPPEW p * (RTMGSOGZ q, p - (RTAML q, p - RTAMLESRNW q, p))]}
- ERCOT Nodal Protocols, Section 2 - Definitions and Acronyms, Section 2.1, definition of Adjusted Metered Load (AML), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/02-080126_Nodal.docx))
  > Adjusted Metered Load (AML) Retail Load usage data that has been adjusted for Unaccounted for Energy (UFE), Transmission Losses, Distribution Losses, and Direct Current Tie (DC Tie) exports.

### Marginal losses

**Charged elsewhere.** Billed to the scheduling entity. Carried in [energy and congestion](#energy-and-congestion).

**Notes.** ERCOT recovers losses by grossing up the quantity rather than by adding a price component. Losses are folded into Adjusted Metered Load before any charge is calculated, so a load is billed for more MWh than its meter recorded and pays the ordinary energy price on the difference. There is no separate loss charge and no separate loss determinant. That placement has a consequence worth noting: because the adjustment enters the base rather than the rate, it scales every layer that uses Adjusted Metered Load, not just energy. The loss and unaccounted-for-energy allocation rules are therefore doing quiet work across most of this inventory, and they have not been extracted.

**Sources.**

- ERCOT Nodal Protocols, Section 2 - Definitions and Acronyms, Definition of Adjusted Metered Load (AML), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/02-080126_Nodal.docx))
  > Adjusted Metered Load (AML) Retail Load usage data that has been adjusted for Unaccounted for Energy (UFE), Transmission Losses, Distribution Losses, and Direct Current Tie (DC Tie) exports.

### Reliability commitment shortfall

**Charged.** Billed to the scheduling entity.

**Base** (deviation; measured: The 15-minute Settlement Interval being billed.; billed: The same 15-minute Settlement Interval.; known as it happens).

$$x^{k}_{e,t} \;=\; \mathrm{SF}_{e,t}, \qquad \mathrm{SF}_{e,t} \;=\; \max\!\left(0,\;\; \mathrm{Obligation}_{e,t} \;-\; \mathrm{Capacity}_{e,t}\right)$$

- $\mathrm{SF}_{e,t}$ (MW): The QSE's capacity shortfall for the interval - how far the generation capacity it brought fell short of what it needed to cover its own load. Zero for a QSE that is long.
- $\mathrm{Obligation}_{e,t}$ (MW): The capacity the entity needed to have covered for the interval, as determined by the reliability commitment process.
- $\mathrm{Capacity}_{e,t}$ (MW): Capacity the QSE had committed and available. Counted only for resources meeting the conditions in 5.7.4.1.1 - self-committed, quick start, or released switchable units.
- $t$ (—): A 15-minute Settlement Interval.

This is the one base in the inventory that is not a measure of consumption. It measures a gap - the distance between what a QSE needed and what it brought - so it is a deviation, and it is zero for anyone adequately covered. A load that grows without arranging matching capacity increases this base directly.


**Pool.** Make-whole payments to units that ERCOT committed for reliability when the market did not commit enough on its own, including amounts for reliability-must-run units.

**Rate** (average cost; exact recovery: no).

$$\Phi^{k}_{e,t} \;=\; \min\!\left[\; \frac{x^{k}_{e,t}}{\sum_{e^{\prime} \in \mathcal{E}} x^{k}_{e^{\prime},t}}\,C^{k}, \;\;\; \frac{2\,C^{k}\,x^{k}_{e,t}}{K_{t}} \;\right] \Big/ 4$$

- $\Phi^{k}_{e,t}$ ($): the QSE's capacity-short charge for the interval.
- $C^{k}$ ($): Total make-whole payments for the reliability commitment process in the hour containing this interval.
- $K_{t}$ (MW): Total capacity of all resources committed by that reliability process. Appears only in the cap.

**True-up.** Yes, via a second layer. Whatever the cap prevents this charge from collecting is uplifted to all loads on a load ratio share basis under the Uplift record.

**Notes.** Added as a layer of its own rather than folded into Uplift, because the two have genuinely different bases. This tier is charged on a shortfall; the residual tier is charged on metered energy. Anything that fails to stick here lands there. The cap makes recovery inexact by design. It binds precisely when shortfall is concentrated in a few payers - the case where a shortfall base would otherwise assign a very large charge to whoever was short - and the shortfall that the cap declines to collect is then socialised across all load. This is the closest ERCOT comes to charging a load for the reliability consequences of its own growth. Because it targets the gap between load and arranged capacity rather than load itself, a flexible load can reduce it either by consuming less or by arranging capacity, which is a different margin from every other layer here.

**Sources.**

- ERCOT Nodal Protocols, Section 5 - Transmission Security Analysis and Reliability Unit Commitment, 5.7.4.1, RUC Capacity-Short Charge, para (1); shortfall share at 5.7.4.1.1, effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/05-080126_Nodal.docx))
  > The dollar amount charged to each QSE, due to capacity shortfalls for a particular RUC, for a 15-minute Settlement Interval, is the QSE's shortfall ratio share multiplied by the total RUC Make-Whole Payments, including amounts for RMR Units, to all QSEs for that RUC, subject to a cap. The cap on the charge to each QSE is two multiplied by the total RUC Make-Whole Payments, including amounts for RMR Units, for all QSEs multiplied by that QSE's capacity shortfall for that RUC process divided by the total capacity of all RUC-committed Resources during that Settlement Interval for the RUC process.

### Scarcity adder

**Charged elsewhere.** Billed to the scheduling entity. Carried in [energy and congestion](#energy-and-congestion).

**Notes.** ERCOT no longer has a separable scarcity charge. Until real-time co-optimization went live overnight on 4-5 December 2025, scarcity was priced by the Operating Reserve Demand Curve as an add-on calculated after dispatch and bolted onto the energy price. The dispatch engine now clears energy and reserves together against demand curves for each reserve product, so scarcity value is inside the energy price rather than added to it. The change is visible in the settlement formula itself. The September 2025 zonal price read max(-$251, weighted LMP + RTRSVPOR + RTRDP), where RTRSVPOR was the reserve adder term. The current formula reads max(-$251, weighted LMP + RTRDP) - the reserve term is deleted. The adder acronyms appear 69 times in the September 2025 text of Section 6 and zero times in the current one, and they are no longer defined in the definitions section at all. The Operating Reserve Demand Curve itself survives, but only upstream: an aggregate curve is fitted to historical reserve data and split into the per-product demand curves the dispatch engine optimises against. It sets prices from inside the optimisation instead of adjusting them afterwards.

**Sources.**

- ERCOT Nodal Protocols, Section 6 - Adjustment Period and Real-Time Operations, 6.5.7.3, Security Constrained Economic Dispatch, para (1), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/06-080126_Nodal.docx))
  > The SCED process evaluates Energy Offer Curves, Energy Bid/Offer Curves, Ancillary Service Offers, Output Schedules, and RTM Energy Bids to determine Resource Dispatch Instructions and Ancillary Service awards by maximizing bid-based revenues minus offer-based costs, subject to power balance, Ancillary Service Demand Curves (ASDCs), and network constraints.

### Ancillary services

**Charged.** Billed to the scheduling entity.

**Base** (metered energy; measured: The Operating Hour being billed, once the day-ahead settlement has been recalculated. The provisional obligation notice issued the day before uses an earlier comparable day, but that vintage does not survive settlement.; billed: The same Operating Hour.; known as it happens).

$$x^{k}_{e,t} \;=\; \sum_{z \,\in\, \mathcal{Z}_{e}} \max\!\left(0,\;\; \mathrm{AML}_{e,z,t}\right)$$

- $x^{k}_{e,t}$ (MWh per hour): The QSE's adjusted metered withdrawal over the operating hour, truncated at zero in each of its zones. Numerator of the hourly load ratio share that finally determines the charge.

An earlier version of this record said the base was lagged. It is not, and the correction matters. A lagged share does appear, but only at the start. The day before the operating day ERCOT tells each QSE its provisional obligation using a share taken from the same hour on the most recent settled comparable day. That figure drives the initial day-ahead charge. It is then reversed out: the day-ahead cost is recalculated on the QSE's actual real-time hourly share, and the difference is settled. Anything procured in real time is allocated on the contemporaneous fifteen-minute share as well. So the historical share determines what a QSE is told to expect and what it is billed provisionally, but not what it ends up paying. Final incidence falls on consumption during the hour being billed. A load that reduces consumption in a costly hour does reduce that hour's charge.


**Pool.** The day-ahead cost of procuring each ancillary service for the hour - what ERCOT paid resources for that product plus the associated offer amounts - together with the net cost of real-time ancillary service payments and charges.

**Rate** (average cost; exact recovery: yes).

$$\Phi^{k}_{e,t} \;=\; \sum_{a \in \mathcal{A}} \Big[\underbrace{\pi_{a,t}\big(R_{a,t}\,\mathrm{LRS}^{\mathrm{RT}}_{e,t} - \mathrm{SA}_{e,a,t}\big)}_{\text{day-ahead, recalculated}} \;+\; \underbrace{C^{k,\mathrm{RT}}_{a,t}\,\mathrm{LRS}^{\mathrm{RT}}_{e,t}}_{\text{real-time}}\Big] \qquad \pi_{a,t} \;=\; \frac{C^{k,\mathrm{DA}}_{a,t}}{\sum_{e^{\prime} \in \mathcal{E}}\big(R_{a,t}\,\mathrm{LRS}^{\mathrm{RT}}_{e^{\prime},t} - \mathrm{SA}_{e^{\prime},a,t}\big)} \qquad \mathrm{LRS}^{\mathrm{RT}}_{e,t} \;=\; \frac{x^{k}_{e,t}}{\sum_{e^{\prime} \in \mathcal{E}} x^{k}_{e^{\prime},t}}$$

- $\Phi^{k}_{e,t}$ ($): The QSE's total ancillary services charge for the hour across all products. The protocol writes each component with a leading minus sign, its settlement convention for money owed to ERCOT.
- $\mathcal{A}$ (—): The set of five products currently in force - Regulation Up, Regulation Down, Responsive Reserve, Non-Spinning Reserve and ERCOT Contingency Reserve Service. A sixth, Dispatchable Reliability Reserve Service, is written into the protocols but sits behind a pending implementation flag and is not yet charged.
- $\pi_{a,t}$ ($/MW): The price charged for product a. Total procurement cost over total obligated quantity - an average, not the marginal clearing price. The protocol names it separately for each product; this is a generalisation across the five provisions, not a symbol that appears in the tariff.
- $R_{a,t}$ (MW): Quantity of product a ERCOT decided to buy for the hour. Set administratively, not by the QSE.
- $\mathrm{LRS}^{\mathrm{RT}}_{e,t}$ (—): Real-time hourly Load Ratio Share. The superscript is the whole point - this is the contemporaneous share, and it replaces the historical one used for the provisional notice.
- $\mathrm{SA}_{e,a,t}$ (MW): Quantity the QSE arranged for itself rather than buying through ERCOT.
- $C^{k,\mathrm{DA}}_{a,t}$ ($): ERCOT's total day-ahead procurement cost for product a.
- $C^{k,\mathrm{RT}}_{a,t}$ ($): Net cost of real-time ancillary service payments and charges for product a, allocated separately on the contemporaneous share.

**True-up.** Yes, and it is structural rather than incidental. The day-ahead charge computed on the historical share is recalculated on the realised share and the difference settled, so the provisional allocation is fully unwound.

**Notes.** The mechanism runs in four steps: a provisional obligation notice on a historical share, a day-ahead charge on that obligation, a recalculation of that charge on the realised real-time share, and a separate allocation of real-time ancillary service costs on the contemporaneous share. Only the first uses lagged data. All five live products are allocated identically - the charge provisions are the same formula with the acronym swapped, which is why this is one record rather than five. Procurement is competitive but the charge is not. ERCOT buys reserves in an auction with a clearing price, then bills load the average cost of what it bought, so load never faces the marginal price of reserves. The determinant is measured at the scheduling entity, not the individual load. For a load inside a retailer's portfolio, the truncation at zero and the share are computed across the whole portfolio.

**Sources.**

- ERCOT Nodal Protocols, Section 4 - Day-Ahead Operations, 4.2.1.2, Ancillary Service Obligation Assignment and Notice, para (1), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/04-080126_Nodal.docx))
  > ERCOT shall base the QSE Ancillary Service allocation on the QSE to LSE relationships for the operating date and on the hourly LSE LRSs from the Real-Time Market (RTM) data used for Initial Settlement for the same hour and day of the week, for the most recent day for which Initial Settlement data is available, multiplied by the quantity of that service required in the Day-Ahead Ancillary Service Plan.
- ERCOT Nodal Protocols, Section 4 - Day-Ahead Operations, 4.6.4.2.1 to 4.6.4.2.5, Charges for Ancillary Services Procurement in the DAM, effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/04-080126_Nodal.docx))
  > Each QSE shall pay to ERCOT or be paid by ERCOT a Reg-Up Service charge for each hour as follows: DARUAMT q = DARUPR * DARUQ q Where: DARUPR = (-1) * DAPCRUAMTTOT / DARUQTOT [...] DARUQ q = DARUO q - DASARUQ q
- ERCOT Nodal Protocols, Section 6 - Adjustment Period and Real-Time Operations, 6.7.1, Real-Time Settlement for Updated Day-Ahead Market Ancillary Service Obligations, para (1), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/06-080126_Nodal.docx))
  > DAM net total costs for Ancillary Service procured in the DAM are re-calculated for each QSE under this Section based on Real-Time Load Ratio Share (LRS).
- ERCOT Nodal Protocols, Section 6 - Adjustment Period and Real-Time Operations, 6.7.3, Real-Time Ancillary Service Revenue Neutrality Allocation, para (1), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/06-080126_Nodal.docx))
  > The total cost for Real-Time Ancillary Service payments and charges is allocated to the QSEs representing Load based on Load Ratio Share (LRS).

### Reactive supply

**Charged.** Billed to the scheduling entity.

**Base** (metered energy; measured: The 15-minute Settlement Interval being billed.; billed: The same 15-minute Settlement Interval.; known as it happens).

$$x^{k}_{e,t} \;=\; \sum_{z \,\in\, \mathcal{Z}_{e}} \max\!\left(0,\;\; \mathrm{AML}_{e,z,t}\right)$$

- $x^{k}_{e,t}$ (MWh per 15-min interval): The load's adjusted metered withdrawal for the interval, truncated at zero in each of its zones before the zones are summed. This is the numerator of the load ratio share.

**Pool.** Total payments to resources providing voltage support - both for supplying reactive power and for the energy they gave up to do so.

**Rate** (average cost; exact recovery: yes).

$$\Phi^{k}_{e,t} \;=\; C^{k}_{t}\; \mathrm{LRS}_{e,t} \qquad\qquad \mathrm{LRS}_{e,t} \;=\; \frac{x^{k}_{e,t}}{\sum_{e^{\prime} \in \mathcal{E}} x^{k}_{e^{\prime},t}}$$

- $\Phi^{k}_{e,t}$ ($): The load's voltage support charge for the interval. The protocol writes this with a leading minus sign, which is its settlement-statement convention for money owed to ERCOT.
- $C^{k}_{t}$ ($): The pool - total voltage support payments for the interval.

**True-up.** None needed. The shares sum to one by construction because the denominator is the sum of the same truncated quantities that form each numerator.

**Notes.** A pure pass-through. Whatever ERCOT paid for voltage support in an interval is divided among loads in proportion to their consumption in that same interval. Nothing in the determinant relates to reactive power. A load's reactive behaviour, power factor, or location has no effect on what it pays - only its share of real energy consumption does. The charge carries no signal about the service it funds.

**Sources.**

- ERCOT Nodal Protocols, Section 6 - Adjustment Period and Real-Time Operations, 6.6.7.2, Voltage Support Charge, para (1), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/06-080126_Nodal.docx))
  > ERCOT shall charge each QSE representing LSEs the total payment for VSS as specified in Section 6.6.7.1, Voltage Support Service Payments, based on a LRS.

### Black start

**Charged.** Billed to the scheduling entity.

**Base** (metered energy; measured: The Operating Hour being billed.; billed: The same Operating Hour.; known as it happens).

$$x^{k}_{e,t} \;=\; \sum_{z \,\in\, \mathcal{Z}_{e}} \max\!\left(0,\;\; \mathrm{AML}_{e,z,t}\right)$$

- $x^{k}_{e,t}$ (MWh per hour): The load's adjusted metered withdrawal over the operating hour, truncated at zero in each of its zones. Numerator of the hourly load ratio share.

**Pool.** Standby fees paid to generators contracted to restart the grid from a total blackout.

**Rate** (average cost; exact recovery: yes).

$$\Phi^{k}_{e,t} \;=\; C^{k}_{t}\; \mathrm{LRS}_{e,t} \qquad\qquad \mathrm{LRS}_{e,t} \;=\; \frac{x^{k}_{e,t}}{\sum_{e^{\prime} \in \mathcal{E}} x^{k}_{e^{\prime},t}}$$

- $\Phi^{k}_{e,t}$ ($): The load's black start charge for the hour.
- $C^{k}_{t}$ ($): The pool - total black start standby payments for the hour.

**True-up.** none

**Notes.** A standby service that is bought whether or not it is ever used, and the cost of standing ready does not vary with how much anyone consumes in the hour. Charging it on hourly consumption means a load can reduce its share by consuming less at a moment when the underlying cost is entirely unaffected by that choice. Structurally the same limiting case as system administration: a fixed pool on a usage base.

**Sources.**

- ERCOT Nodal Protocols, Section 6 - Adjustment Period and Real-Time Operations, 6.6.8.2, Black Start Capacity Charge, para (1), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/06-080126_Nodal.docx))
  > ERCOT shall allocate the total Black Start Service Capacity payment to the QSEs representing Loads based on a LRS.

### Emergency Response Service

**Charged.** Billed to the scheduling entity.

**Base** (metered energy; measured: Each service time period within the contract period, separately.; billed: The contract period, settled once and then resettled.; known as it happens).

$$x^{k}_{e,t} \;=\; \sum_{z \,\in\, \mathcal{Z}_{e}} \max\!\left(0,\;\; \mathrm{AML}_{e,z,t}\right)$$

- $x^{k}_{e,t}$ (MWh per service time period): The entity's adjusted metered load over one of the service time periods that make up a contract period. Numerator of the share for that period.
- $t$ (—): A service time period - one of the recurring blocks of hours a contract covers, not the whole contract term.

The protocol states the share rather than the determinant, defining it as the entity's total load in the time period over total ERCOT load in the same period. The numerator is written here in the truncated form used everywhere else in the protocols so the record is comparable with the other load-ratio layers, which is a reconstruction rather than quoted text.


**Pool.** Payments to demand-side resources contracted to curtail when the grid is short. A voluntary programme procured in advance for a fixed term.

**Rate** (average cost; exact recovery: yes).

$$\Phi^{k}_{e} \;=\; \sum_{t \in \mathcal{P}} C^{k}_{t}\, \mathrm{LRS}_{e,t} \qquad\qquad \mathrm{LRS}_{e,t} \;=\; \frac{x^{k}_{e,t}}{\sum_{e^{\prime} \in \mathcal{E}} x^{k}_{e^{\prime},t}}$$

- $\Phi^{k}_{e}$ ($): The entity's emergency response service charge for the contract period.
- $C^{k}_{t}$ ($): The pool for one service time period.

**True-up.** Yes. Settled first on the latest available settlement load, then resettled using trued-up load for every operating day in the contract period.

**Notes.** ERCOT pays some loads to be available to curtail, and charges all loads for it, so a load enrolled in the programme sits on both sides. The allocation is narrower than most layers here. Rather than one system-wide share, the cost of each service type is spread only across the time periods that service actually covers, so a load consuming heavily during the covered hours pays more of it. That ties the charge to the hours the service is bought for more closely than any other pooled layer in this inventory.

**Sources.**

- ERCOT Nodal Protocols, Section 6 - Adjustment Period and Real-Time Operations, 6.6.11.2, Emergency Response Service Capacity Charge, para (1), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/06-080126_Nodal.docx))
  > ERCOT shall allocate costs for an ERS service type and ERS Contract Period based on the LRS of each QSE during each ERS Time Period in an ERS Contract Period. A QSE's LRS for an ERS Time Period shall be the QSE's total Load for the ERS Time Period divided by the total ERCOT Load in the ERS Time Period.

### Firm fuel supply

**Charged.** Billed to the scheduling entity.

**Base** (metered energy; measured: The Operating Hour being billed.; billed: The same Operating Hour.; known as it happens).

$$x^{k}_{e,t} \;=\; \sum_{z \,\in\, \mathcal{Z}_{e}} \max\!\left(0,\;\; \mathrm{AML}_{e,z,t}\right)$$

- $x^{k}_{e,t}$ (MWh per hour): The entity's adjusted metered withdrawal over the operating hour, truncated at zero in each Load Zone before the zones are summed.

**Pool.** Standby fees and fuel replacement costs paid to generators that hold a secured fuel supply on site so they can run when gas delivery fails.

**Rate** (average cost; exact recovery: yes).

$$\Phi^{k}_{e,t} \;=\; C^{k}_{t}\; \mathrm{LRS}_{e,t} \qquad\qquad \mathrm{LRS}_{e,t} \;=\; \frac{x^{k}_{e,t}}{\sum_{e^{\prime} \in \mathcal{E}} x^{k}_{e^{\prime},t}}$$

- $\Phi^{k}_{e,t}$ ($): The entity's firm fuel supply charge for the hour.
- $C^{k}_{t}$ ($): The pool - total firm fuel supply payments for the hour.

**True-up.** none

**Notes.** Created after the February 2021 winter storm, when gas supply to generators failed at the same time as demand peaked. Load pays generators to keep fuel physically on site. Another standby service billed on hourly consumption: the cost of holding fuel in reserve does not vary with how much anyone consumes in a given hour, but the share deciding who pays for it does.

**Sources.**

- ERCOT Nodal Protocols, Section 6 - Adjustment Period and Real-Time Operations, 6.6.14.3, Firm Fuel Supply Service Capacity Charge, para (1), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/06-080126_Nodal.docx))
  > ERCOT shall allocate the total FFSS capacity and fuel replacement payment to the QSEs representing Loads based on an hourly LRS.

### Uplift

**Charged.** Billed to the scheduling entity.

**Base** (metered energy; measured: The 15-minute Settlement Interval being billed.; billed: The same 15-minute Settlement Interval.; known as it happens).

$$x^{k}_{e,t} \;=\; \sum_{z \,\in\, \mathcal{Z}_{e}} \max\!\left(0,\;\; \mathrm{AML}_{e,z,t}\right)$$

- $x^{k}_{e,t}$ (MWh per 15-min interval): The load's adjusted metered withdrawal for the interval, truncated at zero in each of its zones. Numerator of the load ratio share.

The determinant has nothing to do with why the cost arose. This layer only exists to collect what the shortfall-based charge could not, and it does so on ordinary consumption.


**Pool.** Make-whole payments to units committed by ERCOT for reliability, including reliability-must-run units, less whatever was already recovered from capacity-short QSEs.

**Rate** (average cost; exact recovery: yes).

$$\Phi^{k}_{e,t} \;=\; \left(\frac{C^{k,\mathrm{tot}}_{t}}{4} \;-\; C^{k,\mathrm{short}}_{t}\right) \mathrm{LRS}_{e,t} \qquad\qquad \mathrm{LRS}_{e,t} \;=\; \frac{x^{k}_{e,t}}{\sum_{e^{\prime} \in \mathcal{E}} x^{k}_{e^{\prime},t}}$$

- $\Phi^{k}_{e,t}$ ($): The load's share of the uncovered make-whole cost for the interval.
- $C^{k,\mathrm{tot}}_{t}$ ($ per hour): Total make-whole payments for all reliability commitment processes in the hour containing this interval. The division by four in the formula is what brings it down to the interval.
- $C^{k,\mathrm{short}}_{t}$ ($): What was already collected from capacity-short QSEs in the interval - see the RUC Capacity Short record.

**True-up.** None needed. This layer is itself the true-up - it exists to close whatever gap the capacity-short charge leaves.

**Notes.** The second tier of a two-tier mechanism. ERCOT first tries to charge the QSEs that were short of capacity, then spreads whatever is left over all load by consumption. The two tiers point in opposite directions. The first is targeted and avoidable - a QSE can escape it by arranging capacity. The second is untargeted and can only be avoided by consuming less, at a moment when consumption had nothing to do with the cost. How much of the pool ends up in each tier depends on the cap in the first tier, so an administrative parameter decides how much of the cost is targeted and how much socialised.

**Sources.**

- ERCOT Nodal Protocols, Section 5 - Transmission Security Analysis and Reliability Unit Commitment, 5.7.4.2, RUC Make-Whole Uplift Charge, para (1), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/05-080126_Nodal.docx))
  > If the revenues from the charges under Section 5.7.4.1, RUC Capacity-Short Charge, are not enough to cover all RUC Make-Whole Payments, including amounts for RMR Units, for a 15-minute Settlement Interval, then the difference will be uplifted to all QSEs on a Load Ratio Share basis.

### Capacity obligation

**No such charge.** Billed to the scheduling entity.

**Notes.** ERCOT has no capacity market and places no capacity obligation on load, so there is nothing to charge and no determinant to record. Price stands in its place: resource adequacy is meant to come from energy and reserve prices rising high enough in tight conditions to attract investment. The market design rule lists what ERCOT procures - energy and ancillary services - and no capacity product appears in it. The companion resource adequacy rule requires only a five-year adequacy forecast and creates no obligation on anyone.

**Sources.**

- 16 Tex. Admin. Code §25.501, Wholesale Market Design for the Electric Reliability Council of Texas (PUCT Substantive Rules), (b), Bilateral markets and default provision of energy and ancillary capacity services, effective 2012-04-18 ([link](https://ftp.puc.texas.gov/public/puct-info/agency/rulesnlaws/subrules/electric/25.501/25.501.pdf))
  > ERCOT shall permit market participants to self-arrange (self-schedule or bilaterally contract for) energy and ancillary capacity services, except to the extent that doing so would adversely impact ERCOT's ability to maintain reliability. To the extent that a market participant does not self-arrange the energy and ancillary capacity services necessary to meet its obligations [...] ERCOT shall procure energy and ancillary capacity services on behalf of the market participant to cover the shortfall and charge the market participant for the services provided.

### Transmission network service

**Charged.** Billed to the distribution utility.

**Base** (coincident peak; measured: Measured across four intervals - the peak of total ERCOT demand in each of June, July, August and September. Those intervals happen, and are identified, during that summer itself. ERCOT files the resulting figures by 1 December, and they then bill in every one of the twelve months of the following calendar year, unchanged. A single summer's behaviour is frozen into a full year of charges paid afterwards.; billed: Every month of the following calendar year - twelve charges from one summer's measurements.; known only afterwards).

$$x^{k}_{e,y} \;=\; \frac{1}{4}\sum_{m \,\in\, \mathcal{M}} d_{e,\;t_{m}(y-1)} \qquad\qquad t_{m}(y-1) \;=\; \arg\max_{\,t \,\in\, \mathcal{T}_{m,y-1}} \; \sum_{e^{\prime} \in \mathcal{E}} d_{e^{\prime},t}$$

- $x^{k}_{e,y}$ (MW, averaged over 4 intervals): The entity's average demand across the four peak intervals. A demand level, not energy - which is why the measurement window alone does not tell you the unit. One number per year; it does not vary by month.
- $d_{e,t}$ (MW): Demand of entity e during interval t. Load served by wholesale storage is excluded from the count.
- $t_{m}(y-1)$ (—): The interval in month m at which total ERCOT demand was highest. Set by everyone else's aggregate demand, not by yours, and only identifiable after the month has passed.
- $y$ (—): The billing year. The four intervals occur during the summer of year y-1, are filed by ERCOT that December, and then bill throughout year y.

The rule does not say how long these intervals are; it defers that to ERCOT's own protocols. Not recorded here because it was not read from protocol text.


**Pool.** The transmission owner's approved cost of service - its transmission operating expenses, plus depreciation and other costs assigned to the transmission function.

**Rate** (average cost; exact recovery: no).

$$\Phi^{k}_{e,y} \;=\; r_{y}\, x^{k}_{e,y} \qquad\qquad r_{y} \;=\; \frac{C^{k}}{X^{k}_{y}} \qquad\qquad X^{k}_{y} \;=\; \frac{1}{4}\sum_{m \,\in\, \mathcal{M}}\;\sum_{e^{\prime} \in \mathcal{E}} d_{e^{\prime},\;t_{m}(y-1)}$$

- $\Phi^{k}_{e,y}$ ($): The entity's transmission charge for the year. Billed in twelve monthly instalments.
- $C^{k}$ ($ per year): The transmission owner's approved cost of service - the pool being recovered. Fixed at the last rate case and not refreshed alongside the billing determinants, which is why recovery is not exact.
- $d_{e,t}$ (MW): Demand of entity e during interval t - the same quantity the base measures, reused here to build the denominator.
- $X^{k}_{y}$ (MW): Total demand across all billed entities over the same four peak intervals, divided by four. Turns the pool into a per-MW rate.
- $r_{y}$ ($/MW per year): The resulting annual rate. The rule directs that it be converted to a monthly figure and billed in twelve instalments but does not specify the divisor, so only the annual form is recorded.

**True-up.** None within a year, and none on billing-unit variance at all. The rate stays in force until a new one is approved, so any shortfall or surplus is settled in the next rate case rather than trued up as it accrues.

**Notes.** A year of transmission charges turns on demand during four intervals, and those intervals are only identifiable after the fact. This is the sharpest incentive in the inventory: avoiding load during four moments out of roughly thirty-five thousand determines an entire year's bill. The timing runs forward, not backward. The peaks are set during the summer as it happens; ERCOT files the figures by 1 December; the charges are then paid across the following twelve months. Nothing is chosen retrospectively - the determinant is fixed by behaviour in real time and then billed later. This makes the layer unusual in one respect: the load acts long before it can know whether the action mattered, because whether a given interval turns out to be the monthly peak depends on the whole system's demand. At the time of this extraction - August 2026 - the June and July 2026 peaks have already occurred and are locked in, and the August and September ones have not. Consumption in the coming weeks is setting transmission charges payable throughout 2027. The mechanism is not in an ERCOT tariff. It sits in a state regulator's rule, and ERCOT's protocols disclaim responsibility for billing, collecting or disbursing transmission payments - ERCOT only calculates and files the underlying quantities. Recovery is not exact. The rate stays in force until the commission approves a new one, so its denominator is frozen at the peak demand assumed in the last rate case, while the billing determinant is refreshed every year from the most recent summer. Collections are the cost of service scaled by the ratio of realised peak demand to the assumed figure, so in a market adding load the layer over-recovers, and the faster load grows the more it over-recovers. Nothing in the rule reconciles the difference as it accrues; it is picked up whenever the next rate case happens. Two caveats. The charge falls on distribution utilities rather than on individual loads, so how it reaches any particular load is a retail question. And a pending rulemaking proposes replacing four peak intervals with twelve; as of this extraction the rule still says four and the proceeding is undecided.

**Sources.**

- 16 Tex. Admin. Code §25.192, Transmission Service Rates (PUCT Substantive Rules), (b)(1) rate and charge; (d) billing units, effective 2022-12-20 ([link](https://ftp.puc.texas.gov/public/puct-info/agency/rulesnlaws/subrules/electric/25.192/25.192.pdf))
  > A TSP's transmission rate shall be calculated as its commission-approved transmission cost of service divided by the average of ERCOT coincident peak demand for the months of June, July, August and September (4CP), excluding the portion of coincident peak demand attributable to wholesale storage load. [...] The monthly transmission service charge to be paid by each DSP is the product of each TSP's monthly rate as specified in its tariff and the DSP's previous year's average of the 4CP demand that is coincident with the ERCOT 4CP. [...] A TSP's transmission rate shall remain in effect until the commission approves a new rate. The TSP's annual rate shall be converted to a monthly rate. [...] No later than December 1 of each year, ERCOT shall determine and file with the commission the current year's average 4CP demand for each DSP [...] This demand shall be used to bill transmission service for the next year.
- ERCOT Nodal Protocols, Section 9 - Settlement and Billing, 9.17, Transmission Billing Determinant Calculation, para (1), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2023/06/01/09-080126_Nodal.docx))
  > ERCOT shall provide Market Participants with the key parameters and formula components required by a Transmission Service Provider (TSP) or Distribution Service Provider (DSP) in determining the billing charges for the use of its Transmission Facilities or Distribution Facilities ("Transmission Billing Determinants"). ERCOT is not responsible for billing, collection, or disbursal of payments associated with transmission access service.

### Interconnection upgrade assignment

**Charged.** Billed to the scheduling entity.

**Base** (TODO; measured: TODO; billed: —; known as it happens).


**Pool.** TODO

**Rate** (TODO; exact recovery: TODO).


**True-up.** TODO

**Notes.** Deliberately left unfilled. This is the layer closest to the large-load question and the only one in the inventory with no settled rule to cite. A new state rule, 16 TAC §25.194, would set interconnection standards for loads of 75 MW and above in ERCOT, implementing legislation passed in June 2025. It was proposed in March 2026 and, as of this extraction in August 2026, has not been adopted - there is no rule text at the location where every other adopted rule in this chapter is published. Reported figures for interconnection fees and financial security come from the proposal, not from an operative rule, so recording them would breach the sourcing standard. A second and more consequential proposal is further along. Under PUCT Project No. 58000, published for comment in July 2026 with comments due 11 August 2026, a proposed new rule §25.252 would set tariff terms for large load customers. As proposed it would replace the four summer peaks with twelve monthly ones measured over 30-minute intervals, and - the part that matters here - set a minimum billing demand equal to the greatest of the customer's contracted peak, its highest non-coincident demand in the prior year, and its measured coincident-peak demand, payable monthly for 240 consecutive months and starting when reserved capacity becomes available whether or not the facility is drawing power. If adopted in that form it would be the first ERCOT layer whose determinant is contracted capacity rather than metered consumption, and the only one a load cannot reduce by changing behaviour at all. It is the single most relevant pending item in Texas for a flexible-load argument. It is not recorded as a layer because it is a proposal, not an operative rule.

**Sources.**

- TODO, TODO, effective TODO ([link](TODO))
  > TODO

### Regional project cost allocation

**Charged elsewhere.** Billed to the distribution utility. Carried in [transmission network service](#transmission-network-service).

**Notes.** ERCOT sits outside federal jurisdiction, so it has no separate regional cost allocation process and no beneficiary-pays test for new transmission. A project's costs enter the building utility's cost of service and are recovered through the ordinary peak demand charge alongside everything else that utility owns. The effect is that new transmission is paid for on the same four peak intervals as existing transmission, regardless of who the project was built for or who benefits from it. There is no determinant that distinguishes a load driving new construction from one that is not.

**Sources.**

- 16 Tex. Admin. Code §25.192, Transmission Service Rates (PUCT Substantive Rules), (c), Transmission cost of service, effective 2022-12-20 ([link](https://ftp.puc.texas.gov/public/puct-info/agency/rulesnlaws/subrules/electric/25.192/25.192.pdf))
  > The transmission cost of service for each TSP shall be based on the expenses in Federal Energy Regulatory Commission (FERC) expense accounts 560-573 (or accounts with similar contents or amounts functionalized to the transmission function) plus the depreciation [...]

### Reliability must-run

**Charged.** Billed to the scheduling entity.

**Base** (metered energy; measured: The Operating Hour being billed.; billed: The same Operating Hour.; known as it happens).

$$x^{k}_{e,t} \;=\; \sum_{z \,\in\, \mathcal{Z}_{e}} \max\!\left(0,\;\; \mathrm{AML}_{e,z,t}\right)$$

- $x^{k}_{e,t}$ (MWh per hour): The load's adjusted metered withdrawal over the operating hour, truncated at zero in each of its zones. Numerator of the hourly load ratio share.

**Pool.** The net cost of keeping units running that the market would otherwise have retired - standby payments, energy costs and non-performance amounts, less what those units earned in the market anyway.

**Rate** (average cost; exact recovery: yes).

$$\Phi^{k}_{e,t} \;=\; \left(C^{k,\mathrm{sb}}_{t} + C^{k,\mathrm{en}}_{t} - C^{k,\mathrm{adj}}_{t} + \frac{C^{k,\mathrm{np}}_{t}}{\mathrm{HRS}}\right)\mathrm{LRS}_{e,t} \qquad\qquad \mathrm{LRS}_{e,t} \;=\; \frac{x^{k}_{e,t}}{\sum_{e^{\prime} \in \mathcal{E}} x^{k}_{e^{\prime},t}}$$

- $\Phi^{k}_{e,t}$ ($): The load's reliability-must-run charge for the hour.
- $C^{k,\mathrm{sb}}_{t}$ ($): Standby payments to all must-run units for the hour.
- $C^{k,\mathrm{en}}_{t}$ ($): Energy cost payments to those units for the hour.
- $C^{k,\mathrm{adj}}_{t}$ ($): What the units earned from the market anyway. Entered with a minus sign, so load pays only the incremental cost of the arrangement.
- $C^{k,\mathrm{np}}_{t}$ ($): Non-performance amounts, spread over H hours.
- $\mathrm{HRS}$ (—): The number of hours the non-performance amount is spread across. A count, not a duration, so the division leaves dollars.

**True-up.** none

**Notes.** The pool is netted before allocation - load pays the difference between what the unit receives under the arrangement and what it would have earned without it, not the gross payment. That is a genuinely cost-causal construction of the pool. The base is not. Must-run units are retained to solve a specific local reliability problem, but the cost is spread across all ERCOT load by consumption share, so a load in the constrained area pays the same rate as one hundreds of miles away. The locational information that motivated the contract is discarded at the allocation step.

**Sources.**

- ERCOT Nodal Protocols, Section 6 - Adjustment Period and Real-Time Operations, 6.6.6.5, RMR Service Charge, para (1), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/06-080126_Nodal.docx))
  > The total RMR cost for all RMR Units is allocated to the QSEs representing Loads based on LRS. [...] The amount charged to the QSE based on its LRS of the difference between the amount paid to all QSEs for RMR Service under Section 6.6.6, Reliability Must-Run Settlement, and the amount that would have been paid to the QSEs for the same RMR Units if they were not providing RMR Service.

### System administration

**Charged.** Billed to the scheduling entity.

**Base** (metered energy; measured: The 15-minute Settlement Interval being billed.; billed: The same 15-minute Settlement Interval.; known as it happens).

$$x^{k}_{e,t} \;=\; \sum_{z \,\in\, \mathcal{Z}_{e}} \max\!\left(0,\;\; \mathrm{AML}_{e,z,t}\right)$$

- $x^{k}_{e,t}$ (MWh per 15-min interval): The load's adjusted metered withdrawal for the interval, truncated at zero separately in each of its zones before the zones are summed.
- $\mathcal{Z}_{e}$ (—): The Load Zones in which this entity serves load. The truncation is applied within each of them before they are summed, so a negative position in one zone cannot offset a positive one in another.

The charge is levied on max(0, load), not on load. A payer whose metered load in one of its zones comes out negative in an interval - which happens when on-site generation exceeds consumption - pays nothing there rather than receiving a credit. The charge stops falling once consumption reaches zero and does not turn into a payment beyond it.


**Pool.** ERCOT's operating budget, as approved by the state regulator. The protocol treats the fee as given rather than deriving it from a revenue requirement.

**Rate** (posted; exact recovery: no).

$$\Phi^{k}_{e,t} \;=\; \mathrm{LAFF} \cdot x^{k}_{e,t}$$

- $\Phi^{k}_{e,t}$ ($): The load's system administration charge for the interval.
- $\mathrm{LAFF}$ ($/MWh): Load Administration Fee Factor - the system administration fee itself. A single published number, changed only when the regulator approves a new one.

**True-up.** None. The fee changes only going forward, on regulatory approval. Nothing reconciles what was collected against what ERCOT actually spent.

**Notes.** A near-fixed pool recovered on a usage base, which makes almost the entire charge unrelated to what any individual load costs the system. Small money, but the cleanest example of the pattern. Also a posted rate with no true-up. Collections equal the fee times whatever load turns out to be, which has no reason to match ERCOT's budget in any year. The error is absorbed by resetting the fee later. The charge falls on scheduling entities rather than on loads directly; how it is passed through is a contractual matter outside the wholesale rules.

**Sources.**

- ERCOT Nodal Protocols, Section 9 - Settlement and Billing, 9.16.1, ERCOT System Administration Fee, effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2023/06/01/09-080126_Nodal.docx))
  > The Public Utility Commission of Texas (PUCT) has authorized ERCOT to charge the ERCOT System Administration fee to fund ERCOT's budget. ERCOT converts the fee into a charge to each Qualified Scheduling Entity (QSE) using the formula set forth in paragraph (3) below. [...] Each QSE shall pay the ERCOT System Administration fee. The ERCOT System Administration fee is for each 15-minute Settlement Interval for each QSE. ESACAMT q = LAFF * SUM over p of max(0, RTAML q, p) [...] LAFF | $/MWh | Load Administration Fee Factor - The ERCOT System Administration fee. [...] p | none | A Settlement Point. The summation is over all of the Settlement Points.

### Congestion rights allocation

**Charged.** Billed to the scheduling entity.

**Base** (metered energy; measured: Measured and credited monthly. Trued up after final settlement for the month.; billed: The same calendar month.; known as it happens).

$$x^{k}_{e,t} \;=\; \sum_{z \,\in\, \mathcal{Z}_{e}} \max\!\left(0,\;\; \mathrm{AML}_{e,z,t}\right)$$

- $x^{k}_{e,t}$ (MWh per month): The load's adjusted metered withdrawal over the month, truncated at zero per settlement point. Numerator of the monthly load ratio share.

**Pool.** Net revenue ERCOT collects from selling congestion revenue rights at auction, including the proceeds of rights pre-assigned to municipal and cooperative utilities.

**Rate** (average cost; exact recovery: yes).

$$\Phi^{k}_{e,t} \;=\; -\left(C^{k,\mathrm{zon}}_{z,t}\, \mathrm{LRS}^{z}_{e,t} \;+\; C^{k,\mathrm{sys}}_{t}\, \mathrm{LRS}_{e,t}\right) \qquad\qquad \mathrm{LRS}^{z}_{e,t} \;=\; \frac{x^{k}_{e,z,t}}{\sum_{e^{\prime} \in \mathcal{E}} x^{k}_{e^{\prime},z,t}}$$

- $\Phi^{k}_{e,t}$ ($): The load's share of auction revenue. Negative because this is a credit - money flowing to the load rather than from it.
- $C^{k,\mathrm{zon}}_{z,t}$ ($): Auction revenue from rights that both start and end inside zone z, shared only among entities with load in that zone.
- $C^{k,\mathrm{sys}}_{t}$ ($): Auction revenue from every other right - those whose path crosses a zone boundary. Shared across all of ERCOT.
- $\mathrm{LRS}^{z}_{e,t}$ (—): The zonal load ratio share - the entity's fraction of load inside zone z alone rather than of ERCOT-wide load. The superscript is what separates it from the system-wide share applied to the other pool.
- $x^{k}_{e,z,t}$ (MWh per month): The entity's truncated metered load inside zone z over the month.

**True-up.** Yes. Distributed monthly on initial settlement data, then trued up after final settlement.

**Notes.** A credit, so the sign is reversed, but structurally an ordinary allocation: a pool divided by consumption share. The zonal split is the only place in this inventory where a pooled layer keeps any locational information - revenue from rights that begin and end inside one zone stays with that zone's load. The zone boundaries used are the congestion zones as they stood in 2003, which no longer correspond to how the network is managed. Note also that this credit is allocated on consumption while the congestion charges it offsets are priced at a zonal average. A load's credit and the congestion it actually causes are therefore determined by different things.

**Sources.**

- ERCOT Nodal Protocols, Section 7 - Congestion Revenue Rights, 7.5.7, Method for Distributing CRR Auction Revenues, para (2), effective 2025-12-05 ([link](https://www.ercot.com/files/docs/2021/08/01/07-120525_Nodal.docx))
  > ERCOT shall credit the net CRR Auction revenue (including PCRR revenue) produced from CRRs cleared in each CRR Auction that source from a Settlement Point located within a 2003 ERCOT CMZ and sink at a Settlement Point located within the same 2003 ERCOT CMZ to [QSEs] on a zonal Load Ratio Share (LRS) basis. All other net CRR Auction revenues must be allocated to QSEs on an ERCOT-wide LRS basis.

### Loss and congestion surplus credit

**Charged.** Billed to the scheduling entity.

**Base** (metered energy; measured: Measured and settled over the same 15-minute Settlement Interval. No lag.; billed: The same 15-minute Settlement Interval.; known as it happens).

$$x^{k}_{e,t} \;=\; \sum_{z \,\in\, \mathcal{Z}_{e}} \max\!\left(0,\;\; \mathrm{AML}_{e,z,t}\right)$$

- $x^{k}_{e,t}$ (MWh per 15-min interval): The load's adjusted metered withdrawal for the interval, truncated at zero in each of its zones. Numerator of the load ratio share.

**Pool.** Whatever the real-time market fails to balance in an interval - the net of all energy imbalance payments and charges, DC tie and block load transfer payments, self-schedule congestion, and payments to congestion right holders. Can be a surplus or a shortfall.

**Rate** (average cost; exact recovery: yes).

$$\Phi^{k}_{e,t} \;=\; -\,C^{k}_{t}\; \mathrm{LRS}_{e,t} \qquad\qquad \mathrm{LRS}_{e,t} \;=\; \frac{x^{k}_{e,t}}{\sum_{e^{\prime} \in \mathcal{E}} x^{k}_{e^{\prime},t}} \qquad\qquad C^{k}_{t} \;=\; \sum_{v \in \mathcal{V}} \left(\mathrm{PAY}_{v,t} - \mathrm{CHG}_{v,t}\right)$$

- $\Phi^{k}_{e,t}$ ($): The entity's share of the residual. The leading minus sign means load is credited when ERCOT takes in more than it pays out, and charged when it pays out more than it takes in.
- $C^{k}_{t}$ ($): The net imbalance for the interval. Positive when ERCOT paid out more than it took in, which is the case that produces a charge to load.
- $\mathcal{V}$ (—): The set of eight real-time money flows enumerated in 6.6.10(1) - the three energy imbalance settlements, DC tie imports, block load transfers, settlement-only generation, self-schedule congestion, and payments to congestion right holders.
- $\mathrm{PAY}_{v,t}$ ($): What ERCOT paid out on flow v during the interval.
- $\mathrm{CHG}_{v,t}$ ($): What ERCOT took in on flow v during the interval.

**True-up.** None needed. This layer is the true-up for the market as a whole - it is defined as whatever is left over, so it closes by construction.

**Notes.** The market's plug. Prices are set by an optimisation that has no reason to make money in equal money out, and this layer sweeps up the difference every fifteen minutes and shares it by consumption. It is the clearest case in the inventory of a pool with no cost behind it at all. The residual is an artefact of how prices were formed - congestion rents, the gap between zonal and nodal settlement, payments to rights holders - not a resource anyone bought. Yet it is allocated on the same determinant as everything else. The sign is not fixed. In intervals when the market over-collects, load is paid; when it under-collects, load pays. Both directions land on the same base, so the layer adds variance to a load's bill that is unrelated to anything the load did.

**Sources.**

- ERCOT Nodal Protocols, Section 6 - Adjustment Period and Real-Time Operations, 6.6.10, Real-Time Revenue Neutrality Allocation, paras (1) and (2), effective 2026-08-01 ([link](https://www.ercot.com/files/docs/2024/06/28/06-080126_Nodal.docx))
  > ERCOT must be revenue-neutral in each Settlement Interval. Each QSE receives an allocated share, on a LRS basis, of the net amount of: [Real-Time Energy Imbalance payments or charges at a Resource Node, a Load Zone and a Hub; DC Tie import payments; Block Load Transfer Point payments; SODG and SOTG energy; Real-Time congestion payments or charges for Self-Schedules; and Real-Time payments or charges to the Congestion Revenue Right (CRR) Owners].

---

## 5. Which designations touch which layer

The inventory in `large_load_arrangements.md` describes each designation; this is the cross-reference by layer.

| layer | what a designation changes |
|---|---|
| Energy and congestion | Co-location nets generation behind the meter against load, so the base $d - g$ shrinks (ERCOT §39.169 review; PJM EL25-49 caps netting above 50 MW). PJM economic demand response adds a credit: the energy price times a reduction against an estimated baseline. |
| Ancillary services | A Controllable or Non-Controllable Load Resource is paid the clearing price on awarded capacity; its load-ratio share as payer is unchanged. PJM EL25-49 assesses regulation and black start on gross demand for co-located load. |
| Emergency Response Service | An ERS provider is paid a capped capacity price on contracted MW. Cost is allocated by load-ratio share within the ERS time period, so a load that reduces in those fixed blocks cuts its allocation with certainty. |
| Transmission network service | The 4CP base ([data](https://www.ercot.com/mktinfo/data_agg/4cp)) is what a mover avoids: a year of charges set by demand in four summer intervals. Co-location nets the measured demand. PUCT Project 58484 would replace four peaks with twelve 30-minute peaks and add a minimum billing demand. PJM's analog is Network Service Peak Load, zonal, one or five peaks by zone, plus [Schedule 12](https://agreements.pjm.com/eTariff/transformedTariffs/oatt/Sections/4424.html) enhancement charges ([billing reference](https://www.pjm.com/-/media/DotCom/markets-ops/settlements/custgd.pdf)). |
| Capacity obligation | No ERCOT layer; adequacy is recovered through scarcity energy and reserve prices. In PJM the base is Peak Load Contribution at the five highest RTO peaks; Price Responsive Demand lowers it by a committed reduction; Non-Firm Contract Demand carries no capacity charge. |
| Uplift, reliability commitment shortfall, system administration, and the rest | No designation changes them. Every load pays its share; only the base moves, with consumption. |
