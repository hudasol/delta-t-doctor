# Brief for the Arabic language review

**Who:** a native Arabic speaking engineer who works with district cooling or building HVAC in the UAE.
**Why:** every Arabic string in the product is a machine draft. It must not be shown to customers until it has been reviewed.

## What to check

The file is `docs/i18n_review_sheet.csv` (it opens in Excel; save it back as CSV, UTF-8). Each row is one string as the product shows it:
`where` (note, cause label, check, disclaimer, user interface), `id`, `english`, `arabic`, and three empty columns for you.

For each row, check:

1. **Meaning.** Does the Arabic say what the English says, with nothing added or lost? Numbers in braces, such as `{n}` or `{p}`, are filled in
   by the software and must stay exactly as they are.
2. **Terminology.** Is the technical term the one UAE operators and consultants use? The agreed terms are in `docs/i18n_glossary.csv`; where
   a term there is marked "confirm with an operator engineer", your view decides it.
3. **Register.** Formal and plain, suitable for a building owner's report. No colloquial forms.
4. **Safety of meaning.** Warnings and refusals (for example "the cause ranking is withheld") must be at least as strong in Arabic as in English.

## How to mark each row

| Column | What to write |
|---|---|
| `reviewer_ok (yes/no)` | `yes` if the Arabic can be used as it is; `no` otherwise |
| `reviewer_correction` | when `no`: the corrected Arabic, complete (not a description of the change) |
| `reviewer_comment` | optional: why, or a question; also use it to flag a glossary term |

Also review `docs/i18n_glossary.csv`: for each term, confirm the Arabic or give the term you would use.

## Time

About 180 strings, most of them one or two sentences. Allow roughly one minute per string plus time for the glossary, so about **3 to 5 hours**,
best in two sittings. This is an estimate, not a measurement.

## How corrections are merged

1. The returned CSV is kept unchanged in `docs/i18n_review_returned/` with the reviewer's name and date in the commit message (with their
   consent).
2. Each `no` row is applied to `src/deltat_doctor/i18n.py` or the user interface dictionary in `src/deltat_doctor/web/index.html`, one commit per
   group of related strings, quoting the row ids.
3. `python scripts/i18n_review_sheet.py` regenerates the sheet; the test `tests/test_round4_i18n_report.py` checks that every English note still
   has an Arabic version with the same placeholders.
4. `docs/I18N.md` changes from "machine draft" to "reviewed by a native speaking engineer on (date)" only when every row is `yes` or corrected.
