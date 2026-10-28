# Contributing

## Setup

```bash
pip install -e ".[api,dev,xlsx]"
pytest
ruff check src tests scripts
python scripts/check_links.py
```

## Conventions

* One logical change per commit, with a message that says what changed and why.
* New experiments follow the preregistered pattern: write the predictions and failure conditions in `docs/research/`, commit them, then run, and score every prediction afterwards. Failed predictions stay in the record.
* Every number in a document comes from a script in `scripts/` and a file in `results/`.
* Simulator behaviour, the bundled model and published results change only with a stated reason and a CHANGELOG entry.
* Claims stay inside what was measured: results are from simulation unless a document says otherwise.

## Reporting problems

Open an issue with the command, the input shape (not the data itself if it is confidential) and the output. Security reports: see [docs/SECURITY.md](docs/SECURITY.md).
