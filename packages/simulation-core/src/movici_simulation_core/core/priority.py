"""Publishing priority for resolving attribute ownership when multiple models publish the
same attribute. See GitHub issue #127.

The named values are convenient defaults; any non-negative integer is a valid priority on a
``RegistrationMessage``. The orchestrator grants ownership of an attribute to the unique
publisher at the highest priority; a tie at the highest priority is a configuration error.
"""

from __future__ import annotations

import enum


class Priority(enum.IntEnum):
    """Publishing priority for a model. Higher values take ownership when multiple models
    publish the same attribute. Values are conventions, not a closed set; a model developer
    may send an arbitrary integer on a ``RegistrationMessage`` when a use case warrants it.
    """

    REGULAR = 10
    SOLVER_HELPER = 20


def priority_label(value: int) -> str:
    """Return a human-readable label for a priority value. Falls back to ``UNKNOWN`` for
    values that are not in the named enum so error messages stay informative even when a
    model uses a non-standard priority (see issue #127, comment thread)."""
    try:
        return Priority(value).name
    except ValueError:
        return "UNKNOWN"
