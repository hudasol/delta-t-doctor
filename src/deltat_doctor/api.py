"""FastAPI app: upload a meter export, get a ranked diagnosis. Nothing is stored."""
from __future__ import annotations

import logging
import math
import os
import threading

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, HTMLResponse

from . import CAUSES, __version__
from .diagnose import diagnose_frame, load_default_model
from .io import DataError, read_table
from .penalty import ContractTerms
from .report import render_report
from .portfolio import diagnose_portfolio

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
MAX_BYTES = 25 * 1024 * 1024
MAX_CONCURRENT = int(os.environ.get("DTD_MAX_CONCURRENT", "4"))
log = logging.getLogger("deltat_doctor.api")
_slots = threading.BoundedSemaphore(MAX_CONCURRENT)

app = FastAPI(title="delta-t-doctor", version=__version__,
              description="Diagnose low delta-T in district-cooled buildings from ETS meter data. "
                          "Files are analysed in memory and never stored.")


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Cache-Control", "no-store")
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi")):
        resp.headers.setdefault("Content-Security-Policy",
                                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                                "img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'")
    return resp

DEMOS = {
    "healthy": (),
    "fouled_coils": ("fouling",),
    "idle_coils_leaking": ("passing_valves",),
    "three_way_valves": ("constant_flow",),
    "excess_pressure": ("overflow",),
    "mixed_problems": ("fouling", "passing_valves"),
}


def _demo(name: str, seed: int = 7):
    """Returns (frame, true design delta-T of the simulated building)."""
    from .sim.scenarios import make_sample
    rng = np.random.default_rng(seed)
    cfg, frames = None, []
    for m in (5, 6, 7, 8, 9, 10):
        s = make_sample(rng, 0, cfg=cfg, causes=DEMOS[name], month=m)
        cfg = s.cfg
        frames.append(s.frame)
    design = float(np.average(cfg.dt_design, weights=cfg.q_design_kw))
    return pd.concat(frames, ignore_index=True), design


def _terms(min_dt: float, pct: float, rate: float) -> ContractTerms:
    if not all(math.isfinite(v) for v in (min_dt, pct, rate)):
        raise HTTPException(422, "Contract terms must be finite numbers.")
    if not (3.0 <= min_dt <= 15.0):
        raise HTTPException(422, "Minimum delta-T must be between 3 and 15 C.")
    if not (0.0 <= pct <= 1.0):
        raise HTTPException(422, "Surcharge per degree must be a fraction between 0 and 1.")
    if rate < 0:
        raise HTTPException(422, "Rate must be zero or positive.")
    return ContractTerms(min_dt, pct, rate)


def _run(df, terms, design_dt):
    if design_dt is not None and not math.isfinite(design_dt):
        raise HTTPException(422, "Design delta-T must be a finite number.")
    if not _slots.acquire(blocking=False):
        raise HTTPException(503, "Server is busy. Try again in a few seconds.")
    try:
        return diagnose_frame(df, terms, design_delta_t_c=design_dt)
    except DataError as e:
        raise HTTPException(422, str(e))
    except FileNotFoundError:
        raise HTTPException(503, "The informed model is not installed on this server.")
    finally:
        _slots.release()


def _read_upload(file: UploadFile) -> pd.DataFrame:
    """Read at most MAX_BYTES from the upload (never buffers more), then parse."""
    raw = file.file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 25 MB.")
    try:
        return read_table(raw, file.filename or "")
    except DataError as e:
        raise HTTPException(422, str(e))


@app.get("/api/health")
def health():
    try:
        load_default_model()
        ok = True
    except FileNotFoundError:
        ok = False
    return {"status": "ok" if ok else "model-missing", "version": __version__, "causes": list(CAUSES)}


@app.get("/api/demos")
def demos():
    return {"demos": list(DEMOS)}


@app.get("/api/demo/{name}.csv", response_class=PlainTextResponse)
def demo_csv(name: str):
    if name not in DEMOS:
        raise HTTPException(404, "Unknown demo.")
    return _demo(name)[0].to_csv(index=False)


@app.get("/api/demo/{name}")
def demo(name: str, min_dt: float = 8.9, pct: float = 0.10, rate: float = 0.40,
         design_dt: float | None = None):
    if name not in DEMOS:
        raise HTTPException(404, f"Unknown demo. Choose from: {', '.join(DEMOS)}")
    df, true_design = _demo(name)
    rep = _run(df, _terms(min_dt, pct, rate), design_dt)
    d = rep.to_dict()
    d["demo_true_design_dt"] = round(true_design, 1)
    d["truth_for_demo"] = list(DEMOS[name]) or ["none"]
    return JSONResponse(d)


@app.get("/api/demo/{name}/report", response_class=HTMLResponse)
def demo_report(name: str, min_dt: float = 8.9, pct: float = 0.10, rate: float = 0.40,
                design_dt: float | None = None):
    if name not in DEMOS:
        raise HTTPException(404, "Unknown demo.")
    df, _ = _demo(name)
    return render_report(_run(df, _terms(min_dt, pct, rate), design_dt).to_dict(), f"Simulated building ({name.replace('_', ' ')})")


@app.post("/api/report", response_class=HTMLResponse)
def report(file: UploadFile = File(...), name: str = Form("Your building"), min_dt: float = Form(8.9),
                 pct: float = Form(0.10), rate: float = Form(0.40), design_dt: float | None = Form(None)):
    terms = _terms(min_dt, pct, rate)
    df = _read_upload(file)
    return render_report(_run(df, terms, design_dt).to_dict(), name[:80])


@app.post("/api/diagnose")
def diagnose(file: UploadFile = File(...), min_dt: float = Form(8.9),
                   pct: float = Form(0.10), rate: float = Form(0.40),
                   design_dt: float | None = Form(None)):
    terms = _terms(min_dt, pct, rate)
    df = _read_upload(file)
    return JSONResponse(_run(df, terms, design_dt).to_dict())


def _portfolio_frame(n: int = 12, seed: int = 21) -> pd.DataFrame:
    """A made-up portfolio of simulated buildings with a mix of faults, for the demo."""
    from .sim.scenarios import draw_cause_set, make_sample, sample_building
    rng = np.random.default_rng(seed)
    parts = []
    for b in range(n):
        cfg = sample_building(rng, b)
        causes = draw_cause_set(rng)
        design = float(np.average(cfg.dt_design, weights=cfg.q_design_kw))
        frames = [make_sample(rng, b, cfg=cfg, causes=causes, month=m).frame for m in (5, 6, 7, 8, 9)]
        f = pd.concat(frames, ignore_index=True)
        f.insert(0, "building_id", f"Tower {chr(65 + b)}")
        f["design_delta_t_c"] = round(design, 1)
        parts.append(f)
    return pd.concat(parts, ignore_index=True)


@app.get("/api/demo-portfolio.csv", response_class=PlainTextResponse)
def demo_portfolio_csv():
    return _portfolio_frame().to_csv(index=False)


@app.post("/api/portfolio")
def portfolio(file: UploadFile = File(...), min_dt: float = Form(8.9), pct: float = Form(0.10),
                    rate: float = Form(0.40), design_dt: float | None = Form(None)):
    terms = _terms(min_dt, pct, rate)
    df = _read_upload(file)
    if design_dt is not None and not math.isfinite(design_dt):
        raise HTTPException(422, "Design delta-T must be a finite number.")
    if not _slots.acquire(blocking=False):
        raise HTTPException(503, "Server is busy. Try again in a few seconds.")
    try:
        rep = diagnose_portfolio(df, terms, design_dt)
    except DataError as e:
        raise HTTPException(422, str(e))
    finally:
        _slots.release()
    log.info("portfolio buildings=%d", len(rep.buildings) if hasattr(rep, "buildings") else -1)
    return JSONResponse(rep.to_dict())


@app.get("/api/demo-portfolio")
def demo_portfolio(min_dt: float = 8.9, pct: float = 0.10, rate: float = 0.40):
    rep = diagnose_portfolio(_portfolio_frame(), _terms(min_dt, pct, rate))
    return JSONResponse(rep.to_dict())


app.mount("/fonts", StaticFiles(directory=os.path.join(WEB_DIR, "fonts")), name="fonts")


@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))
