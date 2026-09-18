import typing as t

import numpy as np

from movici_simulation_core import Index
from movici_simulation_core.core import get_rowptr, has_rowptr_key
from movici_simulation_core.core.data_type import get_default_comparator, get_undefined
from movici_simulation_core.core.schema import DEFAULT_ROWPTR_KEY
from movici_simulation_core.csr import remove_undefined_csr, slice_csr_array, update_csr_array
from movici_simulation_core.types import DatasetData as NumpyDatasetData
from movici_simulation_core.types import EntityData, NumpyAttributeData
from movici_simulation_core.utils import determine_new_unicode_dtype


class DatasetStateAggregator:
    """Aggregate multiple dataset dicts to a single dataset. This can be used to calculate a
    state from an initial dataset and simulation updates, or to patch a dataset.

    When generating a scenario state, an incomplete dataset may be given.

    New entities may be created by setting their id to ``-1``. This indicates that a new id must
    be generated which is guaranteed to be unique *within the current aggregated state*. If there
    is a chance that new entities may be generated, be sure to always add the current complete
    dataset first. Alternatively, you can set ``allow_new_entities`` to ``False`` to prevent any
    new entities from being created and raise an error instead

    Entities may be deleted by setting their ``deleted`` pseudo-attribute to ``True``. This will
    remove them from the state

    :param allow_new_entities: Allow new entities to be created when applying updates to the state.
        (Default: ``False``)
    """

    def __init__(self, allow_new_entities=False):
        self.allow_new_entities = allow_new_entities
        self._state: dict[str, tuple[Index, EntityData]] = {}

    @property
    def state(self):
        def _maybe_delete_entries(attr_data: NumpyAttributeData, keep_entries: np.ndarray | None):
            if keep_entries is None:
                return attr_data
            return slice_attribute(attr_data, np.flatnonzero(keep_entries))

        state: NumpyDatasetData = {}
        for entity_name, (index, entity_data) in self._state.items():
            deleted = entity_data.get("deleted")
            keep_entries = None
            if deleted is not None:
                keep_entries = deleted["data"] < 1  # catches 0 and UNDEFINED[bool]
            if keep_entries is not None and not np.any(keep_entries):
                # skip entity group with no 'alive' entities
                continue
            state[entity_name] = t.cast(
                EntityData,
                {
                    "id": _maybe_delete_entries({"data": index.ids}, keep_entries),
                    **{
                        name: _maybe_delete_entries(attr, keep_entries)
                        for name, attr in entity_data.items()
                        if not all_undefined(attr) and name != "deleted"
                    },
                },
            )

        return state

    def add_dataset_data(
        self, data: NumpyDatasetData, is_initial=False, undefined_values_overwrite=False
    ):
        """Add dataset data to the current state. Dataset data must be in movici numpy dict form.

        :param data: Dataset data to be added. This must entity based data in Movici numpy dict
            form
        :param is_initial: A boolean that indicates, whether the data is the initial data.
            Regardless of the ``DatasetStateAggregator.allow_new_entities`` setting, initial data
            is always allowed to create new entities. However, it is only allowed to add initial
            data once, when the internal state is still empty. Default (``False``)
        :param undefined_values_overwrite: By default, undefined values are considered to be
            "holes" and do not overwrite any existing values in the attribute for that specific
            entity. By setting ``undefined_values_overwrite`` to ``True``, any undefined value in
            the attribute array will "unset" the attribute value for that entity. If all values for
            an attribute are unset, the attribute will be removed from the state.
        """
        if is_initial:
            if self._state:
                raise ValueError("can only add initial state once")

        allow_new_entities = self.allow_new_entities or is_initial
        for entity_group, entity_group_data in data.items():
            if "id" not in entity_group_data:
                raise ValueError(f"No 'id' array found for entity group '{entity_group}'")
            if entity_group not in self._state:
                if not allow_new_entities:
                    raise ValueError(
                        f"'{entity_group}' is not valid entity group for this dataset"
                    )
                self._add_new_entity_group(entity_group, entity_group_data)
                continue

            index, current_entity_data = self._state[entity_group]

            ids = entity_group_data["id"]["data"]
            indices = t.cast(np.ndarray, index[ids])
            invalid = np.flatnonzero(indices == -1)
            if len(invalid) > 0:
                if not allow_new_entities:
                    raise ValueError(
                        f"id{'s' if len(invalid) > 1 else ''} "
                        f"{', '.join(str(val) for val in ids[invalid])} not found in dataset"
                    )
                else:
                    # we don't own the id array, so make a copy instead of mutating (if necessary)
                    ids = self._get_filled_ids(ids, copy=True)
                    self._create_new_entities(entity_group, ids[invalid])
                    indices = t.cast(np.ndarray, index[ids])
            for attribute_name, attr_data in entity_group_data.items():
                if attribute_name == "id":
                    continue
                if not undefined_values_overwrite:
                    attr_data, attr_indices = strip_undefined(attr_data, indices)
                else:
                    attr_indices = indices
                update_data = attr_data["data"]
                is_csr = has_rowptr_key(t.cast(dict, attr_data))
                if attribute_name not in current_entity_data:
                    current_entity_data[attribute_name] = get_undefined_array(
                        length=len(index),
                        unit_shape=update_data.shape[1:],
                        dtype=update_data.dtype,
                        is_csr=is_csr,
                    )
                update_attribute_data(current_entity_data[attribute_name], attr_data, attr_indices)

    def _generate_new_ids(self, count: int):
        next_id = (max(index.max() for index, _ in self._state.values()) + 1) if self._state else 0
        return np.arange(next_id, next_id + count)

    def _add_new_entity_group(self, name: str, entity_data: EntityData):
        entity_data = deep_copy_entity_data(entity_data)
        ids = self._get_filled_ids(entity_data["id"]["data"])
        self._check_unique_ids(ids, name)
        self._state[name] = (Index(ids), {k: v for k, v in entity_data.items() if k != "id"})

    def _check_unique_ids(self, ids: np.ndarray, target_entity_group):
        for existing_eg, (index, _) in self._state.items():
            if existing_eg == target_entity_group:
                continue
            indices = t.cast(np.ndarray, index[ids])
            duplicates = np.flatnonzero(indices >= 0)
            if len(duplicates > 0):
                raise ValueError(
                    f"id{'s' if len(duplicates) > 1 else ''}"
                    f" {', '.join(str(val) for val in ids[duplicates])} already"
                    f" exist{'s' if len(duplicates) == 1 else ''} in entity group '{existing_eg}'"
                )

    def _get_filled_ids(self, ids: np.ndarray, copy=False):
        """if the ids array contains any negative values, such as ``-1`` or ``UNDEFINED[int]``
        assign them new ids.

        :return: a new ``id`` array with all values filled
        """
        to_create = np.flatnonzero(ids < 0)
        new_ids = np.array([], dtype=np.int32)
        if (count := len(to_create)) > 0:
            if copy:
                ids = ids.copy()
            new_ids = self._generate_new_ids(count)
            ids[to_create] = new_ids
        return ids

    def _create_new_entities(self, entity_group: str, ids):
        self._check_unique_ids(ids, target_entity_group=entity_group)
        index, entity_data = self._state[entity_group]
        old_size = len(index)
        index.add_ids(ids)
        for attribute in entity_data.values():
            self._grow_attribute(attribute, old_size, new_size=len(index))

    def _grow_attribute(self, attribute: NumpyAttributeData, old_size: int, new_size: int):
        data = attribute["data"]
        new_attribute = get_undefined_array(
            length=new_size,
            unit_shape=data.shape[1:],
            dtype=data.dtype,
            is_csr=has_rowptr_key(t.cast(dict, attribute)),
        )
        update_attribute_data(new_attribute, attribute, np.arange(0, old_size))
        t.cast(dict, attribute).clear()
        t.cast(dict, attribute).update(new_attribute)


def deep_copy_entity_data(obj: EntityData) -> EntityData:
    def _helper(obj: dict | np.ndarray):
        if isinstance(obj, np.ndarray):
            return obj.copy()
        return {k: _helper(v) for k, v in obj.items()}

    return t.cast(EntityData, _helper(obj))


def update_attribute_data(
    current_data: NumpyAttributeData, update_data: NumpyAttributeData, indices
):
    if dtype := determine_new_unicode_dtype(current_data["data"], update_data["data"]):
        current_data["data"] = current_data["data"].astype(dtype)
    current_rowptr = get_rowptr(t.cast(dict, current_data))
    update_rowptr = get_rowptr(t.cast(dict, update_data))

    if current_rowptr is not None:
        if update_rowptr is None:
            raise ValueError("cannot update csr-attribute with uniform data")
        new_data, new_rowptr = update_csr_array(
            data=current_data["data"],
            row_ptr=current_rowptr,
            upd_data=update_data["data"],
            upd_row_ptr=update_rowptr,
            upd_indices=indices,
        )

        t.cast(dict, current_data).clear()
        t.cast(dict, current_data).update({"data": new_data, DEFAULT_ROWPTR_KEY: new_rowptr})
    else:
        if update_rowptr is not None:
            raise ValueError("cannot update uniform attribute with csr data")
        current_data["data"][indices] = update_data["data"]


def get_undefined_array(
    length: int, unit_shape: tuple, dtype: t.Any, is_csr=False
) -> NumpyAttributeData:
    undefined = get_undefined(dtype)
    result: NumpyAttributeData = {
        "data": np.full((length, *unit_shape), fill_value=undefined, dtype=dtype)
    }
    if is_csr:
        result[DEFAULT_ROWPTR_KEY] = np.arange(0, length + 1)
    return result


def get_undefined_value_for_attribute(attribute: NumpyAttributeData):
    undefined = get_undefined(attribute["data"].dtype)
    if undefined is None:
        raise TypeError(f"unsupported dtype {attribute['data'].dtype} ")
    return undefined


def all_undefined(attr: NumpyAttributeData):
    undefined_value = get_undefined_value_for_attribute(attr)
    return np.all(is_undefined(attr["data"], undefined_value))


def slice_attribute(attr: NumpyAttributeData, indices: np.ndarray):
    if (rowptr := get_rowptr(t.cast(dict, attr))) is not None:
        if len(indices) == len(rowptr) - 1:
            return attr
        new_data, new_rowptr = slice_csr_array(attr["data"], rowptr, indices)
        return {"data": new_data, DEFAULT_ROWPTR_KEY: new_rowptr}
    else:
        data_array = attr["data"]
        if len(indices) == len(data_array):
            return attr
        return {"data": data_array[indices]}


def strip_undefined(
    attr_data: NumpyAttributeData, indices: np.ndarray
) -> tuple[NumpyAttributeData, np.ndarray]:
    data_array = attr_data["data"]
    rowptr = get_rowptr(t.cast(dict, attr_data))
    undefined_value = get_undefined_value_for_attribute(attr_data)

    if undefined_value is None:
        raise TypeError(f"unsupported dtype {data_array.dtype} ")

    undefs = is_undefined(data_array, undefined_value)
    undefined_count = np.sum(undefs)

    if not undefined_count:
        return attr_data, indices

    if rowptr is not None:
        new_data_shape = (data_array.shape[0] - undefined_count, *data_array.shape[1:])

        new_data, new_row_ptr, new_indices = remove_undefined_csr(
            data_array,
            rowptr,
            indices,
            undefined_value,
            undefined_count,
            new_data_shape,
            compare=get_default_comparator(data_array.dtype),
        )
        return {"data": new_data, DEFAULT_ROWPTR_KEY: new_row_ptr}, new_indices
    return {"data": data_array[~undefs]}, indices[~undefs]


def is_undefined(arr, undefined):
    result = arr == undefined
    if not isinstance(undefined, str) and np.isnan(undefined):
        result = result | np.isnan(arr)

    # reduce over all but the first axis, e.g. an array with shape (10,2,3) should be
    # reduced to a result array of shape (10,) by reducing over axes (1,2). An single
    # entity's attribute is considered undefined if the item is undefined in all its
    # dimensions
    reduction_axes = tuple(range(1, len(result.shape)))
    return np.minimum.reduce(result, axis=reduction_axes)
