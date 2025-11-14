import os

import numba
import numpy as np
from numba.core.config import reload_config
from numba.core.extending import overload, register_jitable
from numba.np.numpy_support import type_can_asarray


def disable_jit():
    os.environ["NUMBA_DISABLE_JIT"] = "1"
    reload_config()


@overload(np.isclose, jit_options=dict(cache=True))
def np_isclose(a, b, rtol=1e-05, atol=1e-08, equal_nan=False):
    """Numba only has rudimentary np.isclose support. We provide a custom implementation of `np.isclose`
    until numba has better support. See also: https://github.com/numba/numba/issues/5977
    """

    if not type_can_asarray(a) or not type_can_asarray(b):
        raise numba.TypingError("Inputs a and b must be array-like.")

    if (
        rtol not in numba.types.real_domain | numba.types.integer_domain
        or atol not in numba.types.real_domain | numba.types.integer_domain
    ):
        raise numba.TypingError("Relative and absolute tolerance must be represented as floats.")

    def impl(a, b, rtol=1e-05, atol=1e-08, equal_nan=False):
        return _isclose(a, b, rtol, atol, bool(equal_nan))

    return impl


@register_jitable(cache=True)
def _isclose(a, b, rtol, atol, equal_nan):  # pragma: no cover
    # Implementation taken as much as possible from `numpy.core.numeric`

    x = np.asarray(a)
    y = np.asarray(b)

    # Cast the isfinite results to array again because numba's isfinite implementation doesn't
    # always return a 0d array on 0d input
    xfin = np.asarray(np.isfinite(x))
    yfin = np.asarray(np.isfinite(y))

    if np.all(xfin) and np.all(yfin):
        return np.abs(x - y) <= (atol + rtol * np.abs(y))

    else:
        finite = xfin & yfin

        # Numba only supports 1D arrays for boolean indexing, so we have to
        # flatten multidimensional arrays and then later shape it back to it's original shape

        return_shape = finite.shape
        finite = finite.reshape(-1)  # reassign in case the reshaping doesn't happen in place

        cond = np.zeros_like(finite)

        x = x.flatten()
        y = y.flatten()

        x = x * np.ones_like(cond)
        y = y * np.ones_like(cond)

        # Avoid subtraction with infinite/nan values...
        cond[finite] = np.abs(x[finite] - y[finite]) <= (atol + rtol * np.abs(y[finite]))

        # Check for equality of infinite values...
        cond[~finite] = x[~finite] == y[~finite]
        if equal_nan:
            # Make NaN == NaN
            both_nan = np.isnan(x) & np.isnan(y)

            # Needed to treat masked arrays correctly. = True would not work.
            cond[both_nan] = both_nan[both_nan]

        return cond.reshape(return_shape)
