import pkg_resources

from movici_simulation_core.core.plugins import Extensible, Plugin


def configure_global_plugins(app: Extensible, key="movici.plugins"):
    for entry_point in pkg_resources.iter_entry_points(key):
        plugin: Plugin = entry_point.load()
        plugin.install(app)
