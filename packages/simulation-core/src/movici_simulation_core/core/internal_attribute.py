"""Naming convention for internal attribute variants used during REMAP. See issue #127.

An *internal* variant of an attribute is a per-publisher version that the orchestrator routes
through a solver helper to produce the canonical value. By convention the wire name is
``<base>:<model_name>:i``; the trailing ``:i`` marks the attribute as not for general
consumption (e.g. wildcard subscribers skip it by default).
"""

from __future__ import annotations

INTERNAL_ATTRIBUTE_SUFFIX = ":i"
_ATTRIBUTE_VARIANT_SEPARATOR = ":"


def encode_internal_attribute(base_name: str, model_name: str) -> str:
    """Return the wire name a non-owning publisher of ``base_name`` must use."""
    return f"{base_name}{_ATTRIBUTE_VARIANT_SEPARATOR}{model_name}{INTERNAL_ATTRIBUTE_SUFFIX}"


def is_internal_attribute(name: str) -> bool:
    return name.endswith(INTERNAL_ATTRIBUTE_SUFFIX)
