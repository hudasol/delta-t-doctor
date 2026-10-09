"""Latency and memory budget on this machine: parse + diagnose a one-year hourly file, a 5-year file and a 50-building portfolio."""
import os, sys, time, resource
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, pandas as pd
from deltat_doctor.api import _demo, _portfolio_frame
from deltat_doctor.diagnose import diagnose_frame, load_default_model
from deltat_doctor.io import read_table
from deltat_doctor.portfolio import diagnose_portfolio

load_default_model(); load_default_model(informed=True)
df, _ = _demo("fouled_coils")
raw = df.to_csv(index=False).encode()
def t(f):
    s = time.perf_counter(); r = f(); return time.perf_counter() - s, r
a, tbl = t(lambda: read_table(raw, "x.csv")); b, _ = t(lambda: diagnose_frame(tbl))
print(f"6 months hourly: {len(raw)/1e6:.1f} MB  parse {a:.2f}s  diagnose {b:.2f}s")
big = pd.concat([df.assign(timestamp=pd.to_datetime(df.timestamp) + pd.Timedelta(days=183 * k)) for k in range(10)], ignore_index=True)
rawb = big.to_csv(index=False).encode()
a, tbl = t(lambda: read_table(rawb, "x.csv")); b, _ = t(lambda: diagnose_frame(tbl))
print(f"5 years hourly:  {len(rawb)/1e6:.1f} MB  parse {a:.2f}s  diagnose {b:.2f}s")
pf = _portfolio_frame(50)
b, _ = t(lambda: diagnose_portfolio(pf))
print(f"50-building portfolio: {len(pf):,} rows  {b:.1f}s")
print(f"peak RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024:.0f} MB")
