def missing_dependency(message):
    def _inner(*args, **kwargs):
        raise RuntimeError(message)

    return _inner


try:
    from model_engine import DataFetcher
except ImportError:
    DataFetcher = missing_dependency("Install movici-simulation-core[models] to use DataFetcher")
