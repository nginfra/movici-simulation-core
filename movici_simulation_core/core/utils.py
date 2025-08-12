from __future__ import annotations

from importlib.metadata import entry_points

from . import types


def configure_global_plugins(
    app: types.Extensible, key="movici.plugins", ignore_missing_imports=True
):
    try:
        eps = entry_points()
        # Handle different versions of importlib.metadata
        plugin_eps = []
        if hasattr(eps, "select"):
            # Python 3.10+ style
            plugin_eps = eps.select(group=key)
        elif hasattr(eps, "get"):
            # Alternative Python 3.10+ style
            plugin_eps = eps.get(key, [])
        else:
            # Python 3.9 style - eps is a dict
            try:
                plugin_eps = eps.get(key, [])
            except:
                # Fallback for other cases
                pass

        for entry_point in plugin_eps:
            try:
                plugin: types.Plugin = entry_point.load()
                plugin.install(app)
            except ImportError:
                if ignore_missing_imports:
                    continue
                raise
    except (KeyError, AttributeError):
        # No plugins registered, which is fine
        pass
