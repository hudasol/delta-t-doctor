# Deployment

## Docker

```bash
docker build -t delta-t-doctor .
docker run -p 8000:8000 delta-t-doctor           # http://localhost:8000
```

The Dockerfile has not been built on the machine where I wrote it (no Docker daemon there). The CI workflow builds it
and runs a smoke test on every push, which is the first real check.

## From source

```bash
pip install ".[api]"
deltat-doctor serve --host 0.0.0.0 --port 8000
```

## Production notes

* Put it behind a reverse proxy that adds TLS, authentication and rate limiting. The app has none.
* It is stateless, so run as many copies as you need. Each request takes a few seconds for a year of hourly data.
* A portfolio of 500 buildings is the upper limit per request and may take minutes. Use `deltat-doctor portfolio` for
  larger batches.
* Memory: a few hundred MB per worker.
* To retrain on your own labelled data, see `scripts/train.py`. The model is a plain scikit-learn pipeline.
