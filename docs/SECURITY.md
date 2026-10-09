# Security and data handling

* **Nothing is stored.** Uploads are read into memory, analysed and discarded. There is no database, no log of file
  contents and no user accounts.
* **No outbound calls.** The web app bundles its fonts and scripts and makes no external requests, so it can run
  on an isolated network.
* **Limits.** 25 MB per upload, 500 buildings per portfolio file, and input validation on all contract terms.
* **Headers.** `nosniff`, `X-Frame-Options: DENY`, `no-referrer`, `no-store`, and a Content-Security-Policy limited to
  the app's own origin (inline script and style are allowed because the UI is a single file).
* **Container.** The Docker image runs as a non-root user and has a health check.
* **Not included.** Authentication, TLS and rate limiting. Run it behind your own reverse proxy or API gateway
  (see [DEPLOYMENT.md](DEPLOYMENT.md)). Do not expose it to the public internet as it is.
* **Model files.** `joblib` files can run code when loaded. Only load model files you built or trust.
  Never point the app at a model file from an untrusted source.
* **Reporting a problem.** Open a GitHub issue without any customer data in it.
