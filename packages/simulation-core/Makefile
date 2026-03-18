MODULE_NAME = movici_simulation_core

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
	- mypy $(MODULE_NAME)

bump-version:
	bumpversion  --config-file .bumpversion.app $(level)
	@NEW_VERSION=$$(tail -1 VERSION);\
	echo New version: $$NEW_VERSION
