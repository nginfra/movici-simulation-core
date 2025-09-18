MODULE_NAME = movici_simulation_core

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
	@echo "Safety check: Skipping safety scan (requires authentication in CI)"
	@echo "To run locally: pip freeze | safety scan --stdin --output screen"

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

black-check:
	black --check .

isort:
	isort .
	
isort-check:
	isort -c .

lint: flake8 black-check isort-check bandit safety mypy
	
test-all: coverage lint

level=patch
export level

bump-version:
	bumpversion  --config-file .bumpversion.app $(level)
	@NEW_VERSION=$$(tail -1 VERSION);\
	echo New version: $$NEW_VERSION

.PHONY: docs
docs:
	cd docs/ && $(MAKE) html SPHINXOPTS="-W --keep-going"

doctest:
	cd docs/ && $(MAKE) doctest