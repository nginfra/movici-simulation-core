[bumpversion]
current_version = 2.3.1
allow_dirty = True

[bumpversion:file:VERSION]

[bumpversion:file:./movici_simulation_core/__init__.py]
search = __version__ = "{current_version}"
replace = __version__ = "{new_version}"
