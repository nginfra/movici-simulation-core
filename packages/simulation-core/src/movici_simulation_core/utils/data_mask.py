import functools
import typing as t

from movici_simulation_core.core.internal_attribute import is_internal_attribute
from movici_simulation_core.messages import RemapMessage
from movici_simulation_core.types import DataMask


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


def masks_overlap(pub: t.Optional[dict], sub: t.Optional[dict]):
    """calculates whether there is overlap between the pub and sub filters of two models. This
    function assumes that the two filters have been validated using `validate_mask`
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


def apply_remap_to_data_mask(data_mask: DataMask, remap: RemapMessage) -> DataMask:
    r"""Return the new datamask mask after applying a RemapMessage. For a 'pub' datamask the remap
    has the shape ``{dataset: {entity_group: {original: variant}}}``).For a 'sub' datamask the
    remap has the shape ``{dataset: {entity_group: {variant: original}}}``). Each entry replaces
    ``original`` with one or more ``variant``\s in the corresponding ``[dataset][entity_group]``
    attribute list. For pub data_masks there is a one-to-one mapping between orignal and variants
    while for sub data_masks an ``original`` may be replaced by multiple ``variant``\s

    A wildcard pub or sub datamask (``None``) is preserved
    """

    return {
        "pub": t.cast(dict | None, apply_remap_to_pub_mask(data_mask["pub"], remap.pub)),
        "sub": t.cast(dict | None, apply_remap_to_sub_mask(data_mask["sub"], remap.sub)),
    }


def _apply_remap(
    data_mask: dict | None,
    remap: dict[str, dict[str, dict[str, str]]] | None,
    kind: t.Literal["pub", "sub"],
) -> dict | None:
    """Return the new pub or sub mask after applying its associated REMAP section. PUB masks
    are only remapped for existing attributes. No additional attributes are added to the data mask.

    For sub masks, every attribute that exists in the remap is added to the data mask, even if the
    original attribute was not already present in the data mask.

    Wildcard masks (``None``) are preserved at every level in the data mask so that the implicit
    publications/subscription are not quietly dropped.

    Malformed entries (a non-list, non-None value where an attribute list is expected) raise
    ``ValueError`` rather than silently corrupting the mask.
    """
    is_sub = kind == "sub"

    if not remap or data_mask is None:
        return data_mask
    new_mask = {}
    ds_keys = data_mask.keys() | remap.keys() if is_sub else data_mask.keys()
    for ds in ds_keys:
        ds_mask = data_mask.get(ds, {})
        ds_remap = remap.get(ds, {})
        if ds_mask is None:
            new_mask[ds] = None
            continue
        ds_mask_new = new_mask[ds] = {}

        eg_keys = ds_mask.keys() | ds_remap.keys() if is_sub else ds_mask.keys()
        for eg in eg_keys:
            eg_mask = ds_mask.get(eg, [])
            eg_remap = ds_remap.get(eg, {})
            if eg_mask is None:
                ds_mask_new[eg] = None
                continue

            if not isinstance(eg_mask, list):
                raise ValueError(
                    f"Malformed mask at '{ds}/{eg}': expected list or None, got "
                    f"{type(eg_mask).__name__}"
                )
            eg_mask_new = ds_mask_new[eg] = []

            if not is_sub:
                eg_mask_new.extend(eg_remap.get(i, i) for i in eg_mask)
                continue

            # for a sub mask, we need to subscribe to all renamed internal attributes in the mask.
            # this may be many to one
            reversed_remap = {}
            for k, v in eg_remap.items():
                reversed_remap.setdefault(v, []).append(k)

            # the new sub maks consists of:
            #  all attributes in the original mask that are not affected by the remap
            #  the attributes in the original mask that are affected by the remap are completely
            #    replaced
            #  any new attributes in the remap are added

            for attr in set(eg_mask) | reversed_remap.keys():
                eg_mask_new.extend(reversed_remap.get(attr, [attr]))

    return new_mask


apply_remap_to_pub_mask = functools.partial(_apply_remap, kind="pub")
apply_remap_to_sub_mask = functools.partial(_apply_remap, kind="sub")
