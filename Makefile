ruff:
	uv run ruff format --check
	uv run ruff check

toml-check:
	uv run taplo format --check .

lint: ruff toml-check


.PHONY: docs
docs:
	cd docs/ && $(MAKE) html SPHINXOPTS="-W --keep-going"

doctest:
	cd docs/ && $(MAKE) doctest

clean:
	rm -rf dist/
