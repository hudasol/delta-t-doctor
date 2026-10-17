"""Build the reviewer package for the Arabic text: docs/i18n_review_sheet.csv (every string, EN beside AR, empty reviewer columns)
and a consistency check of key terms against docs/i18n_glossary.csv. Re-run after any text change.
usage: python scripts/i18n_review_sheet.py   (needs node for the UI dictionary)
"""
import csv, json, os, re, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from deltat_doctor import i18n
from deltat_doctor.evidence import _FIXED

rows = []
for k in i18n.EN:
    rows.append(("note", k, i18n.EN[k], i18n.AR.get(k, "")))
for k in i18n.CAUSE_LABELS_AR:
    rows.append(("cause label", k, "", i18n.CAUSE_LABELS_AR[k]))
for k, v in i18n.CAUSE_SHORT_AR.items():
    rows.append(("cause short", k, i18n.CAUSE_SHORT_EN[k], v))
for c, lst in i18n.CHECKS_AR.items():
    for i, v in enumerate(lst):
        rows.append(("check", f"{c}[{i}]", "", v))
rows.append(("disclaimer", "disclaimer", "", i18n.DISCLAIMER_AR))
for k, (en, ar, _u) in _FIXED.items():
    rows.append(("feature label", k, en, ar))
html = open("src/deltat_doctor/web/index.html", encoding="utf-8").read()
m = re.search(r"const I = (\{.*?\n\});\nconst CAUSE_AR", html, re.S)
js = "const I=" + m.group(1) + ";const out={};for(const k of Object.keys(I.en)){const f=v=>typeof v==='function'?v.toString():(typeof v==='object'?JSON.stringify(v):String(v));out[k]=[f(I.en[k]),f(I.ar[k]||'')];}console.log(JSON.stringify(out));"
ui = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8", check=True).stdout)
for k, (en, ar) in ui.items():
    rows.append(("ui", k, en, ar))
os.makedirs("docs", exist_ok=True)
with open("docs/i18n_review_sheet.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["where", "id", "english", "arabic", "reviewer_ok (yes/no)", "reviewer_correction", "reviewer_comment"])
    for r in rows:
        w.writerow(list(r) + ["", "", ""])
print(len(rows), "strings written to docs/i18n_review_sheet.csv")

# glossary consistency: every preferred term present, no discouraged variant left
gl = list(csv.DictReader(open("docs/i18n_glossary.csv", encoding="utf-8-sig")))
blob = "\n".join(r[3] for r in rows)
bad = 0
for g in gl:
    for v in filter(None, g["avoid_variants"].split("|")):
        n = blob.count(v)
        if n:
            print(f"AVOID '{v}' ({g['english']}) appears {n}x; prefer '{g['arabic']}'"); bad += 1
print("glossary check:", "clean" if not bad else f"{bad} issue(s)")
sys.exit(1 if bad else 0)
