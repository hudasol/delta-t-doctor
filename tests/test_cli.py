"""Command line interface: each subcommand runs end to end on a small simulated file."""
import json

import pytest

from deltat_doctor import __version__
from deltat_doctor.cli import main


@pytest.fixture(scope="module")
def demo_csv(tmp_path_factory):
    path = tmp_path_factory.mktemp("cli") / "demo.csv"
    main(["simulate", "--causes", "fouling", "--seed", "3", "--out", str(path)])
    return path


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_simulate_rejects_unknown_cause(tmp_path):
    with pytest.raises(SystemExit) as e:
        main(["simulate", "--causes", "nonsense", "--out", str(tmp_path / "x.csv")])
    assert "unknown cause" in str(e.value)


def test_diagnose_text_output(demo_csv, capsys):
    main(["diagnose", str(demo_csv), "--rate", "0.40"])
    out = capsys.readouterr().out
    assert "Flow-weighted delta-T" in out and "Likely causes" in out


def test_diagnose_json_and_html(demo_csv, tmp_path, capsys):
    html = tmp_path / "report.html"
    main(["diagnose", str(demo_csv), "--json", "--html", str(html), "--lang", "ar"])
    out = capsys.readouterr().out
    payload = json.loads(out[out.index("{"):])
    assert payload["findings"] and html.read_text(encoding="utf-8").startswith("<!doctype html")


def test_portfolio_writes_ranked_csv(demo_csv, tmp_path, capsys):
    import pandas as pd
    df = pd.read_csv(demo_csv)
    both = pd.concat([df.assign(building_id="Tower A"), df.assign(building_id="Tower B")], ignore_index=True)
    src, out = tmp_path / "fleet.csv", tmp_path / "ranked.csv"
    both.to_csv(src, index=False)
    main(["portfolio", str(src), "--out", str(out)])
    assert "2 of 2 buildings diagnosed" in capsys.readouterr().out
    assert len(pd.read_csv(out)) == 2
