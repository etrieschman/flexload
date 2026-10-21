# Large-load arrangements in US wholesale power markets

An inventory of the designations a large load can hold in ERCOT and PJM, each described the same way, keyed to a layered bill. Status date **20 August 2026**; not re-verified since. The long-form survey this replaces is at `git show 4c96a5b:docs/catalog/large_load_arrangements.md`.

---

## 0. Conventions

A load's bill is a sum of charges, one per layer, each a rate function $\Phi^k$ on a base $x^k$:

$$B = \sum_{k \in \mathcal K} \Phi^k\big(x^k\big), \qquad \mathcal K = \{\text{energy},\ \text{hedge},\ \text{reserve},\ \text{adequacy},\ \text{transmission},\ \text{supply}\}.$$

The **base** is the quantity a charge lands on; tariffs call it the billing determinant. The load controls $q = (d, h, g)$: consumption, contracted financial volume, and generation behind its own meter. $\Delta^k$ is the wedge on layer $k$, the load's marginal payment less the marginal system cost it causes; $\Delta^k = 0$ is alignment.

**Every load pays every layer.** No designation exempts a load from reserve, adequacy, or transmission cost. A designation changes the quantity a charge lands on, the price on that quantity, who is billed, or adds a credit. The default bill, absent any designation:

| layer | ERCOT | PJM |
|---|---|---|
| energy | net withdrawal $d - g$ at the node, 5-minute | same |
| hedge | none required | none required |
| reserve | QSE load-ratio share of ancillary service cost | load-ratio share of ancillary charges |
| adequacy | **no layer**; recovered through energy and reserve prices in scarcity | Peak Load Share, from Peak Load Contribution at the five highest RTO summer peaks |
| transmission | 4CP: demand in four summer 15-minute system peaks | Network Service Peak Load, zonal coincident peak, plus Schedule 12 |
| supply | zero unless the load sells | zero unless the load sells |

How each of these charges is built, layer by layer with formulas and sources, is in `bill_decomposition.md`. The two bases a mover responds to, ERCOT's 4CP and PJM's Network Service Peak Load and Peak Load Contribution, are described there, not here: they are what every load faces, not designations.

**Operations.** A rule does one of four things to a load; a load does one of three things in response.

| actor | operation | meaning | example |
|---|---|---|---|
| rule | `BASE` | redefines the quantity charged | 4CP → 12CP |
| rule | `RATE` | redefines the charge on a fixed quantity | a minimum-demand ratchet |
| rule | `MENU` | adds or removes options the load may elect | PJM's three transmission services |
| rule | `GATE` | conditions connection; no recurring charge | ERCOT's 75 MW study requirement |
| load | `move` | changes $q$ under a fixed base and rate | curtailing at 4CP |
| load | `elect` | picks an option | taking Non-Firm Contract Demand |
| load | `sell` | adds a credit | a Controllable Load Resource's reserve sales |

**Four axes** place a designation: (a) commercial counterparty: retail customer of a load-serving entity, direct wholesale participant, or co-located behind a generator's meter; (b) ISO representation: from invisible inside a zonal aggregate to individually dispatched with telemetry; (c) firmness: what the load may withdraw and when that can be suspended; (d) supply-side role: whether it sells reserve, response, or capacity. Representation confers no authority: ERCOT can model a load in full detail and still have no right to tell it anything. Authority comes from a product the load sold (d) or a limit on its entitlement (c).

**Each entry below** gives: the rule; what the designation is; who designates or elects it; what it constrains; what the load pays or is paid; the bill effect as layer, base, rate, operation; and one analytical point.

---

## 1. ERCOT

### 1.1 Conforming / Non-Conforming Load
- **Rule.** Nodal Protocols §2.1 — [protocols](https://www.ercot.com/mktrules/nprotocols/current).
- **What.** A forecasting and modeling classification. Non-Conforming Load does not follow a recognizable pattern and is represented individually.
- **Who.** ERCOT, on data the wires provider submits; at registration or when behavior diverges from the assigned profile.
- **Constrains.** Nothing.
- **Bill.** None. Axis (b) only.
- **Point.** Representation without authority; the baseline case for the axes above.

### 1.2 Load Resource: Controllable and Non-Controllable
- **Rule.** Nodal Protocols §2.1, §6; qualification in the Nodal Operating Guides — [program page](https://www.ercot.com/services/programs/load/laar).
- **What.** A Load Resource interrupts on ERCOT instruction under an ancillary service program. A **Controllable Load Resource** (CLR) raises or lowers consumption under dispatch control, taking five-minute base points from security-constrained economic dispatch like a generator. A **Non-Controllable Load Resource** responds in blocks, by ten-minute manual instruction or under-frequency relay.
- **Who.** The load registers through a qualified scheduling entity; ERCOT-standard telemetry, qualification tests, periodic requalification. Non-performance brings charges and can end in decertification.
- **Constrains.** $d$, severely for a CLR inside its awarded range.
- **Pays / paid.** Still pays its QSE's load-ratio share of ancillary cost. Paid the clearing price on awarded capacity (Responsive Reserve, ERCOT Contingency Reserve Service, Non-Spin, Regulation) plus energy settlement on base-point deviations.
- **Bill.** reserve · awarded MW·h · product clearing price · `sell` (a credit). Reserve as payer unchanged. Transmission (4CP) unchanged.
- **Point.** The reserve layer appears twice with opposite signs. The credit is aligned by construction; the payer term keeps the load-ratio defect. Registration adds an aligned term beside a misaligned one.

### 1.3 Emergency Response Service
- **Rule.** Nodal Protocols §3.14.3; settlement §6.6.11.1–2; PUCT Rule 16 TAC §25.507 — [program page](https://www.ercot.com/services/programs/load/eils).
- **What.** Competitively procured emergency curtailment, deployed in an Energy Emergency Alert when physical responsive capability falls below 3,000 MW and is not expected to recover within thirty minutes. Not an ancillary service, not a registration status; exempt from the modeling and telemetry other resources carry.
- **Who.** The load contracts through a QSE; qualification by interval metering showing the reduction is achievable. Standard contract periods over a December-to-November year; ERS-10 and ERS-30 ramp classes. Cannot also provide ancillary services in the contracted period.
- **Constrains.** $d$, conditionally and rarely.
- **Pays / paid.** Capacity payment on contracted MW, offer-capped at $80/MW/hr; program spend capped at $50M a year. ERS cost is allocated by load-ratio share measured within the ERS time period (§6.6.11.2).
- **Bill.** reserve · contracted MW · offered price · `sell`; reserve as payer · load in ERS periods · pool share · `move`.
- **Point.** The periods are fixed blocks, so reducing in them cuts the allocated cost with certainty. A cleaner `move` than 4CP and as misaligned: the pool is set by procurement.

### 1.4 Large Load Interconnection
- **Rule.** Planning Guide §9 via PGRR115 (15 May 2025) — [PGRR115](https://www.ercot.com/mktrules/issues/PGRR115); modeling via NPRR1234 (15 December 2025) — [NPRR1234](https://www.ercot.com/mktrules/issues/NPRR1234); Batch Study process, PUCT 18 June 2026 — [release](https://ftp.puc.texas.gov/public/puct-info/agency/resources/pubs/news/2026/PUCT-Approves-New-ERCOT-Process-to-Manage-Electricity-Requests-from-Data-Centers-Large-Power-Users.pdf); [program page](https://www.ercot.com/services/rq/large-load-integration); SB6, effective 20 June 2025.
- **What.** A Large Load is 75 MW or more of aggregate peak demand at one site; sites of 25 MW or more are individually modeled. Milestone-gated queue; statutory minimum study fee; projects studied in batches.
- **Who.** The wires provider submits the study for the load.
- **Constrains.** Whether, when, and at what size the load connects. Obligations: telemetry, commissioning plan, ride-through, disclosure of backup generation.
- **Bill.** None recurring. `GATE`.
- **Point.** The study feeds transmission planning, so it moves the level of transmission cost everyone pays, not any load's base.

### 1.5 SB6 curtailment: mandatory, voluntary early, demand management
- **Rule.** PURA §§37.0561, 39.169, 39.170; NPRR1238 (31 July 2025) — [NPRR1238](https://www.ercot.com/mktrules/issues/NPRR1238); PUCT projects 58317, 58481, 58479, 58480.
- **What.** Three mechanisms. **Mandatory curtailment (§39.170):** loads of 75 MW or more interconnected after 31 December 2025 install remote disconnection enabling firm load shed; critical industrial and critical gas loads exempt. **Voluntary Early Curtailment Load (NPRR1238):** opt-in curtailment on instruction under defined grid stress, ahead of firm shed. **Large Load Demand Management Service:** procured voluntary service for loads of 75 MW or more, 24-hour notice, closed to loads already price-responsive or committed elsewhere. §37.0561 also lets ERCOT deploy a load's own generation in emergencies where it serves at least half of site demand and cannot export.
- **Who.** Mandatory: a condition of interconnection. VECL and LLDMS: the load elects.
- **Constrains.** $d$ without compensation (mandatory); $d$ contingently with compensation (VECL, LLDMS); $g$ (§37.0561).
- **Pays / paid.** Mandatory: the default bill, nothing either way. LLDMS: a reserve credit; cost allocation unsettled.
- **Bill.** Mandatory: unchanged, `GATE`. LLDMS: reserve · procured MW · procurement price · `sell`.
- **Point.** Mandatory curtailment changes no layer. It is a property of the load, firm service made revocable, in exchange for connecting at all. The asymmetry is the instrument.

### 1.6 Co-location and behind-the-meter arrangements
- **Rule.** PURA §39.169; PUCT Project 58479. Effective 1 September 2025.
- **What.** Net-metering arrangements between an existing generator and a co-located large load need ERCOT evaluation and PUCT approval, unless the generation was under majority common ownership with the load's parent as of 1 January 2025. Conditions attach through the approval, arrangement by arrangement.
- **Who.** PUCT approves; ERCOT evaluates.
- **Constrains.** $g$ directly, its terms indirectly.
- **Bill.** Bases unchanged; the value of $d - g$ at them shrinks. energy · $d - g$ · $\lambda$ · `move`; transmission · 4CP measured net · TCOS rate · `move`; review · `GATE`.
- **Point.** Netting reduces the base on layers whose cost driver is not net withdrawal. Reserve, adequacy and transmission pay for serving the load when the co-located generator is out; netting shrinks the measured quantity without shrinking that obligation.

---

## 2. PJM

### 2.1 Retail customer vs. direct wholesale participant
- **Rule.** OATT §I.1 "Eligible Customer"; Operating Agreement; Reliability Assurance Agreement; Manual 14A.
- **What.** Most load sits inside a load-serving entity's zonal aggregate and sees wholesale charges only as the supplier passes them through. Where state law permits, a load takes unbundled transmission service and participates as or through a PJM member.
- **Who.** State retail law decides eligibility; FERC declined to resolve the boundary in EL25-49.
- **Constrains.** Nothing directly.
- **Bill.** Both pay all six layers on the same wholesale cost. A retail customer's charges land on the base its LSE writes into the retail rate; a wholesale participant's land on the ISO base directly. `elect` between two sets of bases.
- **Point.** Nothing forces the retail base to move with the wholesale base. An LSE billed on coincident peak may bill its customers on non-coincident monthly peak; the customer's curtailment at system peak cuts the LSE's obligation and not its own bill. A misalignment source independent of any defect in the wholesale base.

### 2.2 Demand response through a curtailment service provider
- **Rule.** OATT Attachment K; Operating Agreement Schedule 1 §3.3A; Manuals 11 and 18 — [Manual 18](https://www.pjm.com/-/media/DotCom/documents/manuals/m18.ashx).
- **What.** A curtailment service provider registers end-use load and bears its performance; the provider–customer split is private contract. **Economic DR** offers reductions into the energy market against an estimated baseline. **Emergency / Capacity Performance DR** clears the capacity auction and must reduce on dispatch in emergencies and performance assessment hours.
- **Who.** The load, through a provider; registration in DR Hub and eRPM; 15-minute metering; commitments up to three years forward.
- **Constrains.** $d$ on dispatch; penalty tail governs for a load with uptime commitments.
- **Pays / paid.** Credits only. Transmission and adequacy charges unchanged.
- **Bill.** energy · reduction vs baseline · LMP-based · `sell`; adequacy · cleared MW · RPM price net of penalties · `sell`.
- **Point.** The baseline is an estimate, so a load that can inflate it is paid for reductions it did not make: a base-proxy problem inside the supply term.

### 2.3 Price Responsive Demand
- **Rule.** RAA Schedule 6.1; Manuals 18 and 18B.
- **What.** Load on a retail rate linked to real-time price, with curtailment control, registered by its LSE. The committed Nominal PRD Value lowers the load forecast that sets reliability requirements, so the load's capacity obligation shrinks. No ERCOT analogue.
- **Who.** The LSE files a PRD Plan by 15 January before the Base Residual Auction.
- **Constrains.** $d$ above the price threshold.
- **Pays / paid.** No payment; a smaller capacity obligation.
- **Bill.** adequacy · Peak Load Contribution less the committed value · RPM price · `elect`; energy · metered $d$ · real-time price passthrough · `elect`.
- **Point.** The mirror image of a ratchet: a ratchet commits to a consumption floor, PRD to a reduction once price passes a threshold. 106.5 MW cleared for 2027/28, 0.08% of capacity ([BRA report](https://www.pjm.com/-/media/DotCom/markets-ops/rpm/rpm-auction-info/2026-2027/2026-2027-bra-report.pdf)); any commitment-based menu has to explain that number.

### 2.4 Behind-the-meter generation
- **Rule.** OATT §III.34.2; Manuals 18 and 21. Under revision (§2.5, §3).
- **What.** Generation serving load without using the transmission or distribution system; qualifying output nets against load in the peak bases for network transmission service and capacity obligation.
- **Constrains.** $g$ qualifies or not.
- **Bill.** energy · $d - g$ · $\lambda$ · `move`; transmission · NSPL net of BTMG · zonal rate · `move`; adequacy · PLC net of BTMG · RPM price · `move`.
- **Point.** Three layers shrink from one subtraction. FERC's finding that this is unjust and unreasonable, and the cap that follows, are `BASE`.

### 2.5 Co-located load and the three transmission services (EL25-49)
- **Rule.** 193 FERC ¶ 61,217 (18 December 2025) — [order](https://www.gravel2gavel.com/files/2025/12/E-1-EL25-49-000.pdf); [fact sheet](https://www.ferc.gov/news-events/news/fact-sheet-ferc-directs-nations-largest-grid-operator-create-new-rules-embrace); compliance order 16 April 2026 (ER26-1088); order on rehearing and paper hearing 18 June 2026 — [EL25-49-002](https://www.ferc.gov/media/e-2-el25-49-002). Predecessor: Talen–Amazon ISA, ER24-2172, rejected 1 November 2024.
- **What.** Co-located load is end-use load connected on the interconnection customer's side of the point of interconnection. The customer serving it takes one of three services: **Network Integration Transmission Service** (transmission and capacity on gross demand); **Firm Contract Demand** (a contracted MW, one-year minimum, special protection schemes enforce it, penalties above); **Non-Firm Contract Demand** (a contracted MW, one hour to one month, curtailed in emergencies, no capacity charge). An interim non-firm service bridges customers waiting on upgrades.
- **Who.** The eligible customer elects. FERC directed PJM to propose a netting materiality threshold (PJM: 50 MW cumulative nameplate), grandfather contracts as of 18 December 2025, and allow a three-year transition. Regulation and black start assessed on gross demand.
- **Constrains.** $g$ via the netting cap; $d$ via contract demand limits.
- **Bill.** transmission · gross or contract demand · zonal rate, CD rates developing · `BASE`, `MENU`; adequacy · gross / contract / none by service · RPM price · `BASE`, `MENU`; reserve · gross demand for regulation and black start · existing rates · `BASE`; energy · $d - g$ with netting capped · $\lambda$ · `BASE`.
- **Point.** The clearest `MENU` in either market: three services sorted by how much the load relies on the grid, an explicit price on firmness ERCOT does not offer. Non-Firm Contract Demand makes curtailability a property the load elects, with a declared firm level. No service product was final at the status date.


### 2.6 Large Load Additions and the Expedited Interconnection Track
- **Rule.** Critical Issue Fast Path, August 2025; Board letter 16 January 2026 — [letter](https://www.pjm.com/-/media/DotCom/about-pjm/who-we-are/public-disclosures/2026/20260116-pjm-board-letter-re-results-of-the-cifp-process-large-load-additions.pdf); Expedited Interconnection Track, ER26-1563, accepted 9 June 2026.
- **What.** A large load addition is 50 MW or more at one point of interconnection. The process produced a bring-your-own-generation expedited track (generation above 250 MW UCAP, ten projects a year, three-year site control) and a connect-and-manage curtailable path for loads without generation.
- **Constrains.** Access timing; $g > 0$ becomes a condition of expedited access.
- **Bill.** None recurring. `GATE`.
- **Point.** A load's behind-the-meter generation decision is no longer separable from its interconnection timeline.

---

## 3. State retail tariffs and pending changes

**State retail tariffs** are where `RATE` lives; the ISO markets have almost none. Three large-load tariffs in three wholesale contexts do the same thing: a minimum-demand floor below which curtailment has no private value.

| tariff | threshold | commitment | rule |
|---|---|---|---|
| [AEP Ohio Data Center Tariff](https://www.aepohio.com/company/about/rates/data-center-tariff/), 23 July 2025 | >25 MW; >1 MW crypto | 85% of subscribed demand monthly, ~12 years; exit fee | PUCO 24-508-EL-ATA ([release](https://puco.ohio.gov/news/puco-orders-aep-ohio-to-create-data-center-specific-tariff)) |
| Dominion GS-5, effective 1 January 2027 | ≥25 MW | 85% of T&D demand, 60% of generation demand, 14 years | Virginia SCC PUR-2025-00058 ([release](https://www.scc.virginia.gov/about-the-scc/newsreleases/release/scc-issues-order-on-dev-biennial-review-2025/scc-rules-in-dev-biennial-review-case.html)) |
| Georgia Power, 1 February 2025 | ≥100 MW | customised contract, up to 15 years | Georgia PSC Docket 44280 ([fact sheet](https://psc.ga.gov/site/downloads/datacenterfactsheet.pdf)) |

Whether a commitment distorts turns on one test: can the committed quantity be resold at market price? A hedge on $h$ pays $(f - \lambda)h$ whatever the load consumes, so the marginal price stays $\lambda$ and $\Delta = 0$. A take-or-pay floor on $h$ carries no marginal price below the floor. Resale collapses the second into the first. The record on resale rights is thin.

**Pending**, as of the status date:

| item | docket | timing |
|---|---|---|
| PJM co-located service rates, terms, minimum charge | EL25-49-002 | compliance filings due ~17 August 2026 |
| PJM BTMG netting: 50 MW threshold, grandfathering, transition | EL25-49 compliance | pending |
| Six-RTO show cause orders on large-load tariffs, including new transmission services for flexible loads | EL26-67 to EL26-72 (18 June 2026) — [release](https://www.ferc.gov/news-events/news/ferc-launches-aggressive-targeted-action-speed-large-load-integration) | 60-day responses |
| **ERCOT 4CP → 12CP**, 30-minute intervals; minimum billing demand for new large loads | PUCT Project 58484 | statutory deadline 31 December 2026 |
| ERCOT payment on transmission capacity made available before consumption | PUCT Project 58000 | ongoing |
| ERCOT LLDMS cost allocation | NPRR1238 implementation | not effective |
| NERC computational load standards and registry, after the 10 July 2024 loss of ~1,500 MW of data-center load on a voltage excursion ([incident review](https://www.nerc.com/globalassets/our-work/reports/event-reports/incident_review_large_load_loss.pdf); [task force white paper](https://www.nerc.com/globalassets/who-we-are/standing-committees/rstc/whitepaper-characteristics-and-risks-of-emerging-large-loads.pdf)) | RD26-7 (16 July 2026) | standards due 31 December 2026 |

On 12CP: twelve monthly peaks in longer blocks are harder to predict and costlier to avoid, which is a different question from whether the base is a better proxy for transmission cost. A base can be gaming-resistant and still misaligned. If the minimum billing demand arrives with it, ERCOT gets `BASE` and `RATE` from one proceeding, pushing flexibility in opposite directions.

---

## 4. Order of magnitude

| market | registered to sell | volume | against system scale | source |
|---|---|---|---|---|
| PJM | DR cleared in RPM, 2027/28 | 7,299 MW UCAP | 5.4% of 134,479 MW | [BRA](https://www.pjm.com/-/media/DotCom/about-pjm/newsroom/2025-releases/20251217-pjm-auction-procures-134479-mw-of-generation-resources.pdf) |
| PJM | Price Responsive Demand, 2027/28 | 106.5 MW | 0.08% | BRA report |
| ERCOT | Load Resources, all types | ~8,300 MW, 575+ resources | ~10% of ~85 GW peak | 2023, **uncited** |
| ERCOT | of which Controllable | ~940 MW, 18 resources | ~1% | 2023, **uncited** |
| ERCOT | Emergency Response Service | MW not located | spend cap $50M/yr | §25.507 |

| market | observed moving | volume | source |
|---|---|---|---|
| ERCOT | loads reducing at 4CP | 1,080 in 2024, 418 in 2022 | [NRG, citing ERCOT](https://www.nrg.com/assets/documents/energy-policy/ercot-transmission-costs-and-rate-design-remarks-on-feb-25-2025.pdf) |
| PJM | loads reducing at NSPL or PLC | not published | — |

**Movable share of a bill.** E3's [whitepaper](https://www.ethree.com/wp-content/uploads/2026/05/E3_Large-Load-Tariff-Whitepaper-1.pdf) runs a 25 MW data center at 89% load factor across five retail tariffs: the demand-charge share, the part a peak move can avoid, spans 0% (Georgia Power) to 55% (ComEd) while total bills span under 2:1. Retail structures, not wholesale bills; the wholesale share is computable from published bases and rates and was not computed. [DELTa](https://sepapower.org/large-load-tariffs-database/) held 77 large-load tariffs across 36 states as of 31 March 2026; [Halcyon](https://halcyon.io/large-load-tariff-tracker) tracks the rest.

---

## 5. Takeaways

- **Every load pays every layer.** Designations change the base, the rate, the menu, or add a credit.
- **Most of what large loads do is `move`.** 4CP and NSPL avoidance, ERS-period reduction, netting under standing rules: movement along bases the tariffs did not expect to be optimized against.
- **Products sit on the `sell` margin; loads are active on the `move` margin.** 4CP responders grew 2.6× in two years with nothing on offer; PRD, the one advance-commitment instrument, drew 0.08%.
- **`BASE` is rare and recent; `RATE` lives at state commissions; `MENU` at FERC.** Two levels of government, no evident coordination. The June 2026 orders are the first move to make `MENU` national.
- **ERCOT's missing adequacy layer is structural.** PJM charges adequacy on an explicit base; ERCOT recovers it through scarcity prices. Comparing the two compares a proxy against a price mechanism.
- **Curtailability is becoming a property of the load.** SB6 makes firm service revocable as a condition of connecting; Non-Firm Contract Demand lets a load elect it with a declared firm level. Neither is a charge.
- **Composition, not level, is where the wedge sits.** Bills span under 2:1; the share on a movable base spans 0% to 55%.

---

## 6. How the wargame reads this

The wargame folds adequacy and transmission into one investment layer with a peak-hour base and leaves hedge and supply out. Its load type has private parameters (value of following its profile, tolerated deviation, energy windows, chance a sold MW is called) and two public designations, selling reserve and curtailable. The inventory maps onto the type table as: 4CP and NSPL responders are movers; a CLR sells reserve continuously; Non-Controllable Load Resources, ERS, VECL, LLDMS and PJM emergency DR sell reserve in blocks; SB6 mandatory curtailment and Non-Firm Contract Demand are the curtailable load with a declared firm level. Conforming/Non-Conforming and the interconnection gates have no bill effect; PRD is a tariff feature; co-location needs generation behind the meter, which the model excludes.

---

## 7. Sources to read before relying on the detail

- **ERCOT Nodal Protocols §2.1** for Load Resource and CLR definitions; confirmed as a classification, subsection number not verified against text.
- **Nodal Protocols §6.6.11.2** for the ERS allocation formula; verified as structure only.
- **EL25-49 orders** for Non-Firm Contract Demand terms; paragraph pinpoints not verified.
- **PJM OATT Attachment H and Manual 18** for the zonal NSPL split and how a PRD value reduces the capacity obligation.
- **PJM firm point-to-point and Firm Contract Demand terms** for whether transferability carries over; this decides whether Firm Contract Demand distorts.
- **ERCOT participation figures** are 2023 vintage; the 85 GW denominator is approximate.
