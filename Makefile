.PHONY: install test data train evaluate baselines lbnl serve demo reproduce reproduce-full lock sbom
install:
	pip install -e ".[api,dev]"
test:
	pytest
data:
	python scripts/generate_data.py
train:
	python scripts/train.py
evaluate:
	python scripts/evaluate.py
baselines:
	python scripts/baselines.py
lbnl:
	python scripts/lbnl_check.py
serve:
	deltat-doctor serve
demo:
	deltat-doctor simulate --causes fouling,passing_valves --out demo_ets.csv && deltat-doctor diagnose demo_ets.csv
reproduce:
	python scripts/reproduce.py
reproduce-full:
	python scripts/reproduce.py --full
lock:
	python scripts/make_lock.py --constraints ci/constraints.txt --extras api,xlsx
sbom:
	cyclonedx-py requirements requirements.lock -o sbom.cdx.json
