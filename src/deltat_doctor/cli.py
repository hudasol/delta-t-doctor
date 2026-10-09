"""Command-line interface: diagnose a CSV, make a demo CSV, or serve the web app."""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from . import CAUSES
from .penalty import ContractTerms


def _fmt_report(r) -> str:
    d = r.to_dict()
    lines = []
    lines.append(f"Period: {d['n_days']:.0f} days in {d['n_windows']} window(s)")
    lines.append(f"Flow-weighted delta-T: {d['delta_t_c']:.2f} C (contract minimum {d['min_delta_t_c']:.1f} C)")
    lines.append(f"Estimated annual surcharge at illustrative/contract rate: AED {d['annual_surcharge_aed_estimate']:,.0f}")
    lines.append(f"Probability some fixable cause is present: {d['p_any_cause']:.0%}")
    lines.append("")
    lines.append("Likely causes, ranked by expected annual saving:")
    for i, f in enumerate(d["findings"], 1):
        lines.append(f"  {i}. {f['label']}")
        lines.append(f"     probability {f['probability']:.0%} | expected delta-T recovery +{f['expected_dt_gain_c']:.2f} C | "
                     f"expected saving AED {f['expected_saving_aed_per_year']:,.0f}/yr")
    for n in d["notes"]:
        lines.append(f"\nNote: {n}")
    lines.append(f"\n{d['disclaimer']}")
    return "\n".join(lines)


def cmd_diagnose(a):
    from .diagnose import diagnose_csv
    terms = ContractTerms(a.min_dt, a.pct, a.rate)
    rep = diagnose_csv(a.csv, terms)
    print(json.dumps(rep.to_dict(), indent=2, default=float) if a.json else _fmt_report(rep))


def cmd_simulate(a):
    from .sim.scenarios import make_sample
    rng = np.random.default_rng(a.seed)
    causes = tuple(c for c in a.causes.split(",") if c)
    for c in causes:
        if c not in CAUSES:
            sys.exit(f"unknown cause {c!r}; choose from {', '.join(CAUSES)}")
    frames = []
    cfg = None
    import pandas as pd
    for m in range(1, 13):
        s = make_sample(rng, 0, cfg=cfg, causes=causes, month=m)
        cfg = s.cfg
        frames.append(s.frame)
    df = pd.concat(frames, ignore_index=True)
    df.to_csv(a.out, index=False)
    print(f"wrote {len(df)} hourly rows ({a.causes or 'healthy'}) to {a.out}")


def cmd_serve(a):
    import uvicorn
    uvicorn.run("deltat_doctor.api:app", host=a.host, port=a.port, reload=False)


def main(argv=None):
    p = argparse.ArgumentParser(prog="deltat-doctor", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("diagnose", help="diagnose a meter-export CSV")
    d.add_argument("csv")
    d.add_argument("--min-dt", type=float, default=8.9, help="contract minimum delta-T, deg C")
    d.add_argument("--pct", type=float, default=0.10, help="surcharge fraction per degree below minimum")
    d.add_argument("--rate", type=float, default=0.40, help="AED per RT-hr (illustrative default)")
    d.add_argument("--json", action="store_true")
    d.set_defaults(fn=cmd_diagnose)

    s = sub.add_parser("simulate", help="write a simulated year of ETS data for a chosen fault set")
    s.add_argument("--causes", default="fouling", help=f"comma list from: {', '.join(CAUSES)} (empty = healthy)")
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--out", default="demo_ets.csv")
    s.set_defaults(fn=cmd_simulate)

    v = sub.add_parser("serve", help="run the web app")
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--port", type=int, default=8000)
    v.set_defaults(fn=cmd_serve)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
