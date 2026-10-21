# Large-load designations, as the model uses them

What ERCOT and PJM call a large load that moves, sells reserve, or accepts curtailment, and how each name maps onto the load type $\theta$ in the memo and the Workshop I report. Rule status is as of **20 August 2026** and was not re-verified on 21 October 2026; the previous version of this file (`git show 4c96a5b:docs/catalog/large_load_arrangements.md`) carries the full survey, including the topics parked in §6.

---

## 0. How to read this

**The model's bill has three layers**, energy, reserve, investment. The real bill has six: energy, hedge, reserve, adequacy, transmission, supply. The model folds adequacy and transmission into one investment layer with a peak-hour base, and leaves hedge and supply out (§6). Every load pays every layer; a designation changes the quantity a charge lands on, the price on that quantity, or adds a credit. Nothing exempts a load.

**What a designation does.** The catalog's vocabulary, used in the report:

| who | operation | meaning | in the model |
|---|---|---|---|
| load | `move` | changes consumption under a fixed charge | the best response $R$ |
| load | `sell` | adds a credit for reserve it supplies | `sells reserve`; the credit $\mu^\top\sigma^{\rm clr}$ |
| load | `elect` | picks an option the tariff offers | `Menu`; `elect` |
| rule | `BASE` | redefines the quantity charged | the window $\mathcal W^k$ |
| rule | `RATE` | redefines the charge on a fixed quantity | share vs two-part |
| rule | `MENU` | adds or removes options | `Menu` |
| rule | `GATE` | conditions connection; no recurring charge | not modeled |

**What goes into $\theta$.** Private: $\psi$ (value of following the preferred profile), $\beta$ (tolerated deviation), $A$ (energy-conservation windows), $p$ (believed chance a sold MW is called). Public: whether the load sells reserve, whether it is curtailable, and if so its declared firm level $d^{\rm firm}$. A designation below sets the public fields and bounds the private ones.

**Most of what large loads do today is `move`.** ERCOT 4CP responders grew from 418 loads in 2022 to 1,080 in 2024 with no product on offer. Products sit on the `sell` margin and draw far less: 940 MW of Controllable Load Resources against an 85 GW peak.

---

## 1. The type table

| type | $\psi$ | $\beta$ | $A$ | $p$ | sells reserve | curtailable | ERCOT | PJM |
|---|---|---|---|---|---|---|---|---|
| inflexible | — | 0 | $I$ | — | no | no | any load | any load |
| mover | sweep | sweep | sweep | — | no | no | 4CP responder (§2.1) | NSPL / PLC responder (§3.1) |
| controllable load resource | sweep | sweep | sweep | low | yes, continuous | no | CLR (§2.2) | economic DR, weakly (§3.2) |
| emergency response | sweep | low | sweep | high | yes, in blocks | no | NCLR, ERS, VECL, LLDMS (§2.3, §2.5) | Emergency / Capacity Performance DR (§3.2) |
| curtailable | sweep | sweep | sweep | — | no | yes, $d^{\rm firm}$ | SB6 §39.170 (§2.5) | Non-Firm Contract Demand (§3.4) |

Sweep: $(\psi, \beta, A)$ take the data-center values (high, low, $1^\top$) or the bitcoin-mine values (low, high, $\mathbf 0$). A load sells reserve or is curtailable, not both: the same MW cannot be offered as $\sigma$ and claimed as headroom. The rows are designations; the businesses behind them set the private parameters.

Not in the table, and why: Conforming / Non-Conforming Load (§2.6) has no bill effect; Large Load Interconnection (§2.7) is a gate; Price Responsive Demand (§3.3) is a tariff feature; co-location (§6) needs generation behind the meter.

---

## 2. ERCOT

### 2.1 Plain large load, 4CP responder → mover

**Rule.** PUCT Substantive Rule 16 TAC §25.192 — [rule text](https://ftp.puc.texas.gov/public/puct-info/agency/rulesnlaws/subrules/electric/25.192/25.192.pdf); [4CP data](https://www.ercot.com/mktinfo/data_agg/4cp).

Every load pays transmission on its demand in four 15-minute system peaks, one each in June through September, identified after the fact. The rate is each transmission provider's approved cost of service divided by average ERCOT 4CP demand. A load that curtails for on the order of an hour a year sheds most of its annual transmission charge, whether or not that reduces transmission cost; its avoidance raises everyone else's rate, since the pool is fixed.

**→ $\theta$.** No public designation. The mover is any load that shifts against a peak base. In the model the investment layer's peak-hour share is 4CP's analog, with the peak hour set ex ante instead of ex post. $\beta$ is the fraction of load the business can drop or shift for an hour; $A$ says whether the dropped energy comes back.

**Scale.** 1,080 loads reducing at 4CP in 2024, 2.6× two years earlier ([NRG, citing ERCOT](https://www.nrg.com/assets/documents/energy-policy/ercot-transmission-costs-and-rate-design-remarks-on-feb-25-2025.pdf)). MW reduced is not published. Under active replacement by 12CP (§6).

### 2.2 Controllable Load Resource → controllable load resource

**Rule.** Nodal Protocols §2.1 definitions and §6 real-time operations; qualification tests in the Nodal Operating Guides — [Load Resource program page](https://www.ercot.com/services/programs/load/laar).

A Load Resource can interrupt on ERCOT instruction under an ancillary service program. A Controllable Load Resource (CLR) can raise or lower consumption under ERCOT dispatch control: it takes five-minute base points from security-constrained economic dispatch like a generator. Registered through a qualified scheduling entity; needs ERCOT-standard telemetry and passing qualification tests; requalifies periodically. Failure to follow base points brings non-performance charges and can end in decertification.

**Payment.** Capacity payments on awarded ancillary service capacity (Responsive Reserve, ERCOT Contingency Reserve Service, Non-Spin, Regulation), plus energy settlement on deviations from base point. The reserve layer appears twice: the load still pays its QSE's load-ratio share of ancillary cost (misaligned), and is paid the clearing price on what it sells (aligned by construction). Registration adds the second term without touching the first.

**→ $\theta$.** `sells reserve`, continuous. $p$ is low: ERCOT deploys load-side Responsive Reserve a handful of times a year. $\beta$ is the awarded range over consumption. A CLR pays 4CP like any other load, so it is also a mover.

**Scale.** About 940 MW across 18 resources in 2023, roughly 1% of system peak — **uncited**.

### 2.3 Non-Controllable Load Resource → emergency response

**Rule.** Same as §2.2.

Responds in blocks, on a ten-minute manual instruction or automatically by under-frequency relay, not to a continuous signal. Nine tenths of registered Load Resource capability is this kind.

**→ $\theta$.** `sells reserve` in blocks: small $\beta$ (the block), high $p$ relative to a CLR. In the model the same row as ERS; the difference between them is the product sold, which the model does not distinguish.

**Scale.** About 7,400 MW across some 557 resources in 2023, by subtraction from the Load Resource total — **uncited**.

### 2.4 Emergency Response Service → emergency response

**Rule.** Nodal Protocols §3.14.3 (procurement §3.14.3.1, requirements §3.14.3.3); settlement §6.6.11.1–2. PUCT Rule 16 TAC §25.507 — [program page](https://www.ercot.com/services/programs/load/eils).

A competitively procured emergency service deployed during an Energy Emergency Alert, when physical responsive capability falls below 3,000 MW and is not expected to recover within thirty minutes. Not an ancillary service, not a registration status: ERS resources are exempt from the modeling and telemetry other resources carry, and that exemption is the design point. Qualification rests on interval metering showing the offered reduction is achievable. Procured in standard contract periods over a December-to-November year, in ERS-10 and ERS-30 ramp classes. Contracted capacity may not also provide ancillary services in the period.

**Payment.** Capacity payment on contracted MW, offer-capped at $80/MW/hr; program spending capped at $50M a year.

**Cost allocation.** §6.6.11.2 allocates ERS cost by load-ratio share measured within the ERS time period. The periods are fixed blocks, so reducing in them cuts the allocated cost with certainty. That is a cleaner `move` than 4CP and as misaligned: the pool is fixed by procurement.

**→ $\theta$.** `sells reserve`, high $p$, low $\beta$. The $80/MW/hr cap bounds $c^s = 2p\psi\beta\delta$ for a load that finds ERS worth selling.

**Scale.** MW not located; spending capped at $50M a year.

### 2.5 SB6: mandatory curtailment, VECL, LLDMS → curtailable; emergency response

**Rule.** SB6 (effective 20 June 2025), PURA §§37.0561, 39.169, 39.170. NPRR1238, PUCT-approved 31 July 2025 — [NPRR1238](https://www.ercot.com/mktrules/issues/NPRR1238). Implementing PUCT projects 58317, 58481, 58479, 58480.

Three mechanisms, routinely conflated:

- **Mandatory curtailment (§39.170).** Large loads of 75 MW or more interconnected after 31 December 2025 must install remote disconnection equipment enabling firm load shed. A condition of interconnection, unpaid. Critical industrial and critical natural-gas loads exempt. The load pays the default bill and receives nothing for the obligation; that asymmetry is the instrument.
- **Voluntary Early Curtailment Load (NPRR1238).** Opt-in status to curtail on instruction under defined grid stress, ahead of firm load shed.
- **Large Load Demand Management Service.** Competitively procured voluntary service for loads of 75 MW or more, 24-hour minimum notice; unavailable to loads already responding to price or committed to another reliability or ancillary service. Cost allocation unsettled.

**→ $\theta$.** Mandatory curtailment is the `curtailable` row: the load declares a firm level $d^{\rm firm}$, the operator may shed to it in an emergency, unpaid. In the rules the level is a MW amount, so the model uses a level, not a profile; the report sets $d^{\rm firm} = (1-\beta)\min_t\delta_t$. VECL and LLDMS are paid block curtailment, the emergency-response row.

### 2.6 Conforming and Non-Conforming Load → not a type

**Rule.** Nodal Protocols §2.1 definitions — [protocols](https://www.ercot.com/mktrules/nprotocols/current).

A forecasting and modeling classification. Non-Conforming Load does not follow a recognizable pattern and is represented individually. ERCOT designates it on data the wires provider submits. No charge is assessed on it and it unlocks nothing: ERCOT can model a load in full detail and still have no right to tell it anything. Authority to move a load comes from a product it sold (§2.2) or a limit on its entitlement (§2.5).

### 2.7 Large Load Interconnection → a gate

**Rule.** Planning Guide §9 via PGRR115 (15 May 2025) — [PGRR115](https://www.ercot.com/mktrules/issues/PGRR115); modeling via NPRR1234 (15 December 2025) — [NPRR1234](https://www.ercot.com/mktrules/issues/NPRR1234); Batch Study process, PUCT 18 June 2026 — [release](https://ftp.puc.texas.gov/public/puct-info/agency/resources/pubs/news/2026/PUCT-Approves-New-ERCOT-Process-to-Manage-Electricity-Requests-from-Data-Centers-Large-Power-Users.pdf); [program page](https://www.ercot.com/services/rq/large-load-integration).

A Large Load is 75 MW or more of aggregate peak demand at one site. Sites of 25 MW or more are individually modeled. Milestone-gated queue; statutory minimum study fee; batch studies group projects. Obligations: telemetry, a commissioning plan, ride-through, disclosure of on-site backup generation. No recurring charge; what it decides is whether and at what size the load exists.

---

## 3. PJM

### 3.1 Transmission and capacity bases → mover

**Rule.** OATT network integration provisions; [Schedule 12](https://agreements.pjm.com/eTariff/transformedTariffs/oatt/Sections/4424.html); RPM provisions in the Reliability Assurance Agreement; [billing reference](https://www.pjm.com/-/media/DotCom/markets-ops/settlements/custgd.pdf).

Network transmission service is charged on Network Service Peak Load (NSPL), a zonal coincident-peak contribution, one or five peaks depending on zone, reset each 1 January. Capacity obligation runs through Peak Load Contribution (PLC) at the five highest RTO summer peaks. Same family as 4CP, less concentrated: zonal rather than system-wide, five intervals rather than four, and two separate bases, so avoiding one does not avoid the other.

**→ $\theta$.** The mover, same as §2.1. PJM has an explicit adequacy base where ERCOT has none; the model's investment layer stands for both.

### 3.2 Demand response through a curtailment service provider → controllable / emergency response

**Rule.** OATT Attachment K; Operating Agreement Schedule 1 §3.3A; [Manual 18](https://www.pjm.com/-/media/DotCom/documents/manuals/m18.ashx) and Manual 11.

A curtailment service provider registers end-use load and bears its performance; the provider–customer split is private contract. **Economic DR** offers reductions into the energy market against an estimated baseline. **Emergency / Capacity Performance DR** clears the capacity auction and must reduce on dispatch during emergencies and performance assessment hours, with non-performance charges. Adds credits only; NSPL and PLC charges are unchanged.

**→ $\theta$.** Economic DR is the weak PJM analog of a CLR: it only reduces, against a baseline it can inflate. Emergency DR is the emergency-response row: blocks, high $p$ in assessment hours, paid through the capacity layer rather than the reserve stack.

**Scale.** 7,299 MW UCAP of DR cleared for 2027/28, 5.4% of 134,479 MW ([PJM 2027/28 BRA](https://www.pjm.com/-/media/DotCom/about-pjm/newsroom/2025-releases/20251217-pjm-auction-procures-134479-mw-of-generation-resources.pdf)).

### 3.3 Price Responsive Demand → a tariff feature, not a type

**Rule.** RAA Schedule 6.1; Manuals 18 and 18B.

Load on a retail rate linked to real-time price, with curtailment control, registered by its LSE; the committed reduction lowers the load forecast that sets reliability requirements, so the load's capacity obligation shrinks. No payment. A sold call on its own consumption, compensated by a smaller adequacy base. In the model this is a window change on the investment layer that the load elects, not a property of the load.

**Scale.** 106.5 MW for 2027/28, 0.08% of cleared capacity ([BRA report](https://www.pjm.com/-/media/DotCom/markets-ops/rpm/rpm-auction-info/2026-2027/2026-2027-bra-report.pdf)). Any commitment-based menu has to explain this number.

### 3.4 Non-Firm Contract Demand → curtailable, with a reserve exemption

**Rule.** *PJM Interconnection, L.L.C.*, 193 FERC ¶ 61,217 (18 December 2025), Docket EL25-49 — [order](https://www.gravel2gavel.com/files/2025/12/E-1-EL25-49-000.pdf); order on rehearing and paper hearing, 18 June 2026, EL25-49-002 — [order](https://www.ferc.gov/media/e-2-el25-49-002). Written for co-located load; the service menu is general.

A customer serving large load takes one of three transmission services: Network Integration (charged on gross demand), Firm Contract Demand (a contracted MW with special protection schemes enforcing it, one-year minimum), or Non-Firm Contract Demand (a contracted MW, curtailed in emergencies, one hour to one month, no capacity charge). The clearest `MENU` in either market: an explicit price on firmness. No service product was finalized as of the status date.

**→ $\theta$.** Non-Firm Contract Demand is the curtailable row with the model's $\tau_5$: a declared firm level and an exemption from a layer. PJM exempts adequacy; the model exempts reserve, because the model's curtailable headroom displaces procured reserve.

---

## 4. Order of magnitude

Two different things get counted. **Registered to sell** is capability contracted into a construct. **Observed moving** is load reducing against a base with no product sold, only partly published. A load can appear in both.

| market | registered to sell | volume | against system scale |
|---|---|---|---|
| PJM | DR cleared in RPM, 2027/28 | 7,299 MW UCAP | 5.4% of 134,479 MW |
| PJM | Price Responsive Demand, 2027/28 | 106.5 MW | 0.08% |
| ERCOT | Load Resources, all types | ~8,300 MW, 575+ resources | ~10% of ~85 GW peak (2023, **uncited**) |
| ERCOT | of which Controllable | ~940 MW, 18 resources | ~1% |
| ERCOT | Emergency Response Service | MW not located | spending cap $50M/yr |

| market | observed moving | volume |
|---|---|---|
| ERCOT | loads reducing at 4CP | 1,080 loads in 2024, 418 in 2022 |
| PJM | loads reducing at NSPL or PLC | not published |

**What share of a bill is movable.** E3's whitepaper ([link](https://www.ethree.com/wp-content/uploads/2026/05/E3_Large-Load-Tariff-Whitepaper-1.pdf)) runs a 25 MW data center across five retail tariffs: the demand-charge share, the part a peak move can avoid, spans 0% (Georgia Power) to 55% (ComEd), while total bills span under 2:1. These are retail structures; the wholesale share for an ERCOT or PJM participant is computable from published bases and rates and was not computed. [DELTa](https://sepapower.org/large-load-tariffs-database/) held 77 large-load tariffs across 36 states as of 31 March 2026.

---

## 5. Sources to read before relying on the detail

- **ERCOT Nodal Protocols §2.1** for Load Resource and CLR definitions, and **§6.6.11.2** for the ERS allocation formula; both confirmed as structure, not against current text.
- **Nodal Operating Guides** for CLR qualification tests and the Responsive Reserve deployment history that sets $p$.
- **PJM Manual 18** for how a committed PRD value reduces the capacity obligation, and OATT Attachment H for the zonal NSPL split.
- **EL25-49 orders** for Non-Firm Contract Demand terms; paragraph pinpoints were not verified.
- **ERCOT participation figures** are 2023 vintage and the 85 GW denominator is approximate.

---

## 6. Parked, with pointers

Topics the previous version covered that the model does not use. All are in `git show 4c96a5b:docs/catalog/large_load_arrangements.md` at the section given.

| topic | why parked | where |
|---|---|---|
| Retail customer vs. wholesale participant; the LSE between the load and the tariff | the model's load buys at wholesale | §1.2, §4.1, Appendix A |
| Hedging, take-or-pay floors, and the resale test | no contracts in the model | §1.3 |
| Co-location, behind-the-meter generation, the EL25-49 netting cap | no generation behind the load's meter | §3.6, §4.4, §4.5 |
| State retail tariffs with minimum-demand floors (AEP Ohio, Dominion GS-5, Georgia Power) | retail `RATE`; the model's tariffs are wholesale | Appendix A |
| 4CP → 12CP (PUCT Project 58484), ERCOT minimum billing demand, payment on available capacity (Project 58000) | pending; `BASE` and `RATE` changes for Workshop 2's tariff set | §5.2 |
| The six-RTO show cause orders of 18 June 2026 on flexible-load transmission services | pending; would generalize PJM's `MENU` | §5.1 |
| NERC computational load standards (RD26-7) | reliability, not a charge | §5.3 |
| Axes of designation (counterparty, ISO representation, firmness, supply role) | folded into §0 and the type table | §1 |
