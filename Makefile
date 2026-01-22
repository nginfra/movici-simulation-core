MODULE_NAME = movici_simulation_core

unittest:
	NUMBA_DISABLE_JIT=1 pytest -v tests/

coverage:
	NUMBA_DISABLE_JIT=1 pytest --cov $(MODULE_NAME) --cov-report=term-missing --cov-report=xml  tests/

test-numba:
	pytest -v tests/

ruff:
	ruff format --check
	ruff check

toml-check:
	taplo format --check .

safety:
	@echo "Safety check: Skipping safety scan (requires authentication in CI)"
	@echo "To run locally: pip freeze | safety scan --stdin --output screen"

mypy:
	- mypy $(MODULE_NAME)

lint: ruff toml-check safety mypy
	
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

clean:
	rm -rf dist/
