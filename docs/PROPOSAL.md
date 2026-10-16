# One-page proposal (draft, for a utility or large property owner)

**What it is.** delta-t-doctor reads the ETS meter data you already collect and tells each penalised building which
of four common faults is most likely behind its low delta-T, how many dirhams each one costs per year, and what to
check on site. It is software only: no retrofit, no new sensors, and it runs inside your own network.

**Why now.** Delta-T surcharges are a recurring cost for owners and a plant-efficiency problem for operators.
Diagnosis today means a consultant visit per building. A ranked, quantified list lets you send the right engineer to
the right building first, with the right question.

**What exists.** An open-source prototype with a web app, an API, a portfolio mode and a printable owner report. It is
validated in simulation only. On held out buildings of the simulator it was trained on, macro AUROC is 0.97 and the first fix it
suggests recovers about 97% of the achievable delta-T gain; on differently built simulators it scores 0.68 to 0.77, and 0.705 on a third,
dynamic one (docs/WORLD_D.md). A fleet calibration step, measured in simulation, uses inspected buildings to close part of that gap.

**What does not exist yet.** Validation on real buildings. That is the point of the pilot. In an external test on a
different kind of system the tool failed, and it now says "not reliable" for buildings unlike its training data. We will
report the same honestly on your buildings.

**Proposed pilot.** 90 days, 10-20 buildings, 12 months of ETS data each, inspections as ground truth, success criteria
agreed up front. Details: [PILOT.md](PILOT.md).

**What we ask for.** A data extract (hourly readings preferred, contract terms) and access to inspection outcomes.
**What you get.** A ranked inspection list per building, an AED business case, a portfolio view, and a written account of
where the tool was wrong.

**Contact.** Huda Mueen, Co-Founder and CTO, Kanban Studios F.Z.E.
