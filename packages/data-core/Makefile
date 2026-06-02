MODULE_NAME = movici_data_core

unittest:
	NUMBA_DISABLE_JIT=1 uv run pytest -v tests/

coverage:
	NUMBA_DISABLE_JIT=1 uv run pytest \
		--cov $(MODULE_NAME) \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov-report=html \
		tests/

test-numba:
	uv run pytest -v tests/

mypy:
	- mypy src/$(MODULE_NAME)
