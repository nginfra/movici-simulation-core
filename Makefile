MODULE_NAME = movici_simulation_core
PYPI_SERVER = https://pypi.movici.nl

unittest:
	pytest -v tests/

flake8:
	flake8

coverage:
	NUMBA_DISABLE_JIT=1 pytest --cov $(MODULE_NAME) --cov-report=term --cov-report=xml tests/

bandit:
	bandit --recursive $(MODULE_NAME) bin
	bandit -f json -o bandit-report.json --recursive $(MODULE_NAME) bin

safety:
	safety check --full-report

pylint:
	pylint $(MODULE_NAME) --exit-zero -r n | tee pylint.txt

mypy:
	mypy $(MODULE_NAME)

clean:
	rm -rf dist/

docker:
	docker build -t model-engine .

test-all: unittest flake8 coverage bandit safety pylint mypy
