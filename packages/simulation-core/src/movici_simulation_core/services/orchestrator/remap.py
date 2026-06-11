"""Pure functions for computing the orchestrator's REMAP plan from a set of registered
models. See issue #127.

The orchestrator collects ``RegistrationMessage`` payloads from every model (pub/sub mask +
priority), then asks :func:`compute_remap_plan` to:

* identify each (dataset, entity_group, attribute) that is published by more than one model
  and pick the unique highest-priority publisher as the canonical owner; raise
  :class:`RemapConflictError` if more than one model is tied at the highest priority;
* tell every non-owner publisher to publish under an internal variant name
  (``<base>:<model>:i``);
* tell every model at priority level *N+1* to subscribe to the internal variants produced
  at priority level *N* — so an attribute chain ``10 -> 20 -> 30`` routes each level to
  the level immediately above without short-circuiting intermediate models.

The output is a dict of ``RemapMessage`` payloads keyed by model name; only models whose
mask changes appear. The orchestrator then sends each payload as a ``REMAP`` command and
also updates its in-memory pub/sub views (using :func:`apply_remap_to_pub_mask` and
:func:`apply_remap_to_sub_mask`) before computing the dependency matrix.
"""

from __future__ import annotations

import dataclasses
import typing as t
from collections import defaultdict

from movici_simulation_core.core.internal_attribute import encode_internal_attribute
from movici_simulation_core.core.priority import priority_label
from movici_simulation_core.messages import RemapMessage


@dataclasses.dataclass(frozen=True)
class ModelRegistration:
    """A read-only snapshot of one model's registration used by the planner."""

    name: str
    pub: t.Optional[dict]
    sub: t.Optional[dict]
    priority: int


@dataclasses.dataclass(frozen=True)
class AttributeRef:
    dataset: str
    entity_group: str
    name: str


class RemapConflictError(RuntimeError):
    """Raised when more than one model publishes the same attribute at the highest priority
    among that attribute's publishers — i.e. there is no unique owner."""

    def __init__(self, attribute: AttributeRef, models: t.Sequence[str], priority: int):
        self.attribute = attribute
        self.models = tuple(models)
        self.priority = priority
        label = priority_label(priority)
        verb = "both" if len(self.models) == 2 else "all"
        super().__init__(
            f"Conflict: models {self._format_models(models)} {verb} publish "
            f"'{attribute.dataset}/{attribute.entity_group}/{attribute.name}' at "
            f"priority {priority} ({label}). Resolve by configuring a solver helper "
            "(e.g. 'combiner') for this attribute at a higher priority."
        )

    @staticmethod
    def _format_models(models: t.Sequence[str]) -> str:
        return ", ".join(f"'{m}'" for m in models)


def compute_remap_plan(registrations: t.Iterable[ModelRegistration]) -> t.Dict[str, RemapMessage]:
    """Return the ``REMAP`` payload for every model whose pub/sub mask needs to change.

    Models that need no remap are not present in the returned mapping. Raises
    :class:`RemapConflictError` if any attribute has more than one publisher tied for the
    highest priority.
    """
    registrations = list(registrations)
    by_name = {r.name: r for r in registrations}

    publishers = _publishers_per_attribute(registrations)

    pub_remaps: t.Dict[str, t.Dict[t.Tuple[str, str], t.Dict[str, str]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    sub_remaps: t.Dict[str, t.Dict[t.Tuple[str, str], t.Dict[str, str]]] = defaultdict(
        lambda: defaultdict(dict)
    )

    for attribute, by_priority in publishers.items():
        _plan_for_attribute(attribute, by_priority, pub_remaps, sub_remaps)

    plan: t.Dict[str, RemapMessage] = {}
    for name in sorted(set(pub_remaps) | set(sub_remaps)):
        pub_section = _denormalise(pub_remaps.get(name, {})) or None
        sub_section = _denormalise(sub_remaps.get(name, {})) or None
        # Back-propagation: a higher-priority subscriber that already wanted the canonical
        # value of an attribute being injected into its sub mask must keep that canonical
        # subscription. Lower-priority publishers do not receive a sub remap at all (their
        # connector keeps the original sub mask), so back-propagation only ever augments an
        # existing sub_section.
        sub_section = _augment_back_propagation(
            sub_section,
            by_name[name].sub if name in by_name else None,
            _sub_affected_attributes(name, sub_remaps),
        )
        plan[name] = RemapMessage(pub=pub_section, sub=sub_section)

    return plan


def _publishers_per_attribute(
    registrations: t.Iterable[ModelRegistration],
) -> t.Dict[AttributeRef, t.Dict[int, t.List[str]]]:
    """Group publishers by attribute and priority level."""
    publishers: t.Dict[AttributeRef, t.Dict[int, t.List[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for reg in registrations:
        for ds, eg, attr in _iter_attributes(reg.pub):
            publishers[AttributeRef(ds, eg, attr)][reg.priority].append(reg.name)
    return publishers


def _plan_for_attribute(
    attribute: AttributeRef,
    by_priority: t.Mapping[int, t.Sequence[str]],
    pub_remaps: t.MutableMapping[str, t.MutableMapping[t.Tuple[str, str], t.Dict[str, str]]],
    sub_remaps: t.MutableMapping[str, t.MutableMapping[t.Tuple[str, str], t.Dict[str, str]]],
) -> None:
    """Resolve ownership for a single attribute and append the implied remaps in place.

    Raises :class:`RemapConflictError` if more than one model is tied at the highest priority.
    """
    priorities = sorted(by_priority.keys())
    top = priorities[-1]
    top_publishers = list(by_priority[top])
    if len(top_publishers) > 1:
        raise RemapConflictError(attribute, sorted(top_publishers), top)

    if len(priorities) == 1:
        # A single priority level with a single publisher — nothing to do. (The conflict
        # check above already rejected multiple publishers at this level.)
        return

    key = _key(attribute.dataset, attribute.entity_group)

    # Non-owner publishers — every model at a priority below the top — publish a uniquely
    # named internal variant of the attribute.
    for priority in priorities[:-1]:
        for model in by_priority[priority]:
            internal_name = encode_internal_attribute(attribute.name, model)
            pub_remaps[model][key][attribute.name] = internal_name

    # Each priority level subscribes to the internal variants of the level immediately
    # below — so a chain 10 -> 20 -> 30 routes each link without short-circuiting.
    for lower, higher in zip(priorities[:-1], priorities[1:]):
        for high_model in by_priority[higher]:
            for low_model in by_priority[lower]:
                internal_name = encode_internal_attribute(attribute.name, low_model)
                sub_remaps[high_model][key][internal_name] = attribute.name


def _iter_attributes(mask: t.Optional[dict]) -> t.Iterable[t.Tuple[str, str, str]]:
    """Yield (dataset, entity_group, attribute) for every leaf attribute in a pub/sub mask.

    A ``None`` or empty mask yields nothing. Wildcards (``None`` at a sub-level) are not
    publishable, so they are skipped — only explicit leaf attributes participate in
    ownership resolution.
    """
    if not mask:
        return
    for ds, entity_groups in mask.items():
        if not entity_groups:
            continue
        for eg, attrs in entity_groups.items():
            if not attrs:
                continue
            for attr in attrs:
                yield ds, eg, attr


def _key(dataset: str, entity_group: str) -> t.Tuple[str, str]:
    return (dataset, entity_group)


def _denormalise(
    nested: t.Mapping[t.Tuple[str, str], t.Mapping[str, str]],
) -> t.Optional[t.Dict[str, t.Dict[str, t.Dict[str, str]]]]:
    """Convert ``{(ds, eg): {a: b, ...}, ...}`` to the wire shape
    ``{ds: {eg: {a: b, ...}, ...}, ...}``. Returns ``None`` when there is nothing."""
    out: t.Dict[str, t.Dict[str, t.Dict[str, str]]] = {}
    for (ds, eg), mapping in nested.items():
        if not mapping:
            continue
        out.setdefault(ds, {}).setdefault(eg, {}).update(mapping)
    return out or None


def _sub_affected_attributes(
    name: str,
    sub_remaps: t.Mapping[str, t.Mapping[t.Tuple[str, str], t.Mapping[str, str]]],
) -> t.Set[t.Tuple[str, str, str]]:
    """Set of ``(dataset, entity_group, original_attr)`` for which this model already has a
    sub remap entry. Used by :func:`_augment_back_propagation` to decide whether the model
    needs an explicit canonical-preservation entry."""
    return {
        (ds, eg, original)
        for (ds, eg), mapping in sub_remaps.get(name, {}).items()
        for original in mapping.values()
    }


def _augment_back_propagation(
    current_sub: t.Optional[dict],
    original_sub_mask: t.Optional[dict],
    affected: t.Set[t.Tuple[str, str, str]],
) -> t.Optional[dict]:
    """If the model explicitly subscribed to the canonical name of an attribute it is being
    remapped away from, preserve that subscription in the sub remap so it still receives the
    canonical value. See the proposal's "Backpropagating results" section."""
    if not original_sub_mask:
        return current_sub
    augmented: t.Dict[str, t.Dict[str, t.Dict[str, str]]] = dict(current_sub or {})
    for ds, eg, attr in affected:
        original_attrs = (original_sub_mask.get(ds) or {}).get(eg) or []
        if attr in original_attrs:
            augmented.setdefault(ds, {}).setdefault(eg, {})[attr] = attr
    return augmented or None
