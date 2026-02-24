MODULE_NAME = movici_simulation_core

unittest:
	NUMBA_DISABLE_JIT=1 pytest -v tests/

coverage:
	NUMBA_DISABLE_JIT=1 pytest \
		--cov $(MODULE_NAME) \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov-report=html \
		tests/

test-numba:
	pytest -v tests/

ruff:
	ruff format --check
	ruff check

toml-check:
	taplo format --check .

mypy:
	- mypy $(MODULE_NAME)

lint: ruff toml-check mypy
	
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
