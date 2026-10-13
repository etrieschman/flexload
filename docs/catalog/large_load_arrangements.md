# Large Load Arrangements in US Wholesale Power Markets
### A catalog keyed to a layered bill decomposition

ERCOT and PJM in depth; other ISOs where materially different. Status date **20 August 2026**; items not operative on that date are in §5.

---

## 0. Conventions

$$B(p,q;z) \;=\; \sum_{k \in \mathcal{K}} \Phi^k\big(x^k(p,q);\, p,q;\, z\big), \qquad \mathcal{K} = \{\text{energy},\ \text{hedge},\ \text{reserve},\ \text{adequacy},\ \text{transmission},\ \text{supply}\}$$

- $x^k(p,q)$ — **base**: the function mapping actions to the quantity the charge is assessed on. Tariffs call this the **billing determinant**; the two mean the same thing and "base" is used throughout.
- $\Phi^k$ — **rate function**: the charge on that quantity. $\phi^k = \partial\Phi^k/\partial x^k$.
- $q = (d,h,g)$ — consumption, contracted financial volume, physically delivered behind-the-meter volume. $p = (b,f,c)$ — the matching prices.
- $\ell$ indexes loads. The load under study is left unindexed, so $d$ is its consumption and $d^{(\ell)}$ is some other load's. Aggregate net withdrawal served by the system is $d^{\rm sys} = \sum_\ell \big(d^{(\ell)} - g^{(\ell)}\big)$, and $C_{\rm sys}(d^{\rm sys})$ is the cost of serving it. All three are profiles over site $i$ and interval $t$; indices are suppressed unless they carry weight.
- $\Delta^k$ — the wedge on layer $k$: the load's marginal payment less the marginal system cost it causes. $\Delta^k=0$ is alignment.

### 0.1 The default bill

**Every load pays every layer.** No designation in this document exempts a load from transmission, reserve, or adequacy cost. A data center taking retail service, one settling at the node, and one behind a generator's meter all pay all of them. What a designation changes is the *quantity* the charge lands on, the *price* on that quantity, or *who is billed*.

| Layer | ERCOT base, absent any designation | PJM base, absent any designation |
|---|---|---|
| energy | net withdrawal $d-g$ at the node, 5-minute | net withdrawal $d-g$ at the node, 5-minute |
| hedge | none required; bilateral if taken | none required; bilateral if taken |
| reserve | QSE load-ratio share of ERCOT's ancillary service procurement cost | load-ratio share of PJM ancillary charges |
| adequacy | **no layer** — recovered through energy and reserve rates during scarcity | Peak Load Share, from Peak Load Contribution at the five highest RTO summer peaks |
| transmission | 4CP — demand in four summer 15-minute system peaks | Network Service Peak Load (zonal coincident peak) plus Schedule 12 |
| supply | zero unless the load sells | zero unless the load sells |

Tables in §§3–4 and Appendix A show what a designation changes against this baseline. Layers not listed are unchanged.

### 0.2 Operations

| Actor | Operation | What it does |
|---|---|---|
| rule | `BASE` | redefines the quantity charged, $x^k(\cdot)$ |
| rule | `RATE` | redefines the charge $\Phi^k(\cdot)$ on a fixed quantity |
| rule | `MENU` | adds or removes options the load may elect |
| rule | `GATE` | conditions whether, at what size, or on what terms the load may connect; assesses no recurring charge |
| load | `move` | changes $q$ under a fixed base and rate |
| load | `elect` | picks which option applies |
| load | `sell` | adds a credit to $B$ |

The first four are done to the load by a tariff, protocol, or order. The last three are what the load does in response.

Gaming 4CP is `move`; replacing 4CP with 12CP is `BASE`; a minimum-demand ratchet is `RATE`; ERCOT's ≥75 MW study requirement is `GATE`.

---

## 1. Axes

**(a) Commercial counterparty** — who the load buys from. (a1) retail customer of a load-serving entity, a regulated utility or in Texas a competitive retail electric provider; (a2) direct wholesale participant, settling at nodal prices through a qualified scheduling entity (ERCOT) or as or through a member (PJM); (a3) co-located behind a generator's meter, with only net withdrawal crossing the grid interface.

**(b) ISO representation** — how the load appears in the ISO's forecasts, network model, telemetry, and settlement. Runs from invisible inside an LSE's zonal aggregate, through individually modeled, to individually addressable with live telemetry.

**(c) Firmness of service** — what the load is entitled to withdraw, and the conditions under which that entitlement can be suspended. Firm, non-firm, curtailable, conditional, provisional.

**(d) Supply-side role** — whether the load also sells demand response, ancillary services, or capacity.

### 1.1 Relations among the axes

**(b) confers no authority; (c) and (d) do.** ERCOT can model a Non-Conforming Load in complete detail and still have no right to tell it anything. Authority to move a load comes either from a product it sold — ERCOT dispatches a Controllable Load Resource because the load is delivering what it sold, its firm entitlement untouched — or from a limit on what it was entitled to, as when §39.170 makes firm service revocable with no payment. What high (b) status supplies is *addressability*: a channel to send an instruction and telemetry to verify the response.

**(a3) forces (b) and (c).** Once generation sits behind the meter the interface quantity is $d-g$, and every layer based on net withdrawal moves mechanically. Both markets built dedicated categories in response: PURA §39.169 review in Texas, the Contract Demand services in PJM.

**(d) forces (b).** Payment requires registration in the construct that defines the product, and addressability is the precondition. Selling most load-side ancillary services in ERCOT requires Controllable Load Resource status, with its telemetry and dispatch obligations. One decision, not two.

**(a1) vs (a2) is independent of (d).** A retail customer can sell demand response through a third-party curtailment service provider or QSE without changing who supplies its energy.

**(c) is partly independent of (d).** A load can accept curtailable service unpaid. ERCOT's SB6 mandatory-curtailment obligation is the clean case: an interconnection condition, not a product.

### 1.2 The LSE interposition

For a load on (a1), most non-energy charges are assessed on its LSE, on the LSE's aggregate quantity — not on the load. The load faces a retail base its supplier chooses, and nothing forces that base to move with the wholesale base $x^k$. An LSE billed on 4CP may recover transmission from a customer class on non-coincident monthly peak: the customer's curtailment at system peak cuts the LSE's obligation but not its own bill.

This is a misalignment source independent of any defect in $x^k$ itself. Direct wholesale participation removes it — the load faces $x^k$ directly. That is the analytical content of the (a1)/(a2) choice.

In Texas the wires utility is not the LSE; competitive retail electric providers are. In most PJM states the wires utility is also the default LSE.

### 1.3 Commitments and the resale test

Several designations oblige a load to a contracted quantity $h$ — a hedge volume, a subscribed demand, a nominated reduction. Whether the commitment distorts turns on one question: **does its base reference realized consumption?**

**A hedge's does not.** A contract for differences on $h$ pays $(f-\lambda)h$ whatever the load consumes, so alongside energy at nodal price $\lambda$,

$$B \;=\; \lambda d + (f-\lambda)h \;=\; fh + \lambda\,(d-h), \qquad \frac{\partial B}{\partial d} = \lambda \ \text{ for any } h.$$

The marginal price is the spot price. The contract is a transfer, and $\Delta^{\rm hedge}=0$.

**A take-or-pay's does.** With $\alpha \in [0,1]$ the fraction of $h$ payable regardless of consumption — 0.85 in the Ohio tariff — the charge $\phi\max(d,\alpha h)$ has marginal rate $0$ below the floor and $\phi$ above. Both instruments contract for the same $h$, and $\alpha$ is the single dial between them: $\alpha=0$ is a free hedge, $\alpha=1$ full take-or-pay with no marginal price up to $h$.

**Resale collapses the difference.** A load that may resell the committed quantity at market price faces $\phi\,\alpha h + \lambda(d-\alpha h)$, the second term free to go negative — the hedge payoff again. Forbid resale and the same commitment distorts. The test is not financial versus physical but whether the quantity can be liquidated at the market price.

The record is thin. PJM firm point-to-point service is expressly transferable; whether Firm Contract Demand (§4.5) inherits that right is unsettled. A retail customer under a minimum-demand tariff has no route into the ISO market at all, so the barrier there looks structural rather than contractual — **uncited** either way.

These provisions floor a *demand* charge on kW, not energy on kWh, so only the demand share of the bill goes flat (§6.2).

---

## 2. Map

Functions common to both markets, with the layers each touches. The **axis** column gives which dimension from §1 the row sits on; rows marked *base* are not designations a load elects but quantities every load is charged on.

**Dispatch** means the ISO setting a resource's operating level in real time, in both directions. ERCOT's real-time market — Security Constrained Economic Dispatch, or SCED — runs every five minutes and issues each participating resource a **base point**: the MW level it is instructed to be at until the next run. A Controllable Load Resource receives base points that raise or lower its consumption, the same way a generator does. Demand response is the weaker case: an instruction to reduce, measured against an estimated baseline of what the load would otherwise have consumed.

| Function | Axis | Layers · op | ERCOT | PJM | Notes |
|---|---|---|---|---|---|
| Load modeled individually in the ISO's forecast rather than by class profile | (b) | none | Non-Conforming Load (§3.1) | — | ERCOT-only; PJM handles this through the interconnection study and the LSE's own forecast |
| Load whose consumption the ISO sets in real time, up or down | (b) → (d) | reserve `sell`; energy `sell` `move` | Controllable Load Resource (§3.2) | Economic DR via a curtailment service provider (§4.2) | Partial. A CLR takes five-minute base points continuously; PJM economic DR only reduces, against a baseline |
| Load that drops a block of demand on instruction | (b) → (d) | ERCOT reserve `sell`; PJM adequacy `sell` | Non-Controllable Load Resource (§3.2) | Emergency / Capacity Performance DR (§4.2) | Close, but paid through different layers: ERCOT through the AS stack, PJM through the capacity market |
| Standby curtailment bought in advance, called only in emergencies | (d) | reserve `sell` `move` | Emergency Response Service (§3.3) | Emergency DR, inside the capacity market (§4.2) | Structural mismatch. ERS is procured outside the ancillary services stack and cannot double-count; PJM emergency DR clears in the capacity auction |
| Charge on load for resource adequacy | *base* | adequacy `move` | — | Reliability Pricing Model obligation (§4.6) | **No ERCOT analogue.** No capacity market; adequacy is priced through scarcity energy and ancillary rates |
| Advance commitment to cut consumption at a price, lowering the forecast that sets reliability requirements | (b) | adequacy `elect`; energy `elect` | — | Price Responsive Demand (§4.3) | **No ERCOT analogue** |
| Quantity transmission charges are assessed on | *base* | transmission `move` | 4CP — demand in four summer 15-minute system peaks (§3.7) | Network Service Peak Load, zonal, plus Schedule 12 (§4.6) | Same family. ERCOT's is system-wide and summer-only; PJM's is zonal and split across two charges |
| Study process gating a new large load's connection | (c) | all six `GATE` | Large Load Interconnection Study, Planning Guide §9; Batch Study (§3.4) | Large Load Additions; Expedited Interconnection Track (§4.7) | Both recent; PJM's expedited path is conditioned on bringing generation |
| Rules for load served behind a generator's meter | (a3) | energy, transmission, adequacy — ERCOT `move`; PJM `BASE` `MENU` | PURA §39.169 review (§3.6) | Contract Demand services, EL25-49 (§4.5) | Same direction — restrict unpriced netting — but ERCOT acts arrangement by arrangement, PJM by general rule |
| Curtailment compelled as a condition of connecting, unpaid | (c) | none; `GATE` | SB6 / PURA §39.170 remote disconnect (§3.5) | — | **No PJM analogue** as a statutory condition |
| Choice among transmission services priced by how much firmness the load buys | (c) | transmission, adequacy `MENU` `elect` | — | NITS / Firm CD / Non-Firm CD (§4.5) | **No ERCOT analogue.** Only PJM has `MENU` on the transmission layer |
| Floor under the demand charge in a state retail tariff | (a1) | transmission, adequacy `RATE` | — (PUCT staff proposal, §5) | AEP Ohio DCT; Dominion GS-5 (Appendix A) | Set by state commissions, not the ISO. Georgia Power's equivalent sits outside any RTO |

---

## 3. ERCOT

### 3.1 Conforming and Non-Conforming Load

**Axis.** (b).
**Rule.** ERCOT Nodal Protocols §2.1 definitions — [protocol set](https://www.ercot.com/mktrules/nprotocols/current)

A load-forecasting and network-modeling classification. Conforming Load follows a recognizable pattern and is forecast by profile; Non-Conforming Load does not and is represented individually.

**Who designates.** ERCOT, on data submitted by the transmission or distribution service provider serving the load — the load is not the submitting party. Designation occurs at registration, or later when behavior diverges enough from the assigned profile to make profile-based forecasting unreliable, and is maintained through ERCOT's network model updates.

**Bill effect: none.** No charge is assessed on the classification, and it is not an interconnection or participation status. The load's six layers are exactly the §0.1 defaults. Its only billing relevance is indirect and system-wide: individually modeled load enters transmission planning explicitly, which affects the planned cost $\hat C^{\rm transmission}$ later allocated to everyone. That moves the level of a cost, not any load's base or rate.

### 3.2 Load Resource, Controllable Load Resource, Non-Controllable Load Resource

**Axis.** (b), unlocking (d).
**Rule.** Nodal Protocols §2.1 definitions, §6 real-time operations; qualification tests in the Nodal Operating Guides — [program page](https://www.ercot.com/services/programs/load/laar)

A Controllable Load Resource can controllably reduce or increase consumption under ERCOT dispatch control. A Load Resource can interrupt on ERCOT instruction under an ancillary service program. Non-Controllable Load Resources respond in blocks — ten-minute manual instruction, or automatic under-frequency relay — rather than to a continuous signal.

**Eligibility.** Registered through a QSE. Requires ERCOT-standard telemetry, demonstrated response capability, and passing the Load Resource qualification tests. A provisional CLR registration exists for resources not yet fully qualified. Periodic requalification applies.

**Obligations.** A CLR takes SCED base points on the same five-minute cadence as a generator — continuous, not event-driven (§2). Telemetry must be live. Failure to follow base points or respond to a deployment triggers non-performance charges and can end in decertification.

**Payment.** Capacity payments on awarded ancillary service capacity, plus energy settlement on deviations from base point. Products include ERCOT Contingency Reserve Service, Responsive Reserve, Non-Spinning Reserve, and Regulation Up/Down. Continuous-response products effectively require CLR status.

**What it constrains.** $d$, severely. Within its awarded range the load has ceded short-run control of consumption; it no longer solves $\max_d V(d) - B$ freely there, but is compensated for the value forgone.

**Bill effect.** Adds a credit on the reserve layer and changes how energy settles. Transmission (4CP) and the reserve *payment* obligation are unchanged from §0.1 — a CLR pays 4CP like any other load.

| Layer | Base | Rate | Op |
|---|---|---|---|
| reserve — as provider | awarded AS capacity (MW·h) by product | product clearing price; a **credit** | `sell` |
| reserve — as payer | QSE load-ratio share of AS procurement cost, unchanged | $\hat C\cdot\alpha$ | `move` |
| energy | deviation from SCED base point | $\lambda_{n(i)t}$ | `sell`, `move` |

**The reserve layer appears twice, with opposite signs.** As payer, the load is allocated a share of ERCOT's ancillary service procurement costs through its QSE on a load-ratio base. As provider, it receives the clearing price on awarded capacity. Registration adds the second term without touching the first. Net position can be either sign. Because the AS clearing price is market-determined and marginal, the provider term is aligned by construction while the payer term keeps the load-ratio-share defect — registering as a CLR adds an aligned term beside a misaligned one rather than fixing it.

### 3.3 Emergency Response Service

**Axis.** (d), decoupled from (b): ERS carries no modeling or telemetry status.
**Rule.** Nodal Protocols §3.14.3 (procurement §3.14.3.1, technical requirements §3.14.3.3); settlement §6.6.11.1–6.6.11.2. PUCT Substantive Rule 16 TAC §25.507 — [program page](https://www.ercot.com/services/programs/load/eils)

A competitively procured emergency reliability service deployed during an Energy Emergency Alert. It is **not** an ancillary service — the protocols say so and PUCT Rule §25.507 governs it separately — and it is not a registration status. Contracted ERS capacity may not simultaneously provide ancillary services in the contracted period. ERS resources are exempt from the modeling, telemetry, and current-operating-plan requirements other resource types carry; that exemption is the design point.

**Eligibility.** Contract through a QSE. Qualification rests on historical interval metering showing the offered reduction is achievable. Procured in standard contract periods across the December–November ERS year, in two ramp classes, ERS-10 and ERS-30.

**Obligations.** Reduce to the contracted level on deployment, which occurs when Physical Responsive Capability falls below 3,000 MW and is not expected to recover within thirty minutes after non-spinning reserves deploy. Performance is verified against the interval baseline.

**Payment.** Capacity payment on contracted MW, offer-capped at $80/MW/hr, with program spending capped at $50 million annually under Rule §25.507.

**What it constrains.** $d$ conditionally and rarely — materially lighter than CLR status.

**Bill effect.** Adds a credit on the reserve layer, and changes the base on which ERS *cost* is allocated back. Energy, transmission, and the ordinary AS load-ratio share are unchanged from §0.1.

| Layer | Base | Rate | Op |
|---|---|---|---|
| reserve — as provider | contracted ERS capacity (MW) | offered price ≤ $80/MW/hr; a **credit** | `sell` |
| reserve — as payer | QSE load during the ERS time period ÷ total ERCOT load in that period | $\hat C^{\rm ERS}\alpha^{\rm ERS}$ | `move` |

**ERS cost is allocated on an interval-specific base.** §6.6.11.2 allocates it by load-ratio share measured *within the ERS time period* — $\alpha = x/X$ exactly. Because ERS time periods are blocks fixed in the contract structure rather than peaks identified ex post, reducing consumption in them cuts allocated cost *with certainty* rather than in expectation. That is a cleaner `move` than 4CP, and an unambiguously misaligned one: $\hat C^{\rm ERS}$ is fixed by the procurement, so one load's reduction raises every other load's share and changes no system cost.

### 3.4 Large Load Interconnection

**Axis.** (c). A `GATE`; no recurring charge.
**Rule.** Planning Guide §9, added by PGRR115 (approved 15 May 2025) — [PGRR115](https://www.ercot.com/mktrules/issues/PGRR115). Modeling standards via NPRR1234 — [NPRR1234](https://www.ercot.com/mktrules/issues/NPRR1234), effective 15 December 2025. Batch Study process approved by the PUCT 18 June 2026 — [PUCT release](https://ftp.puc.texas.gov/public/puct-info/agency/resources/pubs/news/2026/PUCT-Approves-New-ERCOT-Process-to-Manage-Electricity-Requests-from-Data-Centers-Large-Power-Users.pdf). [Program page](https://www.ercot.com/services/rq/large-load-integration). Statute: SB6, effective 20 June 2025.

**Thresholds.** "Large Load" is ≥75 MW aggregate peak demand at a single site behind common points of interconnection. Sites ≥25 MW must be individually modeled. A reactive power study is required where a resource entity adds ≥20 MW of load at a site with existing generation.

**Process.** The TDSP submits the Large Load Interconnection Study for the interconnecting entity. Milestone-based queue gated on site control, permitting, and study payments. SB6 sets a statutory minimum study fee (cited at $100,000) and directs the PUCT to set financial security. Under the Batch Study process ERCOT groups projects rather than studying them serially, sorting speculative from ready projects and identifying required network build.

**Obligations.** Modeling and telemetry, a load commissioning plan, ride-through capability, subsynchronous oscillation monitoring, and disclosure of on-site backup generation.

**Bill effect: none recurring.** All six layers stay at the §0.1 defaults once connected. What the process determines is whether and at what capacity the load exists at all, and how it is modeled — which feeds the planning that sets $\hat C^{\rm transmission}$ for everyone.

### 3.5 SB6 curtailment obligations and voluntary programs

**Axis.** (c) for the mandatory part; (d) for the voluntary parts.
**Rule.** SB6, at PURA §§37.0561, 39.169, 39.170. NPRR1238, PUCT-approved 31 July 2025 — [NPRR1238](https://www.ercot.com/mktrules/issues/NPRR1238). Implementing projects: 58317 (grid emergency definition), 58481 (16 TAC §25.194), 58479 (co-location), 58480 (load forecasting).

Three mechanisms, routinely conflated:

**Mandatory curtailment (§39.170).** Large loads ≥75 MW interconnected after 31 December 2025 must install remote disconnection equipment enabling firm load shed. Critical load industrial customers and critical natural gas facilities are exempt. A condition of interconnection, unpaid.

**Voluntary Early Curtailment Load (NPRR1238).** Opt-in status to curtail on ERCOT instruction under defined grid stress, ahead of firm load shed.

**Large Load Demand Management Service.** Competitively procured voluntary reliability service for loads ≥75 MW, minimum 24-hour notice. Unavailable to loads already responding to wholesale price or already committed to another reliability or ancillary service — the same anti-double-counting logic as ERS.

**BTM deployment authority (§37.0561).** ERCOT may curtail behind-the-meter load and deploy on-site generation only where that generation serves ≥50% of site demand and cannot export, only in emergencies, and only after exhausting market services — frequency-responsive capability excepted.

**What it constrains.** $d$ without compensation (mandatory), $d$ contingently with compensation (VECL, LLDMS), and $g$ (§37.0561, which lets ERCOT call on the load's own generation).

**Bill effect.** Mandatory curtailment changes no layer: an affected load pays exactly the §0.1 default bill and receives nothing for accepting the obligation. That asymmetry is the point of the instrument. LLDMS adds a reserve credit; how its cost is allocated back is not yet settled (§5).

| Layer | Base | Rate | Op |
|---|---|---|---|
| all six (mandatory curtailment) | unchanged | unchanged; no payment either way | `GATE` |
| reserve — LLDMS provider | procured capacity | procurement price; a **credit** | `sell` |
| reserve — LLDMS payer | not settled (§5) | not settled | — |

### 3.6 Co-location and behind-the-meter arrangements

**Axis.** (a3), forcing (b) and (c).
**Rule.** SB6 / PURA §39.169; PUCT Project 58479. Effective 1 September 2025.

Net-metering arrangements between an existing generation resource and a co-located large load must be evaluated by ERCOT and approved by the PUCT, unless exempt — the principal exemption covering arrangements where the generation was, as of 1 January 2025, under majority common ownership with the large load's parent. Substantive conditions attach through the approval, so operative terms vary by arrangement rather than being specified in advance.

**What it constrains.** $g$ directly (whether the arrangement is permitted) and $c$ indirectly (what terms survive review).

**Bill effect.** The bases are the §0.1 defaults; what changes is the *value* of $d-g$ the load presents at them. Both the energy and transmission layers shrink because the metered quantity shrinks, not because any rule changed. Reserve cost allocation shrinks the same way through the QSE's reduced share.

| Layer | Base | Rate | Op |
|---|---|---|---|
| energy | $d-g$ at the interconnection, unchanged definition | $\lambda_{n(i)t}$ | `move` |
| transmission | 4CP demand, measured net | $\hat C^{\rm TCOS}/\overline{4\rm CP}$ | `move` |
| supply | $g$ | $c\cdot g$ | `sell` |
| review requirement | — | — | `GATE` |

**Why `move` and not `BASE`.** The base function is $x^{\rm energy} = d-g$ for every load; a co-located load is one that has chosen $g>0$. Nothing about the function changed. What *would* be `BASE` is a rule capping netting or excluding layers from it — which is what PJM did in EL25-49 (§4.5), and which the §39.169 review can impose here arrangement by arrangement rather than by general rule.

**The alignment problem is the same either way.** Netting reduces the base for layers whose cost driver is not net withdrawal. Reserve, adequacy, and transmission pay for the system's ability to serve the load when the co-located generator is unavailable; netting reduces the measured quantity without reducing that obligation.

### 3.7 Four Coincident Peak

**Axis.** None — not a designation. It is the transmission base faced by all ERCOT load, and the §0.1 default.
**Rule.** PUCT Substantive Rule 16 TAC §25.192 — [rule text](https://ftp.puc.texas.gov/public/puct-info/agency/rulesnlaws/subrules/electric/25.192/25.192.pdf). [Published data](https://www.ercot.com/mktinfo/data_agg/4cp)

Each TSP's rate equals its approved transmission cost of service divided by average ERCOT coincident peak demand across four 15-minute system peaks, one each in June, July, August, September; wholesale storage excluded. Each distribution service provider or directly connected large customer is billed on demand coincident with those intervals. ERCOT files each DSP's average 4CP demand by 1 December for the following year.

| Layer | Base | Rate | Op |
|---|---|---|---|
| transmission | demand in the four summer peak intervals | $\hat C^{\rm TCOS}\big/\sum_{\rm all}4\text{CP}$ | `move`, large |

**Avoidance is a prediction problem with an extreme payoff.** Peaks are identified ex post, so the load is forecasting; but a load can shed most of an annual transmission charge by curtailing for on the order of an hour a year, whether or not its consumption in the other 8,759 hours drives transmission investment. The rate is an average of an already-settled cost; the base is a proxy responding to a narrow, predictable window. Because $\hat C^{\rm TCOS}$ is fixed, one load's avoidance raises everyone else's rate — incidence, not alignment, and it never enters $\Delta$ for the avoiding load. Under active replacement (§5).

---

## 4. PJM

### 4.1 Retail customer vs. direct wholesale participation

**Axis.** (a1) vs (a2). Analytical content in §1.2.
**Rule.** PJM OATT; Operating Agreement; Reliability Assurance Agreement. "Eligible Customer" defined at OATT §I.1; see Manual 14A.

Most load is embedded in an LSE's zonal aggregate and sees wholesale charges only as its supplier chooses to pass them through. Where state retail law permits, a load may instead take unbundled transmission service and participate as or through a PJM member. Whether a large load may be served by a non-incumbent is a question of state retail law — a boundary FERC declined to resolve in EL25-49.

**Bill effect.** Both loads pay all six layers, and the wholesale cost underneath is identical. What changes is *which base the load itself faces*. A retail customer's charges land on whatever base its LSE writes into the retail rate; a wholesale participant's land on the ISO base directly.

| Layer | Retail (a1) — base the load faces | Direct wholesale (a2) — base the load faces |
|---|---|---|
| energy | retail contract price on metered $d$ | $\lambda$ on $d-g$, five-minute |
| transmission | retail class base chosen by the LSE | Network Service Peak Load, plus Schedule 12 |
| adequacy | retail class base chosen by the LSE | Peak Load Share, from Peak Load Contribution |
| reserve | bundled into the retail rate | load-ratio share of PJM ancillary charges |
| hedge | embedded in the retail rate, not separable | explicit $f,h$ the load contracts itself |

`elect`. The choice is not between two rates on one base; it is between two sets of bases. Nothing forces the retail base in the left column to move with the wholesale base in the right — the wedge described in §1.2.

### 4.2 Demand response and the curtailment service provider

**Axis.** (d) with (b); independent of (a).
**Rule.** OATT Attachment K; Operating Agreement Schedule 1 §3.3A; Manuals 11 and 18 — [Manual 18](https://www.pjm.com/-/media/DotCom/documents/manuals/m18.ashx)

A **curtailment service provider** is the PJM member that registers end-use load and bears its performance; the CSP–customer payment split is private contract. **Economic DR** offers reductions into the day-ahead or real-time energy market, settled on reduction against a customer baseline. **Emergency / Capacity Performance DR** clears the Reliability Pricing Model capacity auction and must reduce on dispatch during emergencies and performance assessment hours.

**Obligations.** Registration in DR Hub and eRPM; 15-minute interval metering; capacity commitments up to three years forward; Capacity Performance non-performance charges for failure during a performance assessment hour. For a load with firm uptime commitments the penalty tail, not the expected payment, usually governs.

**Bill effect.** Adds credits only. The load's transmission and adequacy *charges* remain on NSPL and Peak Load Contribution exactly as in §0.1; selling DR does not reduce them.

| Layer | Base | Rate | Op |
|---|---|---|---|
| energy — economic DR | reduction against baseline | LMP-based; a **credit** | `sell` |
| adequacy — capacity DR | cleared commitment (MW) | RPM clearing price, net of penalties | `sell` |

The baseline is an estimate rather than a measurement, and it can be gamed: a load that can inflate its baseline is paid for reductions it did not make. That is a base-proxy problem living inside the *supply* term rather than in a charge.

### 4.3 Price Responsive Demand

**Axis.** (b) with (d) characteristics, but nothing is sold. No ERCOT analogue.
**Rule.** RAA Schedule 6.1; Manuals 18 and 18B.

End-use load registered by a PRD Provider (an LSE) with hourly-or-finer metering, supervisory curtailment control, and a retail rate linked to real-time price so consumption falls automatically as price rises. A PRD Plan is due 15 January before the Base Residual Auction; the committed quantity — the Nominal PRD Value — reduces the load forecast used to set RTO and locational deliverability area reliability requirements.

**Payment.** None directly; the benefit is a reduced capacity obligation.

**Bill effect.** The only layer whose *charge* changes is adequacy, and it changes by shrinking the base rather than the rate. Transmission is untouched: a PRD load pays NSPL like any other.

| Layer | Base | Rate | Op |
|---|---|---|---|
| adequacy | Peak Load Contribution less the committed Nominal PRD Value | RPM price on the reduced obligation | `elect` |
| energy | metered $d$ under a price-linked retail rate | real-time LMP passthrough | `elect` |

**PRD is the mirror image of a ratchet.** A ratchet commits the load to a consumption *floor*; PRD commits it to a *reduction* once price passes a threshold — a sold call on its own consumption, compensated through a lower capacity obligation rather than a payment. Both are commitments and the resale test of §1.3 applies to both, but they bind in opposite directions.

### 4.4 Behind-the-meter generation

**Axis.** A partial form of (a3). Under revision — see §4.5, §5.
**Rule.** OATT §III.34.2, Netting of Behind the Meter Generation; Manuals 18 and 21.

BTMG delivers energy to load without using the transmission or distribution system. Qualifying output nets against load in the peak-demand calculations for network integration transmission service and for capacity obligation.

**Bill effect.** Three layers shrink at once, because the same generation output is subtracted from three different peak bases. Nothing exempts the load from those layers; the measured quantity simply falls.

| Layer | Base | Rate | Op |
|---|---|---|---|
| energy | $d-g$ | $\lambda$ | `move` |
| transmission | Network Service Peak Load, net of BTMG | zonal NITS rate | `move` |
| adequacy | Peak Load Contribution, net of BTMG | RPM price | `move` |
| supply | $g$ | $c\cdot g$ | `sell` |

`move` throughout under the standing rules. FERC's finding that this is unjust and unreasonable, and the netting cap that follows, are `BASE`.

### 4.5 Co-located load under EL25-49

**Axis.** (a3) forcing (c). The most consequential recent change in either market.
**Rule.** *PJM Interconnection, L.L.C.*, 193 FERC ¶ 61,217 (18 December 2025), Docket EL25-49-000 — [order text](https://www.gravel2gavel.com/files/2025/12/E-1-EL25-49-000.pdf); [FERC fact sheet](https://www.ferc.gov/news-events/news/fact-sheet-ferc-directs-nations-largest-grid-operator-create-new-rules-embrace). Show cause order 190 FERC ¶ 61,115 (20 February 2025). Compliance order 16 April 2026 (Docket ER26-1088). **Order on rehearing, clarification, compliance and paper hearing, 18 June 2026, Docket EL25-49-002** — [June 2026 order](https://www.ferc.gov/media/e-2-el25-49-002). Predecessor: Talen Susquehanna–Amazon ISA, Docket ER24-2172, rejected 1 November 2024, affirmed 16 April 2025. Approved 5–0.

**Definition.** Co-located load is end-use load physically connected to the facilities of an existing or planned customer facility on the interconnection customer's side of the point of interconnection. On compliance FERC rejected PJM's substitution of "point of change in ownership" for "point of interconnection."

**Three services — a `MENU` on the transmission layer, with different bases on the adequacy layer.** The eligible customer serving co-located load must take one:

| Service | Transmission charged on | Capacity charged on |
|---|---|---|
| Network Integration Transmission Service | gross demand | gross demand |
| Firm Contract Demand | contracted MW; min. one-year term; special protection schemes enforce the limit; penalties for excess withdrawal | contract demand |
| Non-Firm Contract Demand | contracted MW; terms one hour to one month; curtailed in emergencies; unreserved-use penalties | not charged a capacity product |

An interim non-firm service bridges customers who requested NITS while network upgrades are built.

This is the clearest `MENU` in either market: three options with genuinely different base functions on two layers, sorted by how much the load relies on the grid. A load electing Non-Firm Contract Demand buys a zero adequacy base and accepts curtailment risk in exchange — an explicit price on firmness that ERCOT does not offer.

**BTMG netting restriction — `BASE`.** FERC found existing netting unjust and unreasonable: co-located load is not fully accounted for in resource adequacy, and netting shifts cost to others. PJM was directed to *propose* a materiality threshold, to grandfather pre-existing contracts as of 18 December 2025, and to allow a three-year transition from that date. PJM's proposal sets the threshold at **50 MW** cumulative nameplate, with new loads above it ineligible for netting and backup generation excluded from the cap. The 50 MW figure is PJM's, not FERC's.

**Ancillary services — `BASE`, not `RATE`.** FERC found the tariff unjust and unreasonable for not addressing co-located load's use of regulation and black start, and directed that these be assessed on **gross** demand. The charge per unit is unchanged; the quantity charged on moves from net to gross. Additional baseline charges remain possible.

**Minimum charge.** A minimum transmission service charge for loads that stay synchronized to the grid while withdrawing almost nothing — a true `RATE` — was urged in Commissioner Chang's concurrence and placed within the scope of the paper hearing. Its final form is not settled (§5).

**What it constrains.** $g$ via the netting cap, $d$ via contract demand limits enforced by special protection schemes, and $c$ and the arrangement's structure via the service election.

**Bill effect.** This is the one place where the rules reach four layers at once. The direction is uniform: quantities that co-location had moved from gross to net are moved back toward gross, and the load can no longer shrink its transmission and adequacy bases by generating behind the meter.

| Layer | Base | Rate | Op |
|---|---|---|---|
| energy | $d-g$, netting capped above threshold | $\lambda$ | `BASE` |
| transmission | gross demand, or contract demand | zonal NITS rate; CD rates developing | `BASE`, `MENU` |
| reserve | gross demand for regulation and black start | existing ancillary rates | `BASE` |
| adequacy | gross demand / contract demand / none, by service | RPM price | `BASE`, `MENU` |
| supply | $g$ | $c\cdot g$ | unchanged |

### 4.6 Transmission and capacity bases

**Axis.** None — not a designation. These are the §0.1 defaults faced by all PJM load.
**Rule.** OATT network integration and point-to-point provisions; Schedule 9 (administrative charges); [Schedule 12](https://agreements.pjm.com/eTariff/transformedTariffs/oatt/Sections/4424.html) (transmission enhancement charges). RPM provisions in the RAA. [Billing reference](https://www.pjm.com/-/media/DotCom/markets-ops/settlements/custgd.pdf)

Network integration transmission service is charged on **Network Service Peak Load** — a zonal coincident-peak contribution, single-CP or 5-CP depending on zone, resetting 1 January — times the zonal NITS rate. Schedule 12 allocates required transmission enhancement costs by load-ratio share on non-coincident peak, or by solution-based distribution factor analysis. Capacity obligation runs through Peak Load Share, derived from Peak Load Contribution at the five highest RTO summer peaks, scaled by the forecast pool requirement and zonal factors.

| Layer | Base | Rate | Op |
|---|---|---|---|
| transmission | Network Service Peak Load | zonal NITS rate | `move` |
| transmission | non-coincident peak load-ratio, or DFAX | Schedule 12 charge | `move`, weaker |
| adequacy | Peak Load Contribution, five highest RTO summer peaks | RPM zonal clearing price | `move` |

**Versus 4CP.** Same family, less concentrated exposure. PJM's bases are zonal, so a load must predict its zone's peak rather than the system's; there are five intervals rather than four, and in some zones one; and transmission and capacity bases are defined separately, so avoiding one does not automatically avoid the other. ERCOT's single system-wide four-interval base, on a layer with no capacity counterpart, concentrates the whole `move` opportunity into one narrow window.

### 4.7 Large Load Additions and Expedited Interconnection Track

**Axis.** (c). A `GATE`.
**Rule.** Critical Issue Fast Path on Large Load Additions, initiated August 2025; Board decisional letter 16 January 2026 — [Board letter](https://www.pjm.com/-/media/DotCom/about-pjm/who-we-are/public-disclosures/2026/20260116-pjm-board-letter-re-results-of-the-cifp-process-large-load-additions.pdf). Expedited Interconnection Track, Docket ER26-1563, filed 27 February 2026, accepted 9 June 2026.

A large load addition is ≥50 MW at a single point of interconnection. The process produced a "bring your own new generation" expedited track and a connect-and-manage curtailable pathway for loads arriving without generation. The EIT is open to generation >250 MW UCAP, capped at ten projects annually, with no application window and a three-year site control requirement.

**Bill effect: none recurring.** Charges flow through §4.5 and §4.6 once connected. The operative change is that $g>0$ becomes a *condition of expedited access* rather than a purely economic choice — a load's behind-the-meter generation decision is no longer separable from its interconnection timeline.

---
## 5. Not operative as of 20 August 2026

### 5.1 The six-RTO show cause proceeding

On **18 June 2026** FERC issued FPA §206 show cause orders to all six RTOs/ISOs — **PJM EL26-67, SPP EL26-68, NYISO EL26-69, MISO EL26-70, CAISO EL26-71, ISO-NE EL26-72** ([news release](https://www.ferc.gov/news-events/news/ferc-launches-aggressive-targeted-action-speed-large-load-integration)). Each has 60 days to justify its tariff or file changes, and 30 days to report how it will ensure generation adequate to serve new large loads. Five reform categories: study and application processes; preventing cost shifting; accommodating co-location and behind-the-meter generation; **new transmission services for flexible large loads**; and studying generators serving electrically proximate loads.

Category 4 generalises the PJM `MENU`, pushing all six markets toward the interim-NITS / firm contract demand / non-firm contract demand structure. If it lands, `elect` becomes available on the transmission layer market-wide, and the ERCOT/PJM asymmetry in §2 becomes an ERCOT/everyone-else asymmetry. Non-RTO utilities were encouraged but not ordered to file.

### 5.2 Everything else pending

| Item | Docket / process | Posture | Timing |
|---|---|---|---|
| PJM co-located service rates, terms, minimum charge | EL25-49-002 | 18 June 2026 order set aside the December order in part, resolved the paper hearing in part, and established certain rates and terms as just and reasonable — but **no service product is fully finalized**; all constructs remain subject to revision | PJM and PJM transmission owners each owed a compliance filing within 60 days (~17 August 2026) |
| PJM BTMG netting: 50 MW threshold, grandfathering, three-year transition | EL25-49 compliance | PJM's proposal filed; industrial customer groups opposing | Pending |
| PJM further compliance on co-located load definition | ER26-1088 | 16 April 2026 order accepted interconnection pathways, rejected the definition substitution | Further filing ordered |
| PJM reliability backstop procurement | stakeholder process | March 2026 "refined thinking": PJM as administrator and counterparty, cost allocated to the load's area | Not filed |
| **ERCOT 4CP → 12CP**, 30-minute intervals | **PUCT Project 58484**, Evaluation of Transmission Cost Recovery | Staff draft report and proposed rule language (June 2026); proposed rule approved for publication July 2026 | **Statutory deadline 31 December 2026** |
| ERCOT minimum billing demand for new large loads on IOU distribution | Project 58484 (retail-side recommendations) | Proposed: also eliminating interconnection cost allowances, requiring large loads to fund a share of system upgrades, annual updates to class allocation factors | With the 12CP rule |
| ERCOT large-load payment on available capacity | PUCT Project 58000 | New rulemaking; would require a large load to begin paying based on transmission capacity made available to it, even before it consumes | Ongoing |
| ERCOT SB6 implementation | Projects 58317, 58481, 58479, 58480 | Rolling; NPRR1234 and PGRR115 in effect, PUCT rules being finalized | Rolling |
| ERCOT reliability standard and market design | ERCOT / PUCT | Batch Zero forecast mid-August 2026; reliability standard report December 2026 | PUCT market decisions expected H1 2027 |
| ERCOT LLDMS cost allocation | NPRR1238 implementation | Mechanics unsettled | Not effective |
| NERC computational load standards and registry criteria | RD26-7, order 16 July 2026 | Directed; NERC drafting | Standards due 31 December 2026; Phase II workplan 1 March 2027 |
| MISO demand-side resource reforms | ER25-1886 | Accepted subject to condition, June 2026 | From the 2028/29 planning year |
| AEP Ohio DCT challenge | Ohio Manufacturers' Association | Pending | Unresolved |
| Dominion transmission cost assignment | Virginia SCC, after 31 July 2026 order | Directed to file a policy assigning transmission costs to data centers | Draft due ~90 days |

**On 12CP.** If adopted this is `BASE`: twelve monthly peaks in 30-minute intervals replacing four summer 15-minute peaks. Staff cited winter peaks rivaling summer and shoulder-month reliability needs during generator maintenance. Twelve intervals spread across the year, measured in longer blocks, are harder to predict and costlier to avoid. But whether the new base is a *better proxy for transmission cost* is a separate question from whether it is harder to game. A base can be gaming-resistant and still misaligned.

**On the ERCOT minimum billing demand.** If adopted alongside 12CP, ERCOT would acquire both a harder-to-game base and a ratchet — `BASE` and `RATE` arriving together, from the same proceeding, with opposite effects on the marginal price of flexibility.

### 5.3 NERC and reliability status

Nothing here is a tariff charge and nothing is yet mandatory: the published material is advisory, the binding framework directed but unwritten.

**Trigger.** On 10 July 2024 in the Eastern Interconnection, a 230 kV fault — six sequential faults over 82 seconds — caused customer-initiated loss of approximately 1,500 MW of voltage-sensitive load, determined to be exclusively data-centre type. Frequency rose to 60.047 Hz and voltage to 1.07 per unit ([incident review](https://www.nerc.com/globalassets/our-work/reports/event-reports/incident_review_large_load_loss.pdf)). The concern is that large loads disconnect on voltage excursions in ways the system does not model.

**Status.** NERC's Large Loads Task Force output ([white paper](https://www.nerc.com/globalassets/who-we-are/standing-committees/rstc/whitepaper-characteristics-and-risks-of-emerging-large-loads.pdf), July 2025) and a September 2025 Level 2 industry recommendation are advisory. Under FERC Docket RD26-7-000 (16 July 2026), NERC must file standards and registry criteria for computational loads by 31 December 2026, with a Phase II workplan by 1 March 2027 — the first time loads would be registrable entities. Texas is moving in parallel on PUCT and ERCOT authority to require registration.

---

## 6. Order of magnitude

### 6.1 Participation

Two different things get counted. **Registered to sell** is capability contracted into a market construct, countable from auction and registration data. **Observed moving** is load reducing against a base with no product sold — inferred, and only partly published. A load can appear in both, and the two tables are not additive.

| Market | Registered to sell | Volume | Against system scale | Source |
|---|---|---|---|---|
| PJM | Demand Response cleared in RPM, 2027/28 BRA | 7,299 MW UCAP | 5.4% of 134,479 MW cleared | [PJM 2027/28 BRA](https://www.pjm.com/-/media/DotCom/about-pjm/newsroom/2025-releases/20251217-pjm-auction-procures-134479-mw-of-generation-resources.pdf) |
| PJM | Price Responsive Demand, 2027/28 | 106.5 MW (105.5 in 26/27) | 0.08% of cleared | [PJM BRA report](https://www.pjm.com/-/media/DotCom/markets-ops/rpm/rpm-auction-info/2026-2027/2026-2027-bra-report.pdf) |
| ERCOT | Load Resources, all types | ~8,300 MW, 575+ resources | ~10% of ~85 GW system peak | ERCOT 2023 — **uncited** |
| ERCOT | — of which Controllable | ~940 MW, 18 resources | ~1% of peak | ERCOT 2023 — **uncited** |
| ERCOT | — of which Non-Controllable | ~7,400 MW, ~557 resources | ~9% of peak | by subtraction |
| ERCOT | Emergency Response Service | MW **not located**; spending capped at $50M/yr | — | Rule §25.507 |

The ERCOT rows nest — Controllable and Non-Controllable are the two halves of Load Resources — and the split is lopsided: continuously dispatchable load is ~940 MW, about 1% of system peak, while nine tenths of registered capability responds only in blocks. The PJM rows do not nest; DR sells into the capacity market, PRD lowers the reliability requirement without selling anything.

| Market | Observed moving | Volume | Source |
|---|---|---|---|
| ERCOT | loads reducing at 4CP | 1,080 loads, up from 418 in 2022 | [NRG, citing ERCOT](https://www.nrg.com/assets/documents/energy-policy/ercot-transmission-costs-and-rate-design-remarks-on-feb-25-2025.pdf) |
| PJM | loads reducing at NSPL or PLC | **not located** — PJM publishes no equivalent count | — |

1,080 is a count of *loads*; 7,299 MW is *capacity*. The MW reduced at 4CP is not published, so only the trajectory is comparable: 2.6× in two years.

### 6.2 What share of a bill is movable

E3 modelled a 25 MW transmission-connected data centre, 89% load factor, identical shape, across five tariffs ([whitepaper](https://www.ethree.com/wp-content/uploads/2026/05/E3_Large-Load-Tariff-Whitepaper-1.pdf)). Shares computed from E3's per-unit charges at 194.9 GWh/yr and 25 MW billing demand; they reconcile to its totals except for Oncor.

| Tariff | Demand | Energy | Riders | Total |
|---|---|---|---|---|
| Georgia Power PLL-18 | 0% | 100% | — | 9.43 ¢/kWh |
| Dominion GS-4 | 27% | 50% | 23% | 6.54 ¢/kWh |
| Dominion GS-5 | 39% | 42% | 19% | 7.96 ¢/kWh |
| ComEd Extra Large Load | 55% | 33% | 12% | 8.86 ¢/kWh |
| Oncor transmission service | does not reconcile | | | 5.44 ¢/kWh |

What falls into each split:

| E3 category | Billed on | Layers it recovers | Movable by shifting peak? |
|---|---|---|---|
| Demand | $/kW of measured peak | transmission, adequacy, and in a vertically integrated utility the fixed cost of generation capacity | Yes — this is the `move` exposure |
| Energy | ¢/kWh | energy, plus fuel | Only by consuming less |
| Riders | mixed; E3 does not separate kW-based from kWh-based | fuel adjustment, transmission cost recovery, DSM, decommissioning, taxes | **Unknown** — the kW-based portion is movable and is not broken out |

Total bills span under 2:1; the demand share spans 0% to 55%, and is a lower bound on the fraction exposed to `move`.

**These are retail rate structures, not wholesale bills.** Georgia Power is a vertically integrated utility outside any RTO, so its 0% demand share is a rate-design choice with no wholesale base behind it. Dominion and ComEd are bundled utility tariffs inside PJM: their demand charges recover PJM's NSPL and RPM costs, but on a base the utility chose. Oncor is the one ERCOT entry and is wires-only, with no energy component, which is why it does not reconcile against the others. The table describes what an (a1) load faces and says nothing about (a2).

**For a wholesale participant the analogous share is computable, and was not computed here.** No rate designer chooses the split; it falls out of the ISO bases and rates, all published.

*ERCOT (a2).* Movable numerator: 4CP demand × the sum of applicable TSP rates, from PUCT-approved TCOS filings and ERCOT's annual 4CP filing (due 1 December). Denominator: add energy at the load's settlement point × MWh from ERCOT settlement point price history, plus the QSE's ancillary load-ratio share from ERCOT's AS cost reports. No adequacy term, so essentially the entire movable share is the single 4CP charge.

*PJM (a2).* Movable numerator: NSPL × zonal NITS rate (OATT Attachment H, filed per zone) + Schedule 12 charges + Peak Load Share × RPM zonal clearing price. Denominator: the same plus zonal LMP × MWh and PJM's ancillary billing determinants. Both bases and both rates are published per zone, so this computes zone by zone — and NITS rates and RPM clearing prices each vary by an order of magnitude across PJM, so the variation is the output, not an average.

Marked **not computed**; the inputs are public.

### 6.3 Coverage

[DELTa](https://sepapower.org/large-load-tariffs-database/), free from SEPA and NC Clean Energy Technology Center, holds 77 approved and proposed large-load tariffs across 60 utilities in 36 states as of 31 March 2026, 51 approved. Approvals accelerated — 29 in 2025 against 14 across 2018–2024 — and thresholds rose, roughly two-thirds of 2025 approvals landing between 50 and 150 MW. Halcyon's commercial [Large Load Tariff Tracker](https://halcyon.io/large-load-tariff-tracker) covers 218 filings, and is E3's source.

**In tension.** E3 gives Oncor's demand charge as $44/kW-yr in one table and $5.75 in another, neither reconciling to its total. E3 lists a 75% minimum capacity factor for GS-5 where Appendix A reports 85% T&D and 60% generation — possibly different provisions, unresolved. ERCOT participation figures are 2023 vintage, and the ~85 GW peak used as their denominator is approximate.

---

## 7. Takeaways

**Every load pays every layer.** No designation exempts one. Designations change the base, the rate, the menu of options, or add a credit.

**Most of what large loads do today is `move`.** Co-location under standing netting rules, 4CP and NSPL avoidance, ERS-period reduction — movement along fixed base functions the tariffs did not anticipate being optimized against. For coincident-peak bases, $\partial B/\partial d$ plainly does not track $\partial C_{\rm sys}/\partial d^{\rm sys}$ along the movement.

**Products sit on the `sell` margin; loads are active on the `move` margin.** ERCOT 4CP responders grew 2.6× in two years with no product on offer. Price Responsive Demand — the one instrument letting a load commit in advance for a different adequacy base — has drawn 0.08% of PJM's cleared capacity, which any commitment-based menu proposal has to explain.

**`BASE` is rare, recent, and concentrated in co-location.** The EL25-49 netting cap and gross-demand ancillary bases are the operative instance; 12CP would be the second. Both are regulators responding to `move` that grew large enough to notice.

**`RATE` lives at the state commissions, `MENU` at FERC.** Minimum-demand ratchets arrive through state rate cases; the transmission-service menu arrives through FERC. Two levels of government, two operations, no evident coordination. The June 2026 six-RTO orders are the first move toward making `MENU` national.

**ERCOT's lack of a capacity layer is structural, not parametric.** PJM charges adequacy on an explicit base; ERCOT recovers the same cost through energy and reserve rates during scarcity. Comparing $\Delta^{\rm adequacy}$ across the two compares a proxy against a rate mechanism, not two proxies.

**No instrument mandates hedging; several mandate commitment.** The Appendix A ratchets and PJM Firm Contract Demand oblige a load to a contracted level $h$; PRD obliges it to a reduction. None is a hedge — each references realized consumption. Whether they distort turns on resale, which is unsettled (§1.3).

**Composition, not level, is where the wedge sits.** Total bills span under 2:1 across the tariffs in §6.2; the share riding on a movable base spans 0% to 55%. If most loads face tariffs putting little on a peak base, thin participation may reflect loads having no reason to care rather than badly designed instruments. Testable against tariff-level data.

---

## Appendix A. State retail tariffs

The rate structure a **state commission** approves for a regulated utility to bill a large retail customer, sitting on top of whatever the ISO charges. This is where `RATE` lives; the ISO markets have almost none of it. It is also what an (a1) load actually faces in place of the wholesale base (§1.2).

The three below sit in three different wholesale contexts — AEP Ohio and Dominion inside PJM, Georgia Power vertically integrated outside any RTO — and all three do the same thing.

| Tariff | Threshold | Commitment | Rule |
|---|---|---|---|
| [AEP Ohio Data Center Tariff](https://www.aepohio.com/company/about/rates/data-center-tariff/) — effective 23 July 2025 | >25 MW; >1 MW crypto | 85% of subscribed demand monthly, ~12 yr; exit fee ≥3 yr of minimum charges | PUCO 24-508-EL-ATA ([release](https://puco.ohio.gov/news/puco-orders-aep-ohio-to-create-data-center-specific-tariff)) |
| Dominion GS-5 — approved Nov 2025, **effective 1 Jan 2027** | ≥25 MW | 85% of contracted T&D demand, 60% of generation demand, 14 yr, 4-yr ramp | Virginia SCC PUR-2025-00058 ([release](https://www.scc.virginia.gov/about-the-scc/newsreleases/release/scc-issues-order-on-dev-biennial-review-2025/scc-rules-in-dev-biennial-review-case.html)) |
| Georgia Power — effective 1 Feb 2025 | ≥100 MW | Customised contract, up to 15 yr, minimum bill unspecified in rule | Georgia PSC Docket 44280 ([fact sheet](https://psc.ga.gov/site/downloads/datacenterfactsheet.pdf)) |

**Bill effect.** All three are minimum-demand floors: `RATE`, not `BASE`. The base is unchanged — still a peak demand measurement — but below the floor it carries no marginal price, so the private return to curtailment is zero exactly where system value may be highest. Dominion's split floors put kinks at two utilisation levels. Georgia Power's terms are contract-specific, so the filed contracts are the primary source for any particular arrangement.

**Texas is the contrast, and it is narrowing.** Generation and retail are competitive, so large loads contract with retail providers at negotiated, often wholesale-indexed prices. Texas has used interconnection conditions and curtailment obligations where other states used rate structure — `GATE` and constraints on `move` rather than `RATE`. PUCT staff have now proposed a minimum billing demand for new large loads on investor-owned distribution (§5), which would import the floor. The two instruments push flexibility in opposite directions: a payment floor makes curtailment worthless below a threshold, while a curtailment obligation compels reduction the load did not choose and is not paid for.

Indiana (AES Indiana, Indiana Michigan Power) and Pennsylvania have large-load tariffs at their commissions — docket numbers **uncited**. §6.3 points to the databases holding the rest.

---

## Appendix B. Sources to read before relying on the detail

- **ERCOT Nodal Protocols §2.1** — the live subsection defining Conforming and Non-Conforming Load. Confirmed as a definitional and modeling classification; the subsection number was not verified against protocol text.
- **193 FERC ¶ 61,217 and the 18 June 2026 order (EL25-49-002)** — paragraph-level pinpoints. Substance is corroborated across multiple analyses citing both; no pinpoint was verified against the order texts.
- **ERCOT Nodal Protocols §6.6.11.2** — the ERS allocation formula, verified as structure only.
- **PJM OATT Attachment H and Manual 18** — the zonal split between single-CP and 5-CP NSPL bases, and the mechanics by which a Nominal PRD Value reduces the capacity obligation.
- **PJM firm point-to-point service agreement and the Firm Contract Demand terms** — whether the transferability of the former carries into the latter. This decides whether Firm Contract Demand distorts (§1.3).
- **State resource-adequacy and procurement rules imposed on LSEs** — not surveyed. §7's claim that no instrument mandates hedging rests on the tariffs surveyed here; some state rules may pass a hedging obligation through to large customers by contract.
