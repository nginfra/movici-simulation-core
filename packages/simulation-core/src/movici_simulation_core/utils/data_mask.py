import copy
import typing as t

from movici_simulation_core.core.internal_attribute import is_internal_attribute


def validate_mask(data_mask: t.Optional[dict]):
    """determines whether the dataset filter has the correct shape, it must be lists inside
    dictionaries inside a dictionary. eg.:
    `{"some_dataset": {"some_entity_group": ["attribute1", "attribute2"]}}`

    Also, at every level, the filter must either be filled or be none. It cannot be an empty
    container, eg:

    * ``{"some_dataset": {}}``
    * ``{"some_dataset": {"some_entity_group": ["attribute1"], "empty_group": []}}``

    """
    if data_mask == {}:
        return True

    shape = (dict, dict, list)

    def validator_helper(df: t.Union[None, dict, list], depth=0):
        if df is None:
            return True

        # noinspection PyTypeHints
        if not len(df) or not isinstance(df, shape[depth]):
            return False
        if isinstance(df, dict):
            return all(validator_helper(df[key], depth + 1) for key in df.keys())
        return True

    return validator_helper(data_mask)


# Depth at which the dict keys are attribute names: dataset -> entity_group -> attribute.
_ATTRIBUTE_LEVEL = 2


def filter_data(data: dict, mask: t.Optional[dict]):
    """Return a copy of ``data`` restricted to the entries selected by ``mask``.

    ``mask`` is the same nested ``{dataset: {entity_group: [attr, ...] | None}}`` shape used
    everywhere else; ``None`` at any level means "everything below this point". Per issue
    #127, an attribute-level wildcard (the leaf list is ``None``) additionally drops
    attributes whose name ends in the internal-variant suffix (``:i``); explicit
    subscriptions return them.
    """

    def filter_helper(data_, mask_, depth=0):
        if mask_ is None:
            return _wildcard(data_, depth)

        if isinstance(mask_, list):
            ensure_id(mask_)
            mask_ = {attr: None for attr in mask_}

        if isinstance(mask_, dict):
            return {
                key: filter_helper(data_[key], mask_[key], depth + 1)
                for key in data_.keys() & mask_.keys()
            }

    def _wildcard(data_, depth):
        if not isinstance(data_, dict):
            return data_
        if depth >= _ATTRIBUTE_LEVEL:
            return {k: v for k, v in data_.items() if not is_internal_attribute(k)}
        return {k: _wildcard(v, depth + 1) for k, v in data_.items()}

    return filter_helper(data, mask)


def ensure_id(mask: t.List[str]):
    if "id" not in mask:
        mask.append("id")


def apply_remap_to_pub_mask(
    pub_mask: t.Optional[dict],
    remap_pub: t.Optional[t.Mapping[str, t.Mapping[str, t.Mapping[str, str]]]],
) -> t.Optional[dict]:
    """Return the new pub mask after applying a REMAP pub section
    (``{dataset: {entity_group: {original: variant}}}``). Each entry replaces ``original``
    with ``variant`` in the corresponding ``[dataset][entity_group]`` attribute list. The
    orchestrator uses this to keep its in-memory view of each model's publish mask in sync
    after sending a REMAP — so ``determine_interdependency`` sees the post-REMAP graph.
    See issue #127.

    A wildcard ``pub_mask`` (``None``) is preserved unchanged — REMAPs cannot reach a model
    whose pub mask is fully open, since the planner only operates on explicit publishers.
    Malformed entries (a non-list, non-None value where an attribute list is expected) raise
    ``ValueError`` rather than silently corrupting the mask.
    """
    if not remap_pub:
        return pub_mask
    if pub_mask is None:
        return None
    new_mask: dict = copy.deepcopy(pub_mask) if isinstance(pub_mask, dict) else {}
    for ds, entity_groups in remap_pub.items():
        ds_section = new_mask.setdefault(ds, {})
        for eg, mapping in entity_groups.items():
            current = _coerce_attribute_list(ds_section.get(eg), ds, eg)
            originals_to_drop = {
                original for original, variant in mapping.items() if variant != original
            }
            new_attrs = [a for a in current if a not in originals_to_drop]
            for variant in mapping.values():
                if variant not in new_attrs:
                    new_attrs.append(variant)
            ds_section[eg] = new_attrs
    return new_mask


def apply_remap_to_sub_mask(
    sub_mask: t.Optional[dict],
    remap_sub: t.Optional[t.Mapping[str, t.Mapping[str, t.Mapping[str, str]]]],
) -> t.Optional[dict]:
    """Return the new sub mask after applying a REMAP sub section
    (``{dataset: {entity_group: {variant: original}}}``). Each entry adds ``variant`` and
    drops ``original``; back-propagation entries (``variant == original``) keep the name.
    Used by both the orchestrator and the connector. See issue #127.

    A wildcard ``sub_mask`` (``None``) is preserved unchanged — the connector keeps its
    "subscribe to everything" reach, and the inbound rename middleware will translate the
    variant keys it cares about transparently. Without this short-circuit a REMAP would
    silently narrow a wildcard subscription to only the named variants.
    """
    if not remap_sub:
        return sub_mask
    if sub_mask is None:
        return None
    new_mask: dict = copy.deepcopy(sub_mask) if isinstance(sub_mask, dict) else {}
    for ds, entity_groups in remap_sub.items():
        ds_section = new_mask.setdefault(ds, {})
        for eg, mapping in entity_groups.items():
            current = _coerce_attribute_list(ds_section.get(eg), ds, eg)
            originals_to_drop = {
                original for variant, original in mapping.items() if variant != original
            }
            new_attrs = [a for a in current if a not in originals_to_drop]
            for variant in mapping.keys():
                if variant not in new_attrs:
                    new_attrs.append(variant)
            ds_section[eg] = new_attrs
    return new_mask


def _coerce_attribute_list(existing, dataset: str, entity_group: str) -> t.List[str]:
    """Return ``existing`` as a list, or an empty list if it is ``None``. Anything else is
    a malformed mask entry and raises ``ValueError`` — silently dropping data here would
    let mistakes in pub/sub mask construction propagate as confusing routing errors much
    later."""
    if existing is None:
        return []
    if isinstance(existing, list):
        return list(existing)
    raise ValueError(
        f"Malformed mask at '{dataset}/{entity_group}': expected list or None, got "
        f"{type(existing).__name__}"
    )


def masks_overlap(pub: t.Optional[dict], sub: t.Optional[dict]):
    """calculates whether there is overlap between the pub and sub filters of two models. This
    function assumes that the two filters have been validated using `validate_filter`
    """
    if pub == {} or sub == {}:
        return False

    def helper(pub: t.Union[None, list, dict], sub: t.Union[None, list, dict]):
        if pub is None or sub is None:
            return True
        if isinstance(pub, list):
            return set(pub) & set(sub)
        if matches := (pub.keys() & sub.keys()):
            for key in matches:
                if helper(pub[key], sub[key]):
                    return True
        return False

    return helper(pub, sub)
