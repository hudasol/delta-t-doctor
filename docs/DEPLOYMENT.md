# Deployment

## Docker

```bash
docker build -t delta-t-doctor .
docker run -p 8000:8000 delta-t-doctor           # http://localhost:8000
```

The CI workflow builds the image and smoke-tests it on every push. The test job failed on Python 3.10 from Round 4 through v1.1.1 (the
bundled model needs scikit-learn 1.9, which needs Python 3.11); fixed in v1.2.0, see CHANGELOG.md. Run the image read only:

```bash
docker run --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --cap-drop ALL --security-opt no-new-privileges -p 8000:8000 delta-t-doctor
```

## From source

```bash
pip install ".[api]"
deltat-doctor serve --host 0.0.0.0 --port 8000
```

## Production notes

* Put it behind a reverse proxy that adds TLS, authentication and rate limiting. The app has none. Also cap the request body there (nginx: `client_max_body_size 26m;`, Caddy: `request_body { max_size 26MB }`, Traefik: `buffering.maxRequestBodyBytes`). The app enforces the same limit itself, including for chunked uploads, but the proxy stops oversize bodies earlier.
* It is stateless, so run as many copies as you need. Each request takes well under a second to a few seconds for a year of hourly data, depending on the machine (table below).
* A portfolio of 500 buildings is the upper limit per request and may take minutes. Use `deltat-doctor portfolio` for
  larger batches.
* Memory: a few hundred MB per worker.
* To retrain on your own labelled data, see `scripts/train.py`. The model is a plain scikit-learn pipeline.

## Measured budget (2-core cloud VM, scripts/benchmark.py; measured in an earlier session, the output was not saved to results/)

| job | time |
|---|---|
| parse and diagnose 6 months hourly (0.4 MB) | about 0.1 s |
| 5 years hourly (4.4 MB) | about 0.5 s |
| 50-building portfolio (180,000 rows) | about 5 s |

Peak memory in that run was 263 MB. Size the container with at least 512 MB and set `DTD_MAX_CONCURRENT` to the number of CPU cores.
