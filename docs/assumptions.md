# Assumptions

Each line is one modeling assumption, then the gap with reality and what would close it.
Code decisions are in the code and its history. Values marked placeholder are not calibrated.

## The system

- **One node.** Real reserve is deliverable or not by location, and prices differ by node; closing this needs the network and a reserve requirement per zone.
- **Hourly dispatch on the hour's mean of the real-time series stands for the real-time market.** Real-time markets clear every five minutes on a forecast, not on what the hour turned out to be; closing this needs five-minute dispatch with a forecast.
- **Every unit is online and available in every hour, with linear costs.** Real reserve comes from committed units within their ramp limits, and units are out for maintenance and forced outages; closing this needs unit commitment and an outage schedule.
- **Load is scaled so the year's tightest hour has a 6% margin, where ERCOT's rent pays the fleet.** Real margins come from entry and exit and are quoted on installed capacity, before outages; closing this needs a long-run model.
- **Dispatch does not model outages.** A real fleet has several percent of its capacity out at any time; closing this needs outage states that last and a dispatch that sees them.
- **Investment costs are round numbers by category, 1,757 M$ a year (placeholder).** Closing this needs a cited cost table.
- **Reserve offers are 10% of a unit's fuel cost, and wind, solar and hydro do not offer reserve (placeholder).** RTS-GMLC does not give reserve offers, and hydro does provide reserve; closing this needs offer data.
- **Other load is inelastic and is shed at 5,000 $/MWh.** Real load has some response below the cap, and the value of lost load varies by customer.
- **Storage, synchronous condensers and concentrated solar are left out.** Storage is a large source of reserve in ERCOT today.

## The reserve construct

- **One reserve product.** ERCOT and PJM each buy several (regulation, spinning, non-spinning, 30-minute); ERCOT splits one aggregate curve across them.
- **A contingency is a thermal unit: 400 MW, the largest. Both markets hold their top price up to twice that.** PJM's primary reserve is 1.95 times its largest online contingency, with a 3,000 MW floor and a 30-minute product above it; ERCOT's Board sets 3,000 MW, 2.2 times its 1,375 MW unit. Our largest unit is 4% of peak where theirs are 1 to 1.6%, so both hold more reserve against load here than in practice.
- **ERCOT's error is one normal for the year, fit to within-hour net-load error (sd 132 MW, 1.3% of peak), its mean shifted up by half a standard deviation.** ERCOT fits 24 normals by season and hour block to hour-ahead reserve error (summer 2023: mean 861 MW, sd 1,289 MW, about 1.5% of peak) and applies the same shift; closing this needs the fit by block and its mean.
- **The error is each five-minute net-load value less its hour's mean.** The operator does not know the hour's mean in advance, so the real error also has a forecast miss; closing this needs a forecast model or published hour-ahead data.
- **ERCOT's penalty price is the value of lost load less the fleet's highest fuel cost ($179).** ERCOT uses the value of lost load less the energy price in each interval; the highest fuel cost stands for that price at scarcity.
- **PJM's second step is read as an error: 48 MW with probability 0.35, at a penalty of $850.** PJM did not fit a distribution; its factors come from a 2007 event, and its second step is 190 MW, kept here as 190 over the 1,600 MW contingency in its memo.
- **The curve is steps priced at their left edge, and a normal's tail below 2% of the penalty price is priced at zero.** The true curve is smooth; more steps close this.

## The load

- **The load's preferred profile is a fixed share of system load in every hour.** A data center's profile is flatter than system load; closing this needs a load profile.
- **Two workloads with placeholder values: training (ψ 100, β 0.5, energy conserved over the week) and inference (χ 500, β 0.1, nothing conserved); κ 0.2 for both.** Closing this needs operator data on deferrable work and on the value of served requests.
- **Value is a strike on each MWh below the preferred profile plus a quadratic penalty on deviation.** Real costs of deferral depend on job length and deadlines; `hours_at_bound` in the summary shows how much of a result does not depend on this form.
- **The load's within-hour variability is normal with sd κ d_t, independent across intervals and of the system's error (κ placeholder).** GPU load swings are correlated across a site and may follow system conditions; closing this needs telemetry.
- **The tolerance β is symmetric and the same in every hour.**
- **A curtailable data center keeps (1 − β_min) of its lowest hour firm, bids at least that, and is curtailed unpaid.** Real contracts set a MW level and notice period, and the load may consume below its firm level by choice.
- **The load takes prices as given.** A load of 5 to 20% of the system moves prices; closing this needs the price-setter.

## Realized dispatch

- **Only reserve that cleared covers an imbalance.** In practice the five-minute energy dispatch also moves online units that were not paid as reserve, and regulation covers the fastest movement; closing this needs five-minute redispatch with ramp limits.
- **A unit trips with probability 1/MTTF each hour, for that hour only.** A real outage lasts a day or two and the operator redispatches around it; closing this needs outages that persist and a re-clearing.
- **The net-load error is the year's one real-time path.** One history has one set of bad days; closing this needs resampling by day.
- **Only a shortage costs.** A surplus also has a cost, in curtailment and frequency control.
- **Wind, solar and hydro units do not trip.**

## Tariff and settlement

- **Today's tariff bills energy at the price and the reserve pool by load share in every hour. PJM's form also bills the investment pool on the forecast peak hour; ERCOT's form does not bill it.** PJM's capacity charge uses five peaks, and the forecast peak hour stands for them. ERCOT's four coincident peaks recover transmission cost, which the model leaves out.
- **The investment pool is the fleet's cost less its rent over the year, floored at zero and spread evenly over the weeks.** PJM recovers this through a capacity auction. Under ERCOT nobody pays it: what prices leave unrecovered stays with the generators until some exit.
