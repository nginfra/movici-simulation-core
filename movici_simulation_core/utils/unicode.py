import math
import typing as t

import numpy as np


def determine_new_unicode_dtype(
    a: np.ndarray, b: t.Union[np.ndarray, str], max_size=2**8
) -> t.Optional[np.dtype]:
    """Determine the new unicode dtype for array `a` if it needs to be updated with data coming
    from `b`.

    Returns: a new `np.dtype` if required or `None` if the dtype can remain the same. A new dtype
    is the first power of 2 that fits the dtype of `b`
    """
    largest = largest_unicode_dtype(a, b, max_size)
    if largest != a.dtype:
        return largest
    return None


def largest_unicode_dtype(a: np.ndarray, b: t.Union[np.ndarray, str], max_size=2**8):
    """Determines whether the dtype of unicode array a and/or b must be upcasted to the largest
    size dtype of the two arrays to be able to use them both in numba jit compiled functions, since
    numba requires unicode arrays to be of the same itemsize in order to do certain operations,
    such as comparisons.

    :returns The largest dtype of the two or None if no upcasting has to be done (or when the
        arrays involved are not unicode or bytes)
    """

    def unicode_length(obj):
        if isinstance(obj, str):
            return len(obj)
        if isinstance(obj, np.ndarray) and (
            np.issubdtype(obj.dtype, str) or np.issubdtype(obj.dtype, bytes)
        ):
            return obj.dtype.itemsize // 4
        return None

    lengths = [size for i in (a, b) if (size := unicode_length(i)) is not None]
    if not lengths:
        return None
    return get_unicode_dtype(max(lengths))


def get_unicode_dtype(size, max_size=2**8):
    size = next_power_of_two(size, max_val=max_size)
    return np.dtype(f"<U{size}")


def next_power_of_two(val, max_val=2**8):
    return min(2 ** (math.ceil(math.log2(val))), max_val)


def equal_str_dtypes(a: np.ndarray, b: np.ndarray):
    return (
        np.issubdtype(a.dtype, str) or np.issubdtype(a.dtype, bytes)
    ) and b.dtype.itemsize == a.dtype.itemsize
