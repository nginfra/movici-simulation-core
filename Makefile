
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

comma:= ,
coverage:
	NUMBA_DISABLE_JIT=1 uv run coverage run \
	  --source $(subst $(eval ) ,$(comma),$(wildcard packages/*/src/*)) \
		-m pytest packages/*/tests/
	uv run coverage report -m
	uv run coverage html
	uv run coverage xml

test-numba:
	uv run pytest -v packages/*/tests/

.PHONY: docs
docs:
	cd docs/ && $(MAKE) html SPHINXOPTS="-W --keep-going"

doctest:
	cd docs/ && $(MAKE) doctest

clean:
	rm -rf dist/
