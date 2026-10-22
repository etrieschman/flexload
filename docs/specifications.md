# Specifications

Every choice the prototype makes that §3 of the report does not state.
Written for the methodology section: decisions and the inputs a reader needs to
reproduce a number.
`assumptions.md` holds the full record, including choices that were rejected.

## Data and the window

The system is RTS-GMLC, a 73-bus test system with a year of hourly data, aggregated to one node.
Generators enter as offer blocks, one column per step of a unit's cost curve, so costs are linear and the merit order is a step function.
Each column records its physical unit, because the PJM reserve row is written per unit.
Wind, solar, rooftop solar and hydro take their available capacity from the day-ahead series and offer at variable O&M cost.
Storage, synchronous condensers and concentrating solar are excluded; none has a single-period dispatch model here.
Reserve offer cost is $c^r_j = 0$ for every generator, because RTS-GMLC does not report one.

An operating window is 168 hours, and the year is cut into 52 of them.
The load's preferred profile is carved out of the data: $\delta = \alpha \times$ hourly system load, and $d^\circ$ is the remainder, so system load at B0 is the data.
The default size is $\alpha = 0.05$.

## Tightness

One scale factor multiplies $\delta$ and $d^\circ$ in all 52 windows, so that the year's tightest hour has a reserve margin of 0.15.
Margin is spare capacity over system load at the tightest hour.
Scaling load rather than capacity keeps unit sizes and the merit order intact, and leaves $\alpha$ unchanged.
Only the annual peak window sits at the margin; the others keep their seasonal slack.

I set the margin at 0.15 because that is where ERCOT's energy-only prices pay the fleet's annual investment cost: rents of 2,516 M\$ against a cost of 2,500 M\$.
PJM at the same margin is short 1,057 M\$.
Above a margin of about 0.25 reserve is never scarce and the two markets earn the same rents.

## Market parameters

| parameter | value | source |
|---|---|---|
| load-following share $\gamma$ | 0.03 | placeholder; cite before publication |
| value of lost load $c^{\rm VOLL}$ | 5,000 \$/MWh | the level of ERCOT's system-wide offer cap; cite before publication |
| ORDC steps | 10 | choice |
| forecast error $\sigma_\varepsilon$ | fit to the data, one value for the year | RTS-GMLC |

## The operating reserve demand curve

$\varepsilon$ is the hourly net-load forecast error: real-time net load, averaged from five minutes to the hour, minus its day-ahead forecast, where net load is load less wind and solar.
I fit it as $N(0, \sigma_\varepsilon^2)$ with one $\sigma_\varepsilon$ for the year.
ERCOT fits $\varepsilon$ by season and hour block; that is a refinement.

The minimum contingency level $\underline R$ is the largest physical unit's nameplate capacity, the contingency PJM's reserve row protects against.
ERCOT sets $\underline R$ at 3,000 MW administratively.

The ten steps are spaced evenly in price.
Each step's height is the curve's value at the step's left edge, from $c^{\rm VOLL}$ down to $0.2\,c^{\rm VOLL}$ in tenths, and its width is the distance between the normal quantiles where the curve crosses those heights.
A final step of zero price and infinite width closes the curve, so reserve beyond the point where $\pi = 0.1\,c^{\rm VOLL}$ is valued at zero.

Under ERCOT, $C^{\rm sys}$ contains $-\sum_t \Pi_t$, which is large and negative when reserve is plentiful.
Welfare levels are therefore not comparable across the two markets.
Every cross-market comparison I report is a difference taken within a market.

## The cost of the investment layer

$\hat C^{\rm inv}$ is annual and comes from one B0 run over all 52 windows under the tightness scale above.
The window's share is $\hat C^{\rm inv} \cdot |\mathcal T| / 8760$, the same in every window.
The pool is floored at zero: a market whose prices already overpay the fleet has nothing left to collect, so the layer bills zero rather than crediting the load.

I do not compute the pool window by window.
A peak week's rents exceed its share of the fleet's fixed cost, so the pool goes negative — $-$178 M\$ on week 31 — and every tariff with an investment layer pays the load to consume at the peak.

Within a window, the pool is spread over the layer's hours, $\hat C^{\rm inv}_t = \hat C^{\rm inv}\,\mathbb I\{t \in \mathcal W^{\rm inv}\} / |\mathcal W^{\rm inv}|$.
Under $\tau_0$ all of it falls on $t^*$.

## The split pool as the load sees it

The exact split-pool charge $C^k x / (x + x^\circ)$ is concave in the load's base $x$, so a best response to it is not a QP.
Each price-taking belief linearizes it at the consumption $\hat x$ the belief expects, and the two beliefs linearize it differently.

The exogenous price-taker pays the posted average rate.
It reads the rate $C^k_t / (\hat x_t + x^\circ_t)$ at $\hat x = \delta$ and pays it on each MWh it bids, as ERCOT posts a provisional load-ratio share.
Its charge is $B^k = \sum_{t \in \mathcal W^k} \hat C^k_t\, x_t / (\delta_t + d^\circ_t)$.

The consistent price-taker knows its charge is its share of the pool.
It pays along the tangent of the exact charge at $\hat x$, with slope $C^k_t x^\circ_t / (\hat x_t + x^\circ_t)^2$, and $\hat x$ is the previous iterate of the fixed point.
Iterating moves the tangent with the bid, so the charge is exact when the iteration converges.

Both forms equal the exact charge where $x = \hat x$, which is the case at settlement.
The difference between them is the marginal price the load faces: an average rate in the first case, the true slope in the second.

A two-part charge sets its lump sum to the load's share, by its believed base, of what the marginal rate $\phi$ leaves of the pool.
$\tau_0$ uses no two-part charge.

## Two conventions in the load's problem

A load that sells reserve offers $\sigma^{\rm bid}_t = 0$ in the hours where its believed $\tilde\mu_t$ is below $c^\sigma_t$, rather than leaving the quadratic program indifferent there.

B1 for a curtailable load holds the operator's instrument — headroom above $d^{\rm firm}$ counts toward reserve — but consumes what it bids.
Letting the planner consume below its bid let it dodge energy conservation, and $S^{B1}$ then exceeded every realized $S$ by 5%.
Curtailment below the bid is the operator's scarcity action only.

## Metrics

Everyone else's bill is the same tariff with $d$ and $d^\circ$ swapped, with no reserve credit and no curtailment exemption.

The value of flexibility is $S^{B1} - S^{B0}$.

A belief's price error is $\frac{1}{|\mathcal T|}\sum_t |\tilde\lambda_t - \lambda_t|$, between the prices the bid answered to and the prices it produced.
For the consistent price-taker that is the last iterate's gap.

A split pool's marginal charge, used for alignment, holds the layer's cost $C^k$ fixed: $\partial B^k / \partial x = C^k x^\circ / (x + x^\circ)^2$.
This is exact for an ex-ante pool, which is what $\tau_0$ uses on both reserve and investment.
For an ex-post pool the term $(\partial C^k / \partial x)\, x / (x + x^\circ)$ is missing, and recovering it needs $\partial \mu / \partial d$, the price-setter's map.

Alignment is measured on consumption only.
A reserve seller's marginal incentive to offer $\sigma$, which is $\mu_t$, is not in the alignment table.

## Placeholders

| input | status |
|---|---|
| investment cost by RTS-GMLC category, \$/kW-yr: nuclear 600, coal 350, gas CC 110, gas CT 80, oil ST 300, hydro 300, wind 140, solar PV 90 | placeholder; RTS-GMLC reports no capital cost |
| $\psi \in \{0.5, 1, 2\}$ \$/MW²h, $\beta \in \{0.05, 0.2, 0.5\}$, $p \in \{0.02, 0.2\}$ | placeholder levels for the named types |
| $\gamma = 0.03$, $c^{\rm VOLL} = 5{,}000$ \$/MWh | values above; neither is cited yet |

## Solver

Dispatch is a linear program and every best response a quadratic program, both written in cvxpy and solved with Gurobi under an academic license.
HiGHS returns the same duals on week 31 and takes three times as long on the clearing.
Duals at a degenerate point of the merit order are solver-dependent.
