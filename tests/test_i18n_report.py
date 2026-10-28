"""Round 4: Arabic notes, provenance, owner report in EN/AR, UI file sanity."""
import pathlib
import re

import pytest
from fastapi.testclient import TestClient

from deltat_doctor import i18n, provenance
from deltat_doctor.api import app
from deltat_doctor.report import confidence, render_report

client = TestClient(app)


@pytest.fixture(scope="module")
def demo():
    return client.get("/api/demo/fouled_coils").json()


def test_note_keeps_key_and_renders_arabic():
    n = i18n.note("duplicates", n=3)
    assert isinstance(n, str) and "3 duplicate" in n
    ar = i18n.note_ar(n)
    assert "3" in ar and ar != str(n)
    assert i18n.note_ar("plain string") == "plain string"


def test_every_english_note_has_arabic_with_same_params():
    assert set(i18n.EN) == set(i18n.AR) - set()  # same keys
    for k in i18n.EN:
        en = set(re.findall(r"{(\w+)}", i18n.EN[k]))
        ar = {a[:-3] if a.endswith("_ar") else a for a in re.findall(r"{(\w+)}", i18n.AR[k])}
        assert en <= ar, k


def test_api_returns_provenance_and_arabic_fields(demo):
    p = demo["provenance"]
    assert p["report_id"].startswith("DTD-") and p["model"]["sha256"]
    assert demo["is_demo"] is True
    assert demo["disclaimer_ar"] and demo["notes_ar"]
    assert all("label_ar" in f and "checks_ar" in f for f in demo["findings"])


def test_provenance_hash_is_of_input_bytes(demo):
    d = dict(demo)
    pr = provenance.build(d, filename="x.csv", raw=b"abc", rows=3)
    import hashlib
    assert pr["input"]["sha256"] == hashlib.sha256(b"abc").hexdigest()
    assert pr["report_id"] == provenance.build(d, filename="x.csv", raw=b"abc", rows=3)["report_id"]


def test_report_english_and_arabic(demo):
    en = render_report(demo, "Tower Z", "en")
    ar = render_report(demo, "Tower Z", "ar")
    assert 'dir="ltr"' in en and 'dir="rtl"' in ar
    assert demo["provenance"]["report_id"] in en and demo["provenance"]["report_id"] in ar
    assert "simulat" in en.lower()          # demo band
    assert "Tower Z" in en and "Tower Z" in ar
    assert "<script" not in en.lower()


def test_report_escapes_name(demo):
    assert "<img" not in render_report(demo, "<img src=x onerror=1>", "en")


def test_unreliable_report_hides_ranking(demo):
    d = {**demo, "data_quality": {**demo["data_quality"], "reliable": False}}
    assert confidence(d) == "NA"
    html = render_report(d, "T", "en")
    assert "not reliable" in html.lower()


def test_report_endpoint_lang(demo):
    r = client.get("/api/demo/fouled_coils/report?lang=ar")
    assert r.status_code == 200 and 'dir="rtl"' in r.text


def test_ui_has_language_and_a11y_hooks():
    html = (pathlib.Path(__file__).parents[1] / "src/deltat_doctor/web/index.html").read_text(encoding="utf-8")
    for needle in ['class="skip"', 'aria-live="polite"', "dir=", "prefers-reduced-motion", "ar-AE", "label_ar", "checks_ar"]:
        assert needle in html
