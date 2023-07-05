from __future__ import annotations

from importlib.metadata import entry_points

from . import types


def configure_global_plugins(
    app: types.Extensible, key="movici.plugins", ignore_missing_imports=True
):
    for entry_point in entry_points()[key]:
        try:
            plugin: types.Plugin = entry_point.load()
            plugin.install(app)
        except ImportError:
            if ignore_missing_imports:
                continue
            raise
