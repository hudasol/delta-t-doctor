# Security and data handling

* **Nothing is stored.** Uploads are read into memory, analysed and discarded. There is no database, no log of file
  contents and no user accounts.
* **No outbound calls.** The web app bundles its fonts and scripts and makes no external requests, so it can run
  on an isolated network.
* **Limits.** 25 MB per upload (read in a bounded way), 2 million rows, 200 columns, 150 MB unpacked for .xlsx (zip-bomb check), 500 buildings per portfolio file, a concurrency cap (`DTD_MAX_CONCURRENT`, default 4, 2 in the Docker image) that returns 503 when full, and finite-number validation on all contract terms. Old `.xls` files are refused.
* **Input quality gate.** Spikes, sensor codes (-999, 99.9 and similar), impossible temperatures, unreadable timestamps and frozen meters are removed or flagged, counted in `data_quality.input`, and make `reliable` false above small thresholds. A 1% flow-spike file moves the surcharge estimate by 0.1%, against a factor of 40,000 before this check.
* **Audit log.** Each API call writes one JSON line (request id, path, status, duration) and each upload one line (size, first 16 hex of its SHA-256, truncated filename). File contents are never logged. Responses carry `X-Request-ID`.
* **Output.** Portfolio CSVs prefix cells that start with `= + - @` so a building name cannot run as a spreadsheet formula.
* **Headers.** `nosniff`, `X-Frame-Options: DENY`, `no-referrer`, `no-store`, and a Content-Security-Policy limited to
  the app's own origin (inline script and style are allowed because the UI is a single file).
* **Container.** The image installs from the pinned `requirements-lock.txt`, runs as a numeric non-root user with no home directory and no login shell, and has a health check. It also runs read-only: `docker run --read-only --cap-drop ALL --security-opt no-new-privileges -p 8000:8000 delta-t-doctor`.
* **Not included.** Authentication, TLS and rate limiting. Run it behind your own reverse proxy or API gateway
  (see [DEPLOYMENT.md](DEPLOYMENT.md)). Do not expose it to the public internet as it is.
* **Model files.** `joblib` files can run code when loaded. A bundled model is loaded only if its bytes match the sha256 in `model_card.json` (missing entry means refuse) and the installed scikit-learn has the same minor version as at training. That is integrity, not authenticity: someone who can rewrite both files can still swap the model, so verify release artefacts out of band and never point the app at a model file from an untrusted source. A model path outside the package logs a warning and is not verified.
* **Known gaps.** `script-src` still allows `'unsafe-inline'` (single-file UI; planned to move to a nonce). GitHub Actions are pinned to tags, not commit SHAs. No SBOM or image scan is produced yet. No authentication or TLS.
* **Reporting a problem.** Open a GitHub issue without any customer data in it.
* **Upload limits.** A 25 MB read cap applies to every upload, and POST bodies whose Content-Length exceeds 26 MB are rejected before parsing. Starlette spools multipart bodies to disk before the handler runs, and chunked requests carry no Content-Length, so set a body-size limit on the reverse proxy as well. Heavy routes (parse, simulate, diagnose, demos) share a concurrency limit and return 503 when full.
