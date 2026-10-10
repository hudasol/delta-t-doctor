"""Portfolio mode: one file with many buildings, ranked by money at stake."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import pandas as pd

from . import CAUSES, CAUSE_LABELS
from .diagnose import diagnose_frame
from .i18n import CAUSE_LABELS_AR, note, note_ar
from .io import DataError
from .penalty import ContractTerms

ID_ALIASES = ("building_id", "building", "site", "site_id", "ets_id", "meter_id", "account")
DESIGN_ALIASES = ("design_delta_t_c", "design_dt", "design_delta_t")
MAX_BUILDINGS = 500


@dataclass
class BuildingRow:
    building_id: str
    status: str                       # "ok" or "skipped"
    reason: str = ""
    n_days: float = 0.0
    delta_t_c: float | None = None
    below_minimum_c: float | None = None
    annual_surcharge_aed: float | None = None
    p_any_cause: float | None = None
    top_cause: str | None = None
    top_cause_label: str | None = None
    top_cause_probability: float | None = None
    top_cause_saving_aed: float | None = None
    mode: str = "blind"
    findings: list = field(default_factory=list)
    reliable: bool = True
    top_cause_saving_low_aed: float | None = None
    top_cause_saving_high_aed: float | None = None
    top_cause_label_ar: str = ""


@dataclass
class PortfolioReport:
    n_buildings: int
    n_diagnosed: int
    n_skipped: int
    total_surcharge_aed: float
    total_expected_saving_aed: float
    by_cause: list                   # cause, label, buildings_where_top, expected saving
    buildings: list                  # ranked BuildingRow dicts
    terms: dict
    notes: list
    notes_ar: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    is_demo: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _pick(df: pd.DataFrame, aliases) -> str | None:
    low = {c.lower().strip(): c for c in df.columns}
    for a in aliases:
        if a in low:
            return low[a]
    return None


def diagnose_portfolio(df: pd.DataFrame, terms: ContractTerms | None = None,
                       default_design_dt: float | None = None) -> PortfolioReport:
    """Diagnose every building in a long-format table.

    Needs a building id column (see ID_ALIASES) plus the usual meter columns. An optional design delta-T
    column (DESIGN_ALIASES) switches that building to the informed model.
    """
    terms = terms or ContractTerms()
    id_col = _pick(df, ID_ALIASES)
    if id_col is None:
        raise DataError("Portfolio files need a building column named one of: " + ", ".join(ID_ALIASES) + ".")
    design_col = _pick(df, DESIGN_ALIASES)
    n_null = int(df[id_col].isna().sum())
    if n_null:
        df = df.assign(**{id_col: df[id_col].fillna("(no building id)")})
    groups = list(df.groupby(id_col, sort=False))
    if len(groups) > MAX_BUILDINGS:
        raise DataError(f"At most {MAX_BUILDINGS} buildings per file; this one has {len(groups)}.")

    rows: list[BuildingRow] = []
    design_notes: list[str] = []
    for bid, g in groups:
        bid = str(bid)
        design = default_design_dt
        if design_col is not None:
            v = pd.to_numeric(g[design_col], errors="coerce").dropna()
            if len(v):
                design = float(v.median())
                if v.max() - v.min() > 0.5:
                    design_notes.append(note("design_differs", bid=bid, lo=f"{v.min():.1f}", hi=f"{v.max():.1f}"))
                else:
                    pass
            else:
                pass
        data = g.drop(columns=[c for c in (id_col, design_col) if c is not None])
        try:
            rep = diagnose_frame(data, terms, design_delta_t_c=design)
        except DataError as e:
            rows.append(BuildingRow(bid, "skipped", str(e)))
            continue
        top = rep.findings[0]
        rows.append(BuildingRow(
            building_id=bid, status="ok", n_days=rep.n_days, delta_t_c=rep.delta_t_c,
            below_minimum_c=max(rep.min_delta_t_c - rep.delta_t_c, 0.0),
            annual_surcharge_aed=rep.annual_surcharge_aed_estimate, p_any_cause=rep.p_any_cause,
            top_cause=top["cause"], top_cause_label=top["label"], top_cause_probability=top["probability"],
            top_cause_saving_aed=top["expected_saving_aed_per_year"], mode=rep.mode,
            reliable=bool(rep.data_quality.get("reliable", True)),
            top_cause_saving_low_aed=top.get("saving_low_aed_per_year"), top_cause_saving_high_aed=top.get("saving_high_aed_per_year"),
            top_cause_label_ar=CAUSE_LABELS_AR[top["cause"]],
            findings=[{k: f.get(k) for k in ("cause", "probability", "expected_dt_gain_c", "expected_saving_aed_per_year",
                                             "saving_low_aed_per_year", "saving_high_aed_per_year")} for f in rep.findings],
        ))

    ok = [r for r in rows if r.status == "ok"]
    ok.sort(key=lambda r: r.top_cause_saving_aed or 0.0, reverse=True)
    skipped = [r for r in rows if r.status != "ok"]

    by_cause = []
    for c in CAUSES:
        sav = sum(f["expected_saving_aed_per_year"] for r in ok for f in r.findings if f["cause"] == c)
        tops = sum(1 for r in ok if r.top_cause == c)
        by_cause.append({"cause": c, "label": CAUSE_LABELS[c], "label_ar": CAUSE_LABELS_AR[c], "buildings_where_top": tops,
                         "expected_saving_aed_per_year": float(sav)})
    by_cause.sort(key=lambda d: d["expected_saving_aed_per_year"], reverse=True)

    notes = list(design_notes)
    if n_null:
        notes.append(note("null_ids", n=n_null))
    if skipped:
        notes.append(note("skipped", n=len(skipped)))
    blind = sum(1 for r in ok if r.mode == "blind")
    if blind:
        notes.append(note("blind_count", n=blind))
    notes.append(note("savings_overlap"))

    return PortfolioReport(
        n_buildings=len(rows), n_diagnosed=len(ok), n_skipped=len(skipped),
        total_surcharge_aed=float(sum(r.annual_surcharge_aed or 0.0 for r in ok)),
        total_expected_saving_aed=float(sum(f["expected_saving_aed_per_year"] for r in ok for f in r.findings)),
        by_cause=by_cause, buildings=[asdict(r) for r in ok + skipped], terms=terms.to_dict(),
        notes=[str(n) for n in notes], notes_ar=[note_ar(n) for n in notes],
    )


def safe_cell(v):
    """Neutralise spreadsheet formulas: a cell starting with = + - @ tab or CR is prefixed with a quote."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def to_csv(rep: PortfolioReport) -> str:
    cols = ["building_id", "status", "reason", "n_days", "delta_t_c", "below_minimum_c",
            "annual_surcharge_aed", "p_any_cause", "top_cause", "top_cause_probability",
            "top_cause_saving_aed", "mode"]
    frame = pd.DataFrame(rep.buildings)[cols]
    for c in ("building_id", "reason", "top_cause"):
        frame[c] = frame[c].map(safe_cell)
    return frame.to_csv(index=False)
