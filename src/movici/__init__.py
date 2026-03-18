import importlib.metadata

print("This is a dummy package for development purposes only")  # noqa T201

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"  # Fallback for development mode
