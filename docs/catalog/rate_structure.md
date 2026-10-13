# How every charge is built

## The dominant case

Eleven of the fourteen charged ERCOT layers are a single product — a pool, times
your share of a base:

$$
\Phi^{k}_{e}
\;=\;
\underbrace{\sigma^{k}}_{\text{sign}}\;
\underbrace{C^{k}}_{\text{pool}}\;
\underbrace{\frac{x^{k}_{e}(d_{e})}{\sum_{e'\in\mathcal{E}}x^{k}_{e'}(d_{e'})}}_{\text{share of base}}
$$

$d_{e}$ is the entity's demand path — the only thing it controls. Each layer
measures $x^{k}_{e}$ over its own **window**, which need not be the period
billed: transmission bills monthly on four intervals of the *previous* summer.

## Four forms in total

$$
\Phi^{k}_{e}\;=\;
\begin{cases}
\;\lambda_{t}\,x^{k}_{e}
  & \text{cleared price} \quad \text{— no pool} \quad (1)\\[6pt]
\;\sigma^{k}\,C^{k}\,\dfrac{x^{k}_{e}}{\sum_{e'}x^{k}_{e'}}
  & \text{average cost} \quad\ \, \text{— pool } C^{k} \quad (11)\\[10pt]
\;\bar{\rho}^{k}\,x^{k}_{e}
  & \text{posted rate} \quad\ \ \, \text{— no pool} \quad (1)\\[6pt]
\;\min\!\left\{\sigma^{k}C^{k}\tfrac{x^{k}_{e}}{\sum_{e'}x^{k}_{e'}},\;\kappa^{k}_{e}\right\}
  & \text{capped} \quad\ \ \ \ \ \ \ \text{— not a product} \quad (1)
\end{cases}
$$

Only the last is not a product of pool and share.

## The residual

$$
r^{k} \;=\; C^{k} \;-\; \sum_{e\in\mathcal{E}}\Phi^{k}_{e}
$$

The average-cost form gives $r^{k}\equiv 0$ by construction — the denominator is
the sum of the same quantities as the numerators. The other three carry no such
guarantee.

**The residual is not absorbed into the rate. ERCOT disposes of it three ways,
and two of them are separate bill items:**

$$
\begin{array}{lll}
r^{k}\to 0 & \text{recompute the same charge} & \text{no new line item}\\[3pt]
r^{k}\to C^{k'} & \textbf{becomes another layer's pool} & \textbf{a new line item}\\[3pt]
r^{k}\ \text{persists} & \text{rolled forward, or never} & \text{no reconciliation}
\end{array}
$$

### Examples — figures illustrative

- **Recomputed.** *Ancillary services.* Billed day-ahead on last week's comparable
  hour, say a 0.24% share; settlement recomputes on the realised 0.20% and
  refunds the gap. Same charge, revised.
- **Becomes a layer.** *Reliability commitment shortfall.* Your share implies \$1M
  but a cap holds you to \$400k. The \$600k becomes the **uplift** layer's pool.
  Likewise the whole market's imbalance becomes the **surplus credit** layer.
- **Persists.** *Transmission.* Rate set when ERCOT peak was 80 GW, billed on this
  summer's 85 GW — collections run 6.25% **above** cost of service until the next
  rate case. *System administration.* \$0.55/MWh against whatever ERCOT spent;
  nothing ever reconciles the two.

## The design space

The **form** is the first choice, and it decides whether the other dials exist
at all:

$$
\begin{array}{llll}
\textbf{form} & \textbf{pool in the charge?} & \textbf{residual} & \textbf{layers}\\[3pt]
\text{cleared price} & \text{no pool exists} & \text{undefined} & 1\\[3pt]
\text{average cost} & \text{yes} & r^{k}\equiv 0 & 11\\[3pt]
\text{posted rate} & \text{pool exists, but not in the charge} & r^{k}\neq 0 & 1\\[3pt]
\text{capped} & \text{yes, but bounded} & r^{k}>0\ \text{by design} & 1
\end{array}
$$

Only then do the remaining choices apply — and only the average-cost form uses
all of them:

$$
\begin{array}{lll}
\sigma^{k}\in\{+1,-1\} & \text{sign} & \text{charge or credit}\\[3pt]
x^{k}_{e}(d_{e}) & \text{base} & \text{metered energy, peak demand, shortfall}\\[3pt]
\text{window} & \text{when } x^{k}_{e} \text{ is measured} & \text{interval, hour, month, prior-year peaks}\\[3pt]
C^{k} & \text{pool} & \text{only if the form divides one}\\[3pt]
r^{k} & \text{residual} & \text{zero, a new layer, or unreconciled}
\end{array}
$$

## What the space leaves out

Theory points at a two-part tariff — a marginal part that carries the signal, and
a fixed part that recovers the rest without touching the margin:

$$
\Phi_{e} \;=\; \underbrace{\lambda_{t}\,x_{e}}_{\text{marginal}} \;+\; \underbrace{F_{e}}_{\text{fixed}}
$$

ERCOT's actual shape has the marginal part, then recovers everything else on a
*usage* share rather than as a fixed charge:

$$
\Phi_{e} \;=\; \lambda_{t}\,x_{e} \;+\; \sum_{k}\sigma^{k}C^{k}\frac{x^{k}_{e}}{\sum_{e'}x^{k}_{e'}}
$$

So the second term is never fixed — every pooled layer loads back onto usage.
The vocabulary has the slots a fixed part would need — **fixed**,
**contracted capacity**, **non-coincident peak** — and ERCOT uses none of them:
eleven of its fourteen charged layers sit on metered energy.
