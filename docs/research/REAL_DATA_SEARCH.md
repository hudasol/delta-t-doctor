# Real data search record

Purpose: find free, openly licensed, real hourly meter data with flow and supply and return temperature at substation or building
level, to see what the pipeline does when it meets real data. This is not a search for accuracy evidence: none of the datasets below has
labels for the four causes the tool diagnoses. Search date: 2026-10-16. A dataset is called "used" only if I opened it and read its licence.

All downloads go into `external/` (gitignored), one new folder per dataset, and are never executed. `scripts/fetch_real_data.py`
reproduces the download and writes `external/fetch_manifest.json` with the sha256 of every file. Raw data are not committed.

## Used

| Dataset | Licence (as read) | What it contains | How it was fetched | Integrity check |
|---|---|---|---|---|
| Schaffer, Tvedebrink, Marszal-Pomianowska (2022), "Three years of hourly data from 3021 smart heat meters installed in Danish residential buildings", Zenodo record 6563114 (version DOI 10.5281/zenodo.6563114, concept DOI 10.5281/zenodo.6304152), with the article Sci Data 9, 420 | CC BY 4.0 (Zenodo record metadata, `license: cc-by-4.0`) | District heating substations in residential buildings, hourly cumulative registers: heat energy (kWh), volume (m3), volume times inlet temperature and volume times return temperature (m3 x C). No outdoor temperature. | The archive is 3.3 GB (md5 e32a9216f2d3243e7cf9f6ca5ffad685 per Zenodo). At the roughly 100 KB/s available here a full download was not possible, so only 40 processed meter files (seeded random choice), the context file and the data description were read with HTTP range requests. | zipfile verifies each member's CRC32 on extraction; sha256 of every extracted file in `external/fetch_manifest.json` and `results/real_data_contact.json` |
| Cvetkovic, Zdravkovic, Ignjatovic (2024), "XAI4HEAT SCADA Dataset 2024", Mendeley Data, DOI 10.17632/2mwc6x6kwb.1 | CC BY 4.0 (Mendeley API, `data_licence.short_name`) | Five district heating substations in residential buildings in Nis, Serbia, hourly, five heating seasons: primary and secondary supply and return temperature, outdoor temperature, a reference temperature and an energy column (`delta_e`). **No flow column.** | Five files, 0.6 to 1.0 MB each, direct download | sha256 of all five files matches the value published by Mendeley (listed in `scripts/fetch_real_data.py`) |

## Evaluated and not used

| Candidate | Why not used |
|---|---|
| Raftery et al. (2024), "Data from hydronic heating systems in 216 commercial buildings", Dryad DOI 10.5061/dryad.t4b8gtj8n | Licence CC0 (Dryad API). It has supply and return temperature and flow for heating hot water loops, which would be a good second contact. Automated download returned 403, and the Dryad API file endpoint requires a bearer token (an account). Not attempted further. |
| Stadtwerke Flensburg network data 2014 to 2016 (Zenodo 2562658, CC BY-SA 4.0) and 2017 to 2019 (Zenodo 10508280, CC BY-NC-SA 4.0) | Network level only (plant feed temperature and total heat load). The 2017 to 2019 description says the return temperature is assumed to be 50 C, not measured. No flow, no substations. |
| Vanderbilt Alumni Hall, OpenEI / OEDI submission 4534 | A chilled water building would be the closest match, but the submission page returned "No data found" when opened. Licence not readable, so not used. |
| PNNL Systems Engineering Building, OpenEI | Reported to include chilled water supply and return and flow. Not opened within the time box; licence not checked. |
| Schaffer et al. (2024), smart heat and water meter data for Aalborg, Data in Brief | Access is restricted (contact the authors). |
| Chalmers district cooling study, 37 connected buildings (research.chalmers.se 521437) | A real district cooling ETS dataset, but I found no public data release. |
| Shandong district heating anomaly dataset (arXiv 2408.14499) | Stated as confidential. |
| Building Data Genome 2 and similar meter collections | Energy only, no flow or supply and return temperature. |
| LBNL FDD chiller plant (already used in `docs/research/EXTERNAL_CHECK.md`) | Simulated plant data, plant side, no building labels. Kept as the existing external check. |

## What this means

No open, real district cooling ETS dataset with flow and supply and return temperature was found. The two usable real datasets are
district heating, so the tool should refuse or abstain on them; that is what `docs/research/REAL_DATA_CONTACT.md` measures. Real district cooling
data remain something only a pilot partner can supply (`docs/PILOT.md`).
