MODULE_NAME = movici_urban_drainage_model

unittest:
	NUMBA_DISABLE_JIT=1 uv run pytest -v tests/

coverage:
	NUMBA_DISABLE_JIT=1 uv run coverage run \
		--source $(MODULE_NAME) \
		-m pytest tests/
	uv run coverage report -m
	uv run coverage html
	uv run coverage xml

test-numba:
	uv run pytest -v tests/

mypy:
	- mypy $(MODULE_NAME)
