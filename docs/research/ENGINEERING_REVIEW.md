# Engineering review, October 2026

A cold read of the repository by someone who had not seen it: README first, then the running app, the source, the tests and the evidence documents. Scores are out of 10.

## Score: 7.0

| Area | Score | Reading |
|---|---|---|
| Code and API | 8.0 | Small modules with clear responsibilities. Request body limit, concurrency cap, structured audit log, no storage of uploads. 124 tests, 88% line coverage (CLI 56%, evaluation helpers 52%). |
| Evidence | 7.5 | Three simulated worlds, grouped CV, bootstrap intervals, preregistered predictions with failures kept, eight baselines. Weak point: the shipped model has no accuracy lead over plain boosting, so its case rests on calibration and abstention, which the front page does not say. |
| Product and dashboard | 6.0 | Complete and accessible (Arabic, RTL, dark, print), but the look is generic: a teal card layout with a stock heading font, one chart, no picture of the plant itself. Results are a list; nothing shows where in the ETS the problem sits. |
| Documentation | 6.5 | Thorough, but the README opens with a paragraph of caveats, and twenty files sit at the top of `docs/`. |
| Tooling | 7.0 | CI on three Python versions, hashed lock file, SBOM, Docker. No type checking, no pre commit hooks, no typed package marker. |
| Real data | 3.0 | No labelled field data. Real district heating files were parsed only. Nothing in the repository can raise this score except a pilot. |

## Where it loses points

1. **Dashboard identity.** The interface is readable but anonymous. A reviewer opening it sees a generic card layout. The page has no schematic of the energy transfer station, so the idea of "which part of the plant" never appears visually.
2. **Caution density.** The README status block, the dashboard trust line, the rate hint and the footer all repeat the same limitation. One statement in one known place reads as honest; five read as nervous.
3. **Positioning against baselines.** The strongest honest claim is calibrated probabilities, dirham ranked actions and abstention. That is not stated where a reviewer first looks.
4. **Test gaps.** `cli.py` and `evaluate.py` are the least covered modules.
5. **Static analysis.** No mypy, no pre commit, no `py.typed`.
6. **Docs layout.** User facing documents and process documents share one directory.
7. **Release.** The v1.3.0 tag could not be pushed from the cloud environment.

## Plan

| Step | Change | Done when |
|---|---|---|
| 1 | Rebuild the dashboard visual layer: pearl and sakura palette, a monospace numeric face for readings, an ETS schematic drawn in SVG that shows supply, return and the flagged component, tighter copy | Screenshots of home, single building and portfolio views; all existing UI tests pass |
| 2 | Cut repeated caution text to one footer line and one LIMITATIONS link | No caution string repeated across README and UI |
| 3 | README: open with what the tool does and a baseline table; move the evidence summary below | README first screen has no caveat block |
| 4 | CLI and evaluation tests | Coverage above 90% overall, CLI above 80% |
| 5 | mypy on `src`, pre commit with ruff, `py.typed` | `mypy src` clean in CI |
| 6 | Release v1.4.0 | CHANGELOG, notes, tests green; tag pushed or documented |

Items outside the repository: a native Arabic review of the interface strings, and a real pilot with blind inspections.
