# Assumptions

Each line is one modeling assumption, then the gap with reality and what would close it.
Values marked placeholder are not calibrated. The report's appendix table sets the same assumptions beside what ERCOT and PJM do, with sources.

## The system

- **One node.** Real reserve is deliverable or not by location, and prices differ by node; closing this needs the network and a reserve requirement per zone.
- **One real-time market, cleared hourly on the hour's mean of RTS-GMLC's real-time series.** Both markets clear day-ahead and then every five minutes on a forecast, not on what the hour turned out to be; closing this needs five-minute dispatch with a forecast.
- **Every unit is online and available in every hour, with linear costs.** Real reserve comes from committed units within their ramp limits, and several percent of a fleet is out at any time; closing this needs unit commitment and outage states that last.
- **Generators offer at cost.** Real offers are set by each generator.
- **Load is scaled by one factor so the year's tightest hour has a 6% margin, where the ERCOT construct's rent pays the fleet.** Real margins come from entry and exit and are quoted on installed capacity, before outages; closing this needs a long-run model.
- **Fixed costs are round numbers by technology, 1,757 M$ a year (placeholder).** Closing this needs a cited cost table. The margin above has to be retuned when they change.
- **Reserve offers are 10% of a unit's fuel cost, and wind, solar and hydro do not offer reserve (placeholder).** RTS-GMLC does not give reserve offers, and hydro does provide reserve; closing this needs offer data.
- **Other load is inelastic and is shed at 5,000 $/MWh, ERCOT's offer cap, under every construct.** Real load has some response below the cap, the value of lost load varies by customer, and PJM caps prices below ERCOT's cap.
- **Storage, synchronous condensers and concentrated solar are left out.** Storage offers reserve in ERCOT today.

## The reserve construct

- **A construct is a model of the imbalance, a statistic of it, and a penalty price.** ERCOT's curve has this form. PJM posts two prices and does not derive them from a model; the hard requirement is a benchmark that neither market uses alone.
- **One upward reserve product.** ERCOT buys Reg-Up, Reg-Down, RRS, ECRS and Non-Spin, each with its own curve since December 5, 2025; PJM buys regulation, synchronized, non-synchronized and 30-minute reserve, and its reserve prices add.
- **Trips enter each model as a contingency, a loss covered as if certain: the largest thermal unit, 400 MW, which is 4% of peak load.** No construct uses trip probabilities.
- **The ERCOT and PJM constructs both hold the penalty price up to twice the largest unit.** ERCOT's level is a fixed 3,000 MW. PJM's synchronized requirement is 130% of its largest online unit and its primary requirement 150% of that, on its 2025 slides; an earlier deck says 200% for the synchronized one.
- **The ERCOT construct's error is one normal for the year, fit to within-hour net-load error (standard deviation 128 MW, 1.3% of peak), its mean shifted up by half a standard deviation and floored at zero.** ERCOT fit one normal per season to hour-ahead reserve error, which includes forced outages, with the same shift; before 2019 it fit six time-of-day blocks per season. That curve was retired on December 5, 2025. Closing this needs published hour-ahead error.
- **The ERCOT construct's penalty is the value of lost load less the fleet's highest fuel cost, $179.** ERCOT used its offer cap less the energy price in each interval; the highest fuel cost stands for that price at scarcity.
- **The PJM construct has two outcomes: the requirement, and the requirement plus a margin of 12% of the largest unit with probability 35%, at a penalty of $850.** PJM's steps are $850 on the requirement and $300 on a margin of 190 MW, more in alerts. The 35% is the ratio of the two prices; the 12% is our scaling of the margin and is not sourced.
- **The hard requirement is the largest online thermal unit, priced at the value of lost load.** At that price dispatch sheds load before it runs short of reserve, so the curve and a constraint give the same dispatch.
- **Each curve is steps priced at their left edge, and a normal's tail below 2% of the penalty is priced at zero.** The true curve is smooth; more steps close this.
- **No construct's model includes the data center's variability.** That is the paper's question, and the refit in the learning section is the first step toward closing it.

## The data center

- **Its preferred profile is a fixed share of system load in every hour, 10%.** A data center's profile is flatter than system load; closing this needs a load profile.
- **Two workloads (placeholder values): training (penalty ψ 100, tolerance β 0.5, energy conserved over the week) and inference (strike χ 500, β 0.1, nothing conserved).** Closing this needs operator data on deferrable work and on the value of served requests.
- **Value is a strike on each MWh below the preferred profile plus a quadratic penalty on deviation.** Real costs of deferral depend on job length and deadlines; `hours_at_bound` in the summary shows how much of a result does not depend on this form.
- **Its within-hour variability is normal with standard deviation κ d_t, independent across intervals and of the system's error; κ is 0.2 for both workloads (placeholder).** GPU load swings are correlated across a site and may follow system conditions; closing this needs telemetry. With one κ the two workloads vary by the same amount.
- **The tolerance β is symmetric and the same in every hour.**
- **It takes prices as given.** A load of 5 to 20% of the system moves prices; closing this needs the price-setter.
- **It is firm, buys all its energy at wholesale, and sells no reserve.** Real large loads may be curtailable in an emergency, sell reserve as controllable load, buy through a retailer, or generate on site. The code has a curtailable contract and reserve-selling types; the paper does not use them.

## Realized imbalance

- **The imbalance is what tripped units take away, plus net-load error, plus the data center's variability.** Line trips, import cuts and ramps within the hour are left out.
- **Only reserve that cleared covers an imbalance.** In practice the five-minute dispatch also moves online units that were not paid as reserve, and regulation covers the fastest movement; closing this needs five-minute redispatch with ramp limits.
- **A thermal unit trips with probability 1/MTTF each hour, for that hour only; wind, solar and hydro do not trip.** A real outage lasts hours to days and the operator redispatches around it; closing this needs outages that persist and a re-clearing.
- **The net-load error is each five-minute net-load value less its hour's mean, on the year's one real-time path.** The real error also has a forecast miss, and one history has one set of bad days; closing this needs a forecast model and resampling by day.
- **Only a shortage costs.** A surplus also has a cost, in curtailment and frequency control.
- **A simulated year is one draw of each week, and simulated years differ only in trips and in the data center's variability.** There is one weather year, so the worst simulated year is bad luck with trips, not a bad year for weather.

## Tariff and settlement

- **Today's tariff, the same under every construct: energy at the price, the reserve pool by load share in every hour, and the investment pool by load share on each week's forecast peak hour.** Both markets bill energy at the price and reserve by real-time load share. PJM bills capacity on five peak hours a year. ERCOT has no capacity charge, and its four coincident peaks recover transmission cost, which the model leaves out.
- **The reserve pool is the reserve price times reserve bought, in a forecast with the data center inflexible.** In both markets the pool is set mostly day-ahead and trued up in real time; the model has no day-ahead market, so the forecast stands in for it.
- **The investment pool is the fleet's fixed cost less its rent over the year in that forecast, floored at zero and spread evenly over the weeks.** PJM recovers this through a capacity auction. Under the ERCOT construct rent covers the fleet at the 6% margin, so the pool is zero; what the data center's response then takes from rent stays with the generators.
