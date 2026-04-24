sync:
	uv sync --all-packages --all-groups

ruff:
	uv run ruff format --check
	uv run ruff check

toml-check:
	uv run taplo format --check .

lint: ruff toml-check

unittest:
	NUMBA_DISABLE_JIT=1 uv run pytest -v packages/*/tests/

coverage:
	NUMBA_DISABLE_JIT=1 uv run pytest \
		$(patsubst %,--cov %,$(wildcard packages/*/src/*)) \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov-report=html \
		packages/*/tests/

test-numba:
	uv run pytest -v packages/*/tests/

.PHONY: docs
docs:
	cd docs/ && $(MAKE) html SPHINXOPTS="-W --keep-going"

doctest:
	cd docs/ && $(MAKE) doctest

clean:
	rm -rf dist/
