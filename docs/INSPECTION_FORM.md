# Blind inspection form

One form per building. Print it, fill it in on site, sign it, and only then look at anything the tool produced. The result is one row of
the pilot manifest (`examples/real_manifest_template.csv`) that `scripts/evaluate_real.py` and `deltat-doctor calibrate` read.

## Instructions for the inspector (read before the visit)

1. **Do not look at the tool's output before this form is signed.** That includes the ranked causes, the report, the portfolio table and
   any summary someone else has seen. If you have seen it, write "not blind" in section 5 and the building is scored separately.
2. Inspect what you would inspect anyway. Record each of the four causes as **present**, **ruled out** or **not checked**. "Ruled out" means
   you looked for it and it is not there; "not checked" means you did not look. The difference matters: only ruled out causes count as
   negatives in the scoring.
3. A cause is **present** when, in your judgement, fixing it would recover a noticeable part of the building's delta T (the tool's own
   threshold is 0.2 C, which you are not expected to measure).
4. If the dominant cause is something else (controls, sensors, set points, pumps, plant side), tick **other** and describe it.
5. Write the evidence you used for every **present** and **ruled out** mark. Photos are optional; if you take them, record their file names.
6. Sign and date the form before leaving the site.

## Form

**1. Building**

| Field | Entry |
|---|---|
| Building ID (as in the meter export) | |
| Building name or address | |
| Building type (office, hotel, residential, mall, school, clinic, other) | |
| Meter export file name and period covered | |

**2. Visit**

| Field | Entry |
|---|---|
| Inspection date | |
| Inspector name | |
| Organisation | |
| Time on site (arrival, departure) | |
| Systems accessible (AHUs inspected of total, ETS, BMS access yes/no) | |

**3. Causes**

| Cause | Present | Ruled out | Not checked | Evidence (what was looked at, readings, observations) |
|---|---|---|---|---|
| Fouling (coils, strainers, plate exchanger) | | | | |
| Passing valves (water through idle or closed coils) | | | | |
| Constant flow (3-way valves, actuators stuck open or in manual) | | | | |
| Overflow (excess differential pressure, oversized or hunting valves) | | | | |
| Other (describe) | | | | |
| None of the above found | | | | |

**4. Measurements taken (optional)**

| Measurement | Value | Where |
|---|---|---|
| Loop differential pressure and set point | | |
| Pump speed | | |
| Coil delta T on sampled AHUs | | |
| Valve positions on idle AHUs | | |

**5. Declaration**

| Field | Entry |
|---|---|
| I had not seen the tool's output for this building before signing (yes / not blind) | |
| Photos taken (file names) | |
| Signature | |
| Date and time of signature | |

## Turning the form into a manifest row

* `causes`: the present causes separated by semicolons, using `fouling`, `passing_valves`, `constant_flow`, `overflow`, `other`; `none` if
  nothing was found.
* `complete`: `yes` only if every one of the four causes is marked present or ruled out (none "not checked"). Calibration uses only complete
  rows; scoring of false alarms and confidently wrong answers also uses only complete rows.
* Keep the signed forms; the manifest should record where they are filed.
