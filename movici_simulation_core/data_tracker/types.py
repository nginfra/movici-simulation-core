import typing as t
import numpy as np


class UniformPropertyData(t.TypedDict):
    data: np.ndarray


class CSRPropertyData(t.TypedDict, total=False):
    data: np.ndarray
    ind_ptr: t.Optional[np.ndarray]
    indptr: t.Optional[np.ndarray]
    row_ptr: t.Optional[np.ndarray]


NumpyPropertyData = t.Union[UniformPropertyData, CSRPropertyData]

ComponentData = t.Dict[str, NumpyPropertyData]
EntityData = t.Dict[str, t.Union[NumpyPropertyData, ComponentData]]
DatasetData = t.Dict[str, EntityData]
PropertyIdentifier = t.Tuple[t.Optional[str], str]

ValueType = t.Union[int, float, bool, str]