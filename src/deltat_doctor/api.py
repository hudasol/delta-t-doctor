"""FastAPI app: upload a meter export, get a ranked diagnosis. Nothing is stored."""
from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import functools
import math
import os
import threading
import time
import uuid
from typing import Any

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, HTMLResponse

from . import CAUSES, __version__
from .diagnose import diagnose_frame, load_default_model
from .io import DataError, read_table
from . import provenance
from .penalty import ContractTerms
from .report import render_report
from .portfolio import diagnose_portfolio

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
MAX_BYTES = 25 * 1024 * 1024
MAX_CONCURRENT = int(os.environ.get("DTD_MAX_CONCURRENT", "4"))
log = logging.getLogger("deltat_doctor.api")
_slots = threading.BoundedSemaphore(MAX_CONCURRENT)


def _slot():
    """Dependency: at most MAX_CONCURRENT heavy requests (parse, simulate, diagnose) at once; others get a 503."""
    if not _slots.acquire(blocking=False):
        raise HTTPException(503, "Server is busy. Try again in a few seconds.")
    try:
        yield
    finally:
        _slots.release()

app = FastAPI(title="delta-t-doctor", version=__version__,
              description="Diagnose low delta-T in district-cooled buildings from ETS meter data. "
                          "Files are analysed in memory and never stored.")


_rid: contextvars.ContextVar[str] = contextvars.ContextVar("rid", default="-")


def audit(event: str, **kw) -> None:
    """One JSON log line per event. Never logs file contents, only sizes, hashes and outcomes."""
    log.info(json.dumps({"event": event, "request_id": _rid.get(), "version": __version__, **kw}, default=str))


class BodyLimit:
    """Pure ASGI middleware: counts the request body as it streams and stops at the limit, with or without Content-Length.

    Starlette would otherwise spool a whole multipart body to disk before any handler could look at it.
    """

    def __init__(self, app, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        seen, over, sent413 = 0, False, False

        async def recv():
            nonlocal seen, over
            if over:
                return {"type": "http.disconnect"}
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > self.limit:
                    over = True
                    return {"type": "http.disconnect"}
            return msg

        async def snd(msg):
            # whatever the app answers after the limit was crossed (its parser sees a disconnect) is replaced by one 413
            nonlocal sent413
            if not over:
                return await send(msg)
            if not sent413 and msg["type"] == "http.response.start":
                body = b'{"detail":"File is larger than 25 MB."}'
                sent413 = True
                await send({"type": "http.response.start", "status": 413,
                            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                                        (b"connection", b"close")]})
                await send({"type": "http.response.body", "body": body})

        try:
            await self.app(scope, recv, snd)
        except Exception:
            if not over:
                raise
        if over and not sent413:
            body = b'{"detail":"File is larger than 25 MB."}'
            await send({"type": "http.response.start", "status": 413,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})


app.add_middleware(BodyLimit, limit=MAX_BYTES + 1024 * 1024)


@app.middleware("http")
async def security_headers(request, call_next):
    rid = uuid.uuid4().hex[:12]
    _rid.set(rid)
    t0 = time.perf_counter()
    cl = request.headers.get("content-length")
    if request.method == "POST" and cl and cl.isdigit() and int(cl) > MAX_BYTES + 1024 * 1024:
        return JSONResponse({"detail": "File is larger than 25 MB."}, status_code=413)
    resp = await call_next(request)
    if request.url.path.startswith("/api/"):
        audit("request", method=request.method, path=request.url.path, status=resp.status_code,
              ms=round((time.perf_counter() - t0) * 1000))
    resp.headers["X-Request-ID"] = rid
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
    cfg: Any = None
    frames: list[pd.DataFrame] = []
    for m in (5, 6, 7, 8, 9, 10):
        s = make_sample(rng, 0, cfg=cfg, causes=DEMOS[name], month=m)
        cfg = s.cfg
        frames.append(s.frame)
    assert cfg is not None
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


def _finish(rep, *, filename=None, raw=None, demo=False) -> dict:
    d = rep.to_dict()
    d["provenance"] = provenance.build(d, filename=filename, raw=raw)
    d["is_demo"] = demo
    audit("report", report_id=d["provenance"]["report_id"], input_sha=(d["provenance"]["input"]["sha256"] or "")[:16],
          reliable=d["data_quality"].get("reliable"), mode=d.get("mode"))
    return d


def _lang(lang: str) -> str:
    return "ar" if str(lang).lower().startswith("ar") else "en"


def _run(df, terms, design_dt):
    if design_dt is not None and not math.isfinite(design_dt):
        raise HTTPException(422, "Design delta-T must be a finite number.")
    try:
        return diagnose_frame(df, terms, design_delta_t_c=design_dt)
    except DataError as e:
        raise HTTPException(422, str(e))
    except FileNotFoundError:
        raise HTTPException(503, "The informed model is not installed on this server.")


def _read_upload(file: UploadFile):
    """Read at most MAX_BYTES from the upload (never buffers more), then parse."""
    raw = file.file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 25 MB.")
    audit("upload", bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()[:16], filename=(file.filename or "")[:80])
    try:
        return read_table(raw, file.filename or ""), {"filename": file.filename or "", "raw": raw}
    except DataError as e:
        raise HTTPException(422, str(e)) from None


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


@app.get("/api/demo/{name}.csv", response_class=PlainTextResponse, dependencies=[Depends(_slot)])
def demo_csv(name: str):
    if name not in DEMOS:
        raise HTTPException(404, "Unknown demo.")
    return _demo(name)[0].to_csv(index=False)


@app.get("/api/demo/{name}", dependencies=[Depends(_slot)])
def demo(name: str, min_dt: float = 8.9, pct: float = 0.10, rate: float = 0.40,
         design_dt: float | None = None):
    if name not in DEMOS:
        raise HTTPException(404, f"Unknown demo. Choose from: {', '.join(DEMOS)}")
    df, true_design = _demo(name)
    rep = _run(df, _terms(min_dt, pct, rate), design_dt)
    d = _finish(rep, filename=f"simulated demo: {name}", demo=True)
    d["demo_true_design_dt"] = round(true_design, 1)
    d["truth_for_demo"] = list(DEMOS[name]) or ["none"]
    return JSONResponse(d)


@app.get("/api/demo/{name}/report", response_class=HTMLResponse, dependencies=[Depends(_slot)])
def demo_report(name: str, min_dt: float = 8.9, pct: float = 0.10, rate: float = 0.40,
                design_dt: float | None = None, lang: str = "en"):
    if name not in DEMOS:
        raise HTTPException(404, "Unknown demo.")
    df, _ = _demo(name)
    rep = _run(df, _terms(min_dt, pct, rate), design_dt)
    return render_report(_finish(rep, filename=f"simulated demo: {name}", demo=True),
                         f"Simulated building ({name.replace('_', ' ')})", _lang(lang))


@app.post("/api/report", response_class=HTMLResponse, dependencies=[Depends(_slot)])
def report(file: UploadFile = File(...), name: str = Form("Your building"), min_dt: float = Form(8.9),
                 pct: float = Form(0.10), rate: float = Form(0.40), design_dt: float | None = Form(None),
                 lang: str = Form("en")):
    terms = _terms(min_dt, pct, rate)
    df, info = _read_upload(file)
    rep = _run(df, terms, design_dt)
    return render_report(_finish(rep, filename=info["filename"], raw=info["raw"]), name[:80], _lang(lang))


@app.post("/api/diagnose", dependencies=[Depends(_slot)])
def diagnose(file: UploadFile = File(...), min_dt: float = Form(8.9),
                   pct: float = Form(0.10), rate: float = Form(0.40),
                   design_dt: float | None = Form(None)):
    terms = _terms(min_dt, pct, rate)
    df, info = _read_upload(file)
    return JSONResponse(_finish(_run(df, terms, design_dt), filename=info["filename"], raw=info["raw"]))


@functools.lru_cache(maxsize=2)
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


@app.get("/api/demo-portfolio.csv", response_class=PlainTextResponse, dependencies=[Depends(_slot)])
def demo_portfolio_csv():
    return _portfolio_frame().copy().to_csv(index=False)


@app.post("/api/portfolio", dependencies=[Depends(_slot)])
def portfolio(file: UploadFile = File(...), min_dt: float = Form(8.9), pct: float = Form(0.10),
                    rate: float = Form(0.40), design_dt: float | None = Form(None)):
    terms = _terms(min_dt, pct, rate)
    df, info = _read_upload(file)
    if design_dt is not None and not math.isfinite(design_dt):
        raise HTTPException(422, "Design delta-T must be a finite number.")
    try:
        rep = diagnose_portfolio(df, terms, design_dt)
    except DataError as e:
        raise HTTPException(422, str(e))
    d = rep.to_dict()
    d["provenance"] = provenance.build(d, filename=info["filename"], raw=info["raw"], rows=len(df), kind="portfolio")
    audit("portfolio", report_id=d["provenance"]["report_id"], buildings=d["n_buildings"], diagnosed=d["n_diagnosed"])
    return JSONResponse(d)


@app.get("/api/demo-portfolio", dependencies=[Depends(_slot)])
def demo_portfolio(min_dt: float = 8.9, pct: float = 0.10, rate: float = 0.40):
    rep = diagnose_portfolio(_portfolio_frame().copy(), _terms(min_dt, pct, rate))
    d = rep.to_dict()
    d["provenance"] = provenance.build(d, filename="simulated demo portfolio", kind="portfolio")
    d["is_demo"] = True
    return JSONResponse(d)


app.mount("/fonts", StaticFiles(directory=os.path.join(WEB_DIR, "fonts")), name="fonts")


@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))
