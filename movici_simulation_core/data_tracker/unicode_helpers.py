import math
import typing as t
import numpy as np


def determine_new_unicode_dtype(
    a: np.ndarray, b: t.Union[np.ndarray, str], max_val=2 ** 8
) -> t.Optional[np.dtype]:
    """Determine the new unicode dtype for array `a` if it needs to be updated with data coming
    from `b`.

    Returns: a new `np.dtype` if required or `None` if the dtype can remain the same. A new dtype
    is the first power of 2 that fits the dtype of `b`
    """
    newsize = None
    if not (np.issubdtype(a.dtype, str) or np.issubdtype(a.dtype, bytes)):
        return newsize
    newsize = a.dtype.itemsize // 4
    if isinstance(b, str) and len(b) > (a.dtype.itemsize // 4):
        newsize = next_power_of_two(len(b), max_val)
    elif isinstance(b, np.ndarray) and b.dtype.itemsize > a.dtype.itemsize:
        newsize = next_power_of_two(b.dtype.itemsize // 4, max_val)
    new_dtype = np.dtype(f"<U{newsize}")
    if new_dtype != a.dtype:
        return new_dtype
    return None


def next_power_of_two(val, max_val=2 ** 8):
    return min(2 ** (math.ceil(math.log2(val))), max_val)


def equal_str_dtypes(a: np.ndarray, b: np.ndarray):
    return (
        np.issubdtype(a.dtype, str) or np.issubdtype(a.dtype, bytes)
    ) and b.dtype.itemsize == a.dtype.itemsize
