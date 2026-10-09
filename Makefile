.PHONY: install test data train evaluate lbnl serve demo
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
lbnl:
	python scripts/lbnl_check.py
serve:
	deltat-doctor serve
demo:
	deltat-doctor simulate --causes fouling,passing_valves --out demo_ets.csv && deltat-doctor diagnose demo_ets.csv
