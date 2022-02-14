MODULE_NAME = movici_simulation_core
PYPI_SERVER = https://pypi.movici.nl

unittest:
	NUMBA_DISABLE_JIT=1 pytest -v tests/

coverage:
	NUMBA_DISABLE_JIT=1 pytest --cov $(MODULE_NAME) --cov-report=term-missing --cov-report=xml  tests/

flake8:
	flake8

bandit:
	bandit --recursive $(MODULE_NAME) bin
	bandit -f json -o bandit-report.json --recursive $(MODULE_NAME) bin

safety:
	safety check -r requirements.txt --full-report

pylint:
	pylint $(MODULE_NAME) --exit-zero -r n | tee pylint.txt

mypy:
	- mypy $(MODULE_NAME)

clean:
	rm -rf dist/

docker:
	docker build -t model-engine .

benchmark:
	pytest --benchmark-only tests/

test-numba:
	pytest -v tests/

test-all: unittest flake8 coverage bandit safety pylint mypy

level=patch
export level

bump-version:
	bumpversion  --config-file .bumpversion.app $(level)
	@NEW_VERSION=$$(tail -1 VERSION);\
	echo New version: $$NEW_VERSION

