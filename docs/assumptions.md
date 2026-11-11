# Assumptions

Each line is one modeling assumption, then the gap with reality and what would close it.
Code decisions are in the code and its history. Values marked placeholder are not calibrated.

## The system

- **One node.** Real reserve is deliverable or not by location, and prices differ by node; closing this needs the network and a reserve requirement per zone.
- **Hourly dispatch on the day-ahead series stands for the real-time market.** Real-time markets clear every five minutes on a short-horizon forecast; closing this needs five-minute dispatch on the real-time series.
- **Every unit is online and available in every hour, with linear costs.** Real reserve comes from committed units within their ramp limits, and units are out for maintenance and forced outages; closing this needs unit commitment and an outage schedule.
- **Load is scaled so the year's tightest hour has a 2.7% margin, where ERCOT's rent pays the fleet.** Real margins come from entry and exit and are quoted on installed capacity, before outages; closing this needs a long-run model.
- **Investment costs are round numbers by category, 1,757 M$ a year (placeholder).** Closing this needs a cited cost table.
- **Reserve offers are 10% of a unit's fuel cost, and wind, solar and hydro offer none (placeholder).** RTS-GMLC has no reserve offers, and hydro does provide reserve; closing this needs offer data.
- **Other load is inelastic and is shed at 5,000 $/MWh.** Real load has some response below the cap, and the value of lost load varies by customer.
- **Storage, synchronous condensers and concentrated solar are left out.** Storage is a large source of reserve in ERCOT today.

## The reserve construct

- **One reserve product.** ERCOT and PJM each buy several (regulation, spinning, non-spinning, 30-minute); ERCOT splits one aggregate curve across them.
- **A contingency is a thermal unit: 400 MW, the largest.** ERCOT's Board sets its minimum contingency level (3,000 MW), and PJM multiplies its largest contingency by a performance factor (1.2 in 2026).
- **ERCOT's error is one normal for the year, fit to hour-ahead net-load error (sd 295 MW, 3.1% of peak).** ERCOT fits 24 normals by season and hour block to hour-ahead reserve error, about 1.6% of its peak (from memory), and shifts the mean; closing this needs the fit by block.
- **The hour-ahead error is the five-minute real-time value less the day-ahead forecast, less that miss's mean over the hour before.** A real hour-ahead forecast uses more than the last hour's miss; closing this needs a forecast model or published hour-ahead data.
- **ERCOT's penalty price is the value of lost load.** ERCOT uses the value of lost load less the energy price.
- **PJM's second step is read as an error: 48 MW with probability 0.35, at a penalty of $850 (placeholder scaling).** PJM did not fit a distribution; its factors come from a 2007 event, and its second step is 190 MW, kept here as 12% of the contingency (from memory).
- **The curve is steps priced at their left edge, and a normal's tail below 2% of the penalty price is priced at zero.** The true curve is smooth; more steps close this.

## The load

- **The load's preferred profile is a fixed share of system load in every hour.** A data center's profile is flatter than system load; closing this needs a load profile.
- **Two workloads with placeholder values: training (ψ 100, β 0.5, energy conserved over the week) and inference (χ 1,000, β 0.1, nothing conserved).** Closing this needs operator data on deferrable work and on the value of served requests.
- **Value is a strike on each MWh below the preferred profile plus a quadratic penalty on deviation.** Real costs of deferral depend on job length and deadlines; `hours_at_bound` in the summary shows how much of a result does not depend on this form.
- **The load's within-hour variability is normal with sd κ d_t, independent across intervals and of the system's error (κ placeholder).** GPU load swings are correlated across a site and may follow system conditions; closing this needs telemetry.
- **The tolerance β is symmetric and the same in every hour.**
- **A curtailable data center keeps (1 − β_min) of its lowest hour firm, bids at least that, and is curtailed unpaid.** Real contracts set a MW level and notice period, and the load may consume below its firm level by choice.
- **The load takes prices as given.** A load of 5 to 20% of the system moves prices; closing this needs the price-setter.

## Realized dispatch

- **Only reserve that cleared covers an imbalance.** With every unit online, capacity that is not generating can respond too, within its ramp rate; closing this needs ramp limits on idle capacity.
- **A unit trips with probability 1/MTTF each hour, for that hour only.** A real outage lasts a day or two and the operator redispatches around it; closing this needs outages that persist and a re-clearing.
- **The net-load error is the year's one real-time path.** One history has one set of bad days; closing this needs resampling by day.
- **Only a shortage costs.** A surplus also has a cost, in curtailment and frequency control.
- **Wind, solar and hydro units do not trip.**

## Tariff and settlement

- **Today's tariff bills energy at the price, the reserve pool by load share in every hour, and the investment pool on the forecast peak hour.** ERCOT's four coincident peaks recover transmission cost, and PJM's capacity charge uses five peaks; the forecast peak hour stands for both.
- **The investment pool is the fleet's cost less its rent over the year, floored at zero and spread evenly over the weeks.** PJM recovers this through a capacity auction, and ERCOT through prices alone.
