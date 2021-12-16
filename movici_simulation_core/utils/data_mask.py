import typing as t


def validate_mask(data_mask: t.Optional[dict]):
    """determines whether the dataset filter has the correct shape, it must be lists inside
    dictionaries inside a dictionary. eg.:
    {"some_dataset": {"some_entity_group": ["attribute1", "component_a/attribute2"]}}
    Also, at every level, the filter may be filled. these are invalid filters eg:
      * {"some_dataset": {}}
      * {"some_dataset": {"some_entity_group": ["attribute1"], "empty_group": []}}
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


def filter_data(data: dict, mask: t.Optional[dict]):
    def filter_helper(data_: dict, mask_: t.Union[dict, list, None]):
        if mask_ is None:
            return data_

        if isinstance(mask_, list):
            ensure_id(mask_)
            mask_ = expand_list_mask(mask_)

        if isinstance(mask_, dict):
            return {
                key: filter_helper(data_[key], mask_[key]) for key in data_.keys() & mask_.keys()
            }

    return filter_helper(data, mask)


def ensure_id(mask: t.List[str]):
    if "id" not in mask:
        mask.append("id")


def expand_list_mask(mask: t.List[str]) -> dict:
    rv = {}
    for attr in mask:
        component, name = split_attribute(attr)
        if component is None:
            rv[name] = None
        else:
            comp_dict = rv.setdefault(component, {})
            comp_dict[name] = None
    return rv


def split_attribute(attribute: str):
    if "/" in attribute:
        return attribute.split("/", maxsplit=1)
    return None, attribute


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
