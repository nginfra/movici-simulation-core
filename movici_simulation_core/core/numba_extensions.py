import functools
import os

import numba
import numpy as np
from numba import types
from numba.core.config import reload_config
from numba.core.extending import overload, register_jitable
from numba.np.numpy_support import type_can_asarray


def generated_jit(func=None, **kwargs):
    """Custom decorator that replaces `numba.generated_jit` and works also when the jit compiler
    is disabled
    """
    if numba.config.DISABLE_JIT:
        if func is None:
            return generated_jit
        return _fake_generated_jit(func)
    # Try to use generated_jit if available (older numba versions)
    # Otherwise, use overload_method for newer versions
    try:
        return numba.generated_jit(func, **kwargs)
    except AttributeError:
        # For newer numba versions, we need a different approach
        # Since generated_jit was used for creating specialized implementations,
        # we'll create a wrapper that mimics this behavior
        if func is None:
            return lambda f: generated_jit(f, **kwargs)
        
        @functools.wraps(func)
        def wrapper(*args, **kw):
            # Get the types of the arguments
            arg_types = tuple(numba.typeof(arg) for arg in args)
            # Create a specialized implementation
            impl_func = func(*arg_types)
            # JIT compile the implementation
            # Use the kwargs as-is, they're properly set by the caller
            jitted_impl = numba.jit(**kwargs)(impl_func)
            # Call the jitted implementation
            return jitted_impl(*args, **kw)
        
        return wrapper


def _fake_generated_jit(func):
    @functools.wraps(func)
    def run_generated_jit_func(*args, **kwargs):
        arg_types = (numba.typeof(arg) for arg in args)
        kwargs_types = {k: numba.typeof(v) for k, v in kwargs.items()}
        return func(*arg_types, **kwargs_types)(*args, **kwargs)

    return run_generated_jit_func


def disable_jit():
    os.environ["NUMBA_DISABLE_JIT"] = "1"
    reload_config()


def configure_numba_performance():
    """Configure Numba for optimal performance.
    
    Call this function early in your application to set optimal Numba configuration
    for the movici-simulation-core workload.
    """
    # Enable parallel execution for supported operations
    os.environ.setdefault("NUMBA_ENABLE_THREADING_LAYER", "1")
    
    # Use optimal cache directory location
    cache_dir = os.environ.get("NUMBA_CACHE_DIR")
    if cache_dir is None:
        # Use a more persistent cache location if available
        import tempfile
        cache_dir = os.path.join(tempfile.gettempdir(), "numba_cache", "movici")
        os.environ["NUMBA_CACHE_DIR"] = cache_dir
    
    # Enable debugging info in development
    debug_mode = os.environ.get("MOVICI_DEBUG", "").lower() in ("1", "true", "yes")
    if debug_mode:
        os.environ.setdefault("NUMBA_DEBUG", "1")
        os.environ.setdefault("NUMBA_DEVELOPER_MODE", "1")
    
    # Optimize for scientific computing workloads
    os.environ.setdefault("NUMBA_BOUNDSCHECK", "0")  # Disable bounds checking for performance
    os.environ.setdefault("NUMBA_FASTMATH", "1")     # Enable fast math optimizations
    
    reload_config()


# Performance-optimized decorator for hot paths
def fast_njit(func=None, **kwargs):
    """Numba JIT decorator optimized for performance-critical code paths.
    
    This decorator applies optimal settings for scientific computing workloads
    in movici-simulation-core.
    
    Usage:
        @fast_njit
        def my_function(data):
            return result
            
        # Or with custom options:
        @fast_njit(parallel=True)
        def parallel_function(data):
            return result
    """
    default_kwargs = {
        'cache': True,           # Always cache compiled functions
        'fastmath': True,        # Enable fast math optimizations
        'nogil': True,          # Release GIL for better parallelization
        'boundscheck': False,   # Disable bounds checking for speed
    }
    
    # Handle caching gracefully for inline/testing code
    if func is not None:
        try:
            # Check if we can cache this function
            import inspect
            filename = inspect.getfile(func)
            if filename == '<string>' or '<stdin>' in filename:
                default_kwargs['cache'] = False
        except (OSError, TypeError):
            default_kwargs['cache'] = False
    default_kwargs.update(kwargs)
    
    if func is None:
        # Called with arguments: @fast_njit(parallel=True)
        return lambda f: numba.njit(**default_kwargs)(f)
    else:
        # Called without arguments: @fast_njit
        return numba.njit(**default_kwargs)(func)


@overload(np.isclose, jit_options=dict(cache=True))
def np_isclose(a, b, rtol=1e-05, atol=1e-08, equal_nan=False):
    """Custom implementation of `np.isclose` until numba has native support. See also:
    https://github.com/numba/numba/issues/5977
    """

    # Allow scalar strings to pass through
    a_is_scalar_string = isinstance(a, (types.UnicodeType, types.CharSeq))
    b_is_scalar_string = isinstance(b, (types.UnicodeType, types.CharSeq))
    
    if not (type_can_asarray(a) or a_is_scalar_string) or not (type_can_asarray(b) or b_is_scalar_string):
        raise numba.TypingError("Inputs a and b must be array-like.")

    # Check if inputs are string/unicode types  
    a_type = getattr(a, 'dtype', a) if hasattr(a, 'dtype') else a
    b_type = getattr(b, 'dtype', b) if hasattr(b, 'dtype') else b
    
    # Debug: print type information
    # print(f"DEBUG: a_type={a_type}, type={type(a_type)}, str={str(a_type)}")
    # print(f"DEBUG: b_type={b_type}, type={type(b_type)}, str={str(b_type)}")
    
    # Better detection for unicode/string types
    a_is_string = (a_is_scalar_string or
                   isinstance(a_type, (types.UnicodeType, types.CharSeq)) or 
                   (hasattr(a_type, '__class__') and 'unicode' in str(a_type.__class__).lower()) or
                   (hasattr(a_type, 'key') and 'char' in str(a_type.key).lower()) or
                   'unichar' in str(a_type).lower())
    
    b_is_string = (b_is_scalar_string or
                   isinstance(b_type, (types.UnicodeType, types.CharSeq)) or 
                   (hasattr(b_type, '__class__') and 'unicode' in str(b_type.__class__).lower()) or
                   (hasattr(b_type, 'key') and 'char' in str(b_type.key).lower()) or
                   'unichar' in str(b_type).lower())
    
    if a_is_string or b_is_string:
        # String comparison - only equality makes sense
        def string_impl(a, b, rtol=1e-05, atol=1e-08, equal_nan=False):
            return a == b
        return string_impl

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
