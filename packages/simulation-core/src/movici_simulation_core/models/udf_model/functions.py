import typing as t

import numpy as np

from movici_simulation_core.core.arrays import TrackedCSRArray
from movici_simulation_core.core.data_format import is_undefined_csr, is_undefined_uniform
from movici_simulation_core.core.data_type import NP_TYPES, UNDEFINED
from movici_simulation_core.core.schema import infer_data_type_from_array
from movici_simulation_core.csr import csr_binop, row_wise_max, row_wise_min, row_wise_sum
from movici_simulation_core.models.udf_model.result_type import (
    ResultType,
    Shape,
    combine,
    promote,
)

functions = {}

result_types: t.Dict[str, t.Callable[[t.List[ResultType]], ResultType]] = {}
"""Type rules, keyed by function name. A rule maps the result types of a function's arguments onto
the result type of the call. A function without a rule produces a result of unknown type, which
makes the caller fall back on a default rather than fail.
"""


def func(name: str, returns: t.Optional[t.Callable[[t.List[ResultType]], ResultType]] = None):
    def decorator(f):
        functions[name] = f
        if returns is not None:
            result_types[name] = returns
        return f

    return decorator


def elementwise_result(py_type: t.Optional[t.Type] = None):
    """Type rule for a function that operates elementwise on its arguments"""
    return lambda args: combine(*args, py_type=py_type)


def row_wise_result(args: t.List[ResultType]) -> ResultType:
    """Type rule for a function that reduces the values of a single entity to one value"""
    if len(args) == 1:
        return args[0].reduced()
    return combine(*args)


def group_result(py_type: t.Optional[t.Type] = None):
    """Type rule for a function that reduces an entire entity group to a single value. Without a
    `py_type` the result is at least an integer, since summing booleans produces a count.
    """
    return lambda args: ResultType(
        py_type if py_type is not None else promote(args[0].py_type, int), Shape.SCALAR
    )


def apply_unary(ufunc, value):
    """Apply an elementwise function to a csr array, uniform array or scalar. The csr structure of
    the input is preserved.
    """
    if isinstance(value, TrackedCSRArray):
        return TrackedCSRArray(ufunc(value.data), row_ptr=value.row_ptr.copy())
    return ufunc(value)


def apply_binary(ufunc, left, right):
    """Apply an elementwise function to any combination of csr arrays, uniform arrays and scalars.
    A uniform array or scalar operand is broadcast along the rows of a csr operand.
    """
    if isinstance(left, TrackedCSRArray):
        return left.__bin_op__(right, ufunc)
    if isinstance(right, TrackedCSRArray):
        return right.__r_bin_op__(left, ufunc)
    return ufunc(left, right)


def undefined_on_non_finite(value):
    """Turn non-finite results (``inf`` and ``-inf``) into undefined values. A Movici dataset has
    no representation for infinity, so an expression that cannot produce a finite number produces
    an undefined value instead. This keeps the result detectable downstream, eg. by ``default``.

    A csr operand is updated to hold the corrected data, so only call this on freshly calculated
    results.
    """
    if isinstance(value, TrackedCSRArray):
        value.data = undefined_on_non_finite(value.data)
        return value
    if isinstance(value, np.ndarray):
        if not np.issubdtype(value.dtype, np.floating):
            return value
        return np.where(np.isfinite(value), value, np.nan)
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return np.nan
    return value


def divide(numerator, denominator):
    """Division as used by the ``/`` operator. Division by zero yields an undefined value rather
    than an infinity, and undefined operands propagate into the result.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        return undefined_on_non_finite(apply_binary(np.divide, numerator, denominator))


def power(base, exponent):
    """Exponentiation as used by the ``**`` operator"""
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        return undefined_on_non_finite(apply_binary(np.power, base, exponent))


def modulo(value, divisor):
    """Remainder as used by the ``%`` operator"""
    with np.errstate(divide="ignore", invalid="ignore"):
        return undefined_on_non_finite(apply_binary(np.mod, value, divisor))


def logical_and(left, right):
    """Elementwise conjunction as used by the ``and`` (``&&``) operator"""
    return apply_binary(np.logical_and, left, right)


def logical_or(left, right):
    """Elementwise disjunction as used by the ``or`` (``||``) operator"""
    return apply_binary(np.logical_or, left, right)


def _register_unary(name: str, ufunc, py_type=float, guard_non_finite: bool = False):
    """Register an elementwise numpy ufunc as a udf function. `py_type` is the python type of the
    result, or `None` when the ufunc preserves the type of its argument.
    """

    def wrapped(value):
        with np.errstate(divide="ignore", invalid="ignore"):
            result = apply_unary(ufunc, value)
        return undefined_on_non_finite(result) if guard_non_finite else result

    wrapped.__name__ = name
    wrapped.__doc__ = f"Elementwise ``{name}``, may be applied to uniform and csr attributes"
    functions[name] = wrapped
    result_types[name] = elementwise_result(py_type)
    return wrapped


for _name, _ufunc, _py_type in (
    # np.absolute and np.sign preserve the type of their argument, the others always produce
    # floating point values
    ("abs", np.absolute, None),
    ("sign", np.sign, None),
    ("sqrt", np.sqrt, float),
    ("exp", np.exp, float),
    ("sin", np.sin, float),
    ("cos", np.cos, float),
    ("tan", np.tan, float),
    ("floor", np.floor, float),
    ("ceil", np.ceil, float),
    ("round", np.round, float),
):
    _register_unary(_name, _ufunc, _py_type)

# the logarithm of zero is -inf, which is turned into an undefined value
for _name, _ufunc in (("log", np.log), ("log10", np.log10), ("log2", np.log2)):
    _register_unary(_name, _ufunc, float, guard_non_finite=True)

# `not` is an operator in the expression grammar, the parser lowers it onto this function
_register_unary("not", np.logical_not, bool)


@func("clip", returns=elementwise_result())
def clip_func(value, lower, upper):
    """Limit ``value`` to the range [``lower``, ``upper``]"""
    return apply_binary(np.minimum, apply_binary(np.maximum, value, lower), upper)


def defined_values(value) -> np.ndarray:
    """All defined values of an attribute as a flat array. Undefined values are left out, so that
    a single undefined entity does not make an entire group reduction undefined.
    """
    if isinstance(value, TrackedCSRArray):
        data = value.data
    elif isinstance(value, np.ndarray):
        data = value
    else:
        data = np.asarray([value])
    if data.size == 0:
        return data.reshape(-1)
    data_type = infer_data_type_from_array(data)
    return np.asarray(data)[~data_type.is_undefined(data)]


@func("total", returns=group_result())
def total_func(value):
    """The sum of every defined value in the entity group, as a single number.

    Where ``sum`` reduces the values of each entity separately, ``total`` reduces the entire entity
    group, so ``a / total(a)`` expresses each entity's share of the whole.
    """
    return np.sum(defined_values(value))


@func("mean", returns=group_result(float))
def mean_func(value):
    """The average of every defined value in the entity group, as a single number. Undefined when
    the entity group holds no defined values at all.
    """
    values = defined_values(value)
    if values.size == 0:
        return NP_TYPES[float].type(UNDEFINED[float])
    return np.mean(values)


@func("count", returns=group_result(int))
def count_func(value):
    """The number of defined values in the entity group, as a single number"""
    return defined_values(value).size


@func("any", returns=group_result(bool))
def any_func(value):
    """Whether any defined value in the entity group is true, as a single boolean"""
    return bool(np.any(defined_values(value)))


@func("all", returns=group_result(bool))
def all_func(value):
    """Whether every defined value in the entity group is true, as a single boolean"""
    return bool(np.all(defined_values(value)))


GROUP_REDUCERS = frozenset({"total", "mean", "count", "any", "all"})
"""Functions whose result depends on every entity in the entity group, rather than only on the
entity a value belongs to
"""


@func("sum", returns=row_wise_result)
def sum_func(arr):
    if isinstance(arr, TrackedCSRArray):
        return row_wise_sum(arr.data, arr.row_ptr)
    if isinstance(arr, np.ndarray):
        return np.sum(arr, axis=tuple(range(1, arr.ndim)))
    return np.sum(arr)


@func("min", returns=row_wise_result)
def min_func(*arrays_or_values):
    """calculate row-wise minimum value of n arrays or values. Every array must have the same
    length in the first dimension. Values are broadcasted along the first axis
    """
    return _extreme_func(
        arrays_or_values,
        row_wise_csr=row_wise_min,
        row_wise_uniform=np.amin,
        reduce_func=np.minimum,
    )


@func("max", returns=row_wise_result)
def max_func(*arrays_or_values):
    """calculate row-wise maximum value of n arrays or values. Every array must have the same
    length in the first dimension. Values are broadcasted along the first axis
    """
    return _extreme_func(
        arrays_or_values,
        row_wise_csr=row_wise_max,
        row_wise_uniform=np.amax,
        reduce_func=np.maximum,
    )


def _extreme_func(arrays_or_values, row_wise_csr, row_wise_uniform, reduce_func):
    """
    calculates extreme (ie min or max) for multiple inputs. Result shape depends on first input.
    Rules:

    - for a single entry (array), reduce by all axes except axis 0
    - for multiple inputs, calculate the element wise minimum:
      min([1,2,3], [4,1,2], 1.5) == [1, 1, 1.5]
      min([[1,2],[3], []], 2) == [[1,2],[2],[]]
      min([[1,2],[3], []], [1.5, 2, 0]) == [[1,1.5],[2],[]]
      min([[1,2],[3], []], [1.5, 2, 0], 1.7) == [[1,1.5],[1.7],[]]


    :param arrays_or_values: multiple operands to perform the min/max calculation
    :param row_wise_csr:
    :param row_wise_uniform:
    :param reduce_func:
    :return:
    """
    if len(arrays_or_values) < 1:
        raise TypeError("max() function requires at least one argument")

    item = arrays_or_values[0]

    if len(arrays_or_values) == 1:
        if isinstance(item, TrackedCSRArray):
            data_type = infer_data_type_from_array(item.data)
            return row_wise_csr(item.data, item.row_ptr, empty_row=data_type.undefined)
        elif isinstance(item, np.ndarray):
            return row_wise_uniform(item, axis=tuple(range(1, item.ndim)))
        else:
            # item is a scalar, which cannot be reduced
            return item

    if isinstance(item, TrackedCSRArray):
        working_func = _extreme_func_csr
    elif isinstance(item, np.ndarray):
        working_func = _extreme_func_uniform
    else:
        raise ValueError(
            "min/max functions should have an attribute as their first argument, not a scalar"
        )

    result = item

    for item in arrays_or_values[1:]:
        result = working_func(result, item, reduce_func)
    return result


def _extreme_func_csr(
    csr_array: TrackedCSRArray, other: t.Union[np.ndarray, float, int], extreme_func
):
    if isinstance(other, np.ndarray):
        data = csr_binop(csr_array.data, csr_array.row_ptr, other, extreme_func)
    else:
        data = extreme_func(csr_array.data, other)
    return TrackedCSRArray(data, row_ptr=csr_array.row_ptr)


def _extreme_func_uniform(
    array: np.ndarray, other: t.Union[np.ndarray, TrackedCSRArray, float, int], extreme_func
):
    # `other` may be a csr array, in which case the uniform values are broadcast along its rows
    # and the result is a csr array
    return apply_binary(extreme_func, array, other)


@func("default", returns=lambda args: combine(*args, py_type=args[0].py_type))
def default_func(
    arr: t.Union[TrackedCSRArray, np.ndarray],
    default_val: t.Union[float, TrackedCSRArray, np.ndarray],
):
    if isinstance(arr, np.ndarray):
        if isinstance(default_val, TrackedCSRArray):
            raise TypeError("Cannot assign default CSR data to a Uniform attribute")
        data_type = infer_data_type_from_array(arr)
        undefined = is_undefined_uniform(arr, data_type)
        rv = arr.copy()
        rv[undefined] = (
            default_val[undefined] if isinstance(default_val, np.ndarray) else default_val
        )
        return rv
    if isinstance(arr, TrackedCSRArray):
        data_type = infer_data_type_from_array(arr.data)
        undefined = np.flatnonzero(is_undefined_csr(arr, data_type))
        if isinstance(default_val, (float, int, bool)):
            default_values = TrackedCSRArray(
                data=np.full_like(undefined, fill_value=default_val, dtype=arr.data.dtype),
                row_ptr=np.arange(len(undefined) + 1),
            )

        elif isinstance(default_val, np.ndarray):
            default_values = TrackedCSRArray(
                data=default_val[undefined],
                row_ptr=np.arange(len(undefined) + 1),
            )

        elif isinstance(default_val, TrackedCSRArray):
            default_values = default_val.slice(undefined)
        else:
            raise TypeError(f"Usupported default value of type {type(default_val)}")

        rv = arr.copy()
        rv.update(default_values, undefined)
        return rv


# `if` takes its shape from the branches and its python type from the first branch, mirroring the
# implementation below. It does not support csr values
@func("if", returns=lambda args: combine(*args[1:], py_type=args[1].py_type))
def if_func(*arrays_or_values):
    if len(arrays_or_values) != 3:
        raise TypeError("function 'if' requires 3 arguments: COND, IF_TRUE, IF_FALSE")
    cond, if_true, if_false = arrays_or_values

    if isinstance(if_true, TrackedCSRArray) or isinstance(if_false, TrackedCSRArray):
        raise TypeError("function 'if' does not support csr attributes (yet)")

    if isinstance(cond, bool):
        return if_true if cond else if_false

    if isinstance(cond, np.ndarray) and cond.dtype in [bool, NP_TYPES[bool], NP_TYPES[int]]:
        cond = np.asarray(cond, dtype=bool)
        dtype = if_true.dtype if isinstance(if_true, np.ndarray) else type(if_true)
        rv = np.empty_like(cond, dtype=dtype)
        rv[cond] = if_true[cond] if isinstance(if_true, np.ndarray) else if_true
        rv[~cond] = if_false[~cond] if isinstance(if_false, np.ndarray) else if_false
        return rv

    raise TypeError("conditional for 'if' must be boolean or boolean array")
