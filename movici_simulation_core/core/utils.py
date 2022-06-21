from __future__ import annotations

import pkg_resources

from . import types


def configure_global_plugins(
    app: types.Extensible, key="movici.plugins", ignore_missing_imports=True
):
    for entry_point in pkg_resources.iter_entry_points(key):
        try:
            plugin: types.Plugin = entry_point.load()
            plugin.install(app)
        except (ImportError, pkg_resources.DistributionNotFound):
            if ignore_missing_imports:
                continue
            raise
