"""FastAPI app: upload a meter export, get a ranked diagnosis. Nothing is stored."""
from __future__ import annotations

import io
import os

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from . import CAUSES, __version__
from .diagnose import diagnose_frame, load_default_model
from .io import DataError
from .penalty import ContractTerms

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
MAX_BYTES = 25 * 1024 * 1024

app = FastAPI(title="delta-t-doctor", version=__version__)

DEMOS = {
    "healthy": (),
    "fouled_coils": ("fouling",),
    "idle_coils_leaking": ("passing_valves",),
    "three_way_valves": ("constant_flow",),
    "excess_pressure": ("overflow",),
    "mixed_problems": ("fouling", "passing_valves"),
}


def _demo_frame(name: str, seed: int = 7) -> pd.DataFrame:
    from .sim.scenarios import make_sample
    rng = np.random.default_rng(seed)
    cfg, frames = None, []
    for m in (5, 6, 7, 8, 9, 10):
        s = make_sample(rng, 0, cfg=cfg, causes=DEMOS[name], month=m)
        cfg = s.cfg
        frames.append(s.frame)
    return pd.concat(frames, ignore_index=True)


def _terms(min_dt: float, pct: float, rate: float) -> ContractTerms:
    if not (3.0 <= min_dt <= 15.0):
        raise HTTPException(422, "Minimum delta-T must be between 3 and 15 C.")
    if not (0.0 <= pct <= 1.0):
        raise HTTPException(422, "Surcharge per degree must be a fraction between 0 and 1.")
    if rate < 0:
        raise HTTPException(422, "Rate must be zero or positive.")
    return ContractTerms(min_dt, pct, rate)


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


@app.get("/api/demo/{name}")
def demo(name: str, min_dt: float = 8.9, pct: float = 0.10, rate: float = 0.40):
    if name not in DEMOS:
        raise HTTPException(404, f"Unknown demo. Choose from: {', '.join(DEMOS)}")
    rep = diagnose_frame(_demo_frame(name), _terms(min_dt, pct, rate))
    d = rep.to_dict()
    d["truth_for_demo"] = list(DEMOS[name]) or ["none"]
    return JSONResponse(d)


@app.get("/api/demo/{name}.csv", response_class=PlainTextResponse)
def demo_csv(name: str):
    if name not in DEMOS:
        raise HTTPException(404, "Unknown demo.")
    return _demo_frame(name).to_csv(index=False)


@app.post("/api/diagnose")
async def diagnose(file: UploadFile = File(...), min_dt: float = Form(8.9),
                   pct: float = Form(0.10), rate: float = Form(0.40)):
    terms = _terms(min_dt, pct, rate)
    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 25 MB.")
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception:
        raise HTTPException(422, "Could not read the file as CSV.")
    try:
        rep = diagnose_frame(df, terms)
    except DataError as e:
        raise HTTPException(422, str(e))
    return JSONResponse(rep.to_dict())


@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))
