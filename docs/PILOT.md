# Pilot proposal (draft)

**Goal:** measure, on real buildings, how often delta-t-doctor's top-ranked cause matches what a site inspection finds.

## Scope
* One operator or one property owner. 10-20 penalised buildings. 90 days.
* Data: 12 months of ETS meter data per building (timestamp, flow, supply and return temperature or energy, outdoor
  temperature if available). Hourly or 2-hourly is enough.
* Contract terms per building (minimum delta-T, surcharge rule, rate).

## Method
1. Run the tool blind on every building. Record the ranked causes before anyone visits.
2. An engineer inspects each building without seeing the output and records the dominant cause(s) among: fouling,
   passing valves, constant-flow (3-way or stuck-open) valves, excess pressure, other.
3. Compare. Report top-1 agreement, top-2 agreement, and where "other" occurred.
4. For buildings that are fixed, compare delta-T and surcharge before and after.

## Success criteria (set before the pilot)
* Top-2 agreement with inspection of at least 70% on buildings with a single dominant cause.
* No building where the tool is confidently wrong (probability above 0.8) on a cause the inspection rules out,
  in more than 1 of 10.
* Fix-order value: the first inspection target is the dominant cause in at least half of the buildings.

These thresholds are my starting proposal, and the pilot partner should adjust them.

## What the partner gets
A ranked inspection list and an AED business case per building, plus a written account of where the tool was wrong.

## Data handling
Files are analysed in memory by the web app and are not stored. A pilot would run the tool inside the partner's own
environment (Docker) so that no data leaves it.
