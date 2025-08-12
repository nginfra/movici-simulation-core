# Performance Optimization Guide

This guide covers performance optimization strategies for movici-simulation-core.

## Numba Performance Configuration

### Quick Setup

For optimal performance, call the configuration function early in your application:

```python
from movici_simulation_core.core.numba_extensions import configure_numba_performance

# Call this before importing/using simulation models
configure_numba_performance()
```

### Performance Settings Explained

The `configure_numba_performance()` function sets these optimizations:

- **Threading Layer**: Enables parallel execution for supported operations
- **Persistent Caching**: Uses optimal cache directory for compiled functions
- **Fast Math**: Enables aggressive floating-point optimizations
- **Bounds Checking**: Disabled for maximum speed (use with caution)

### Environment Variables

You can also set these manually:

```bash
# Enable parallel threading
export NUMBA_ENABLE_THREADING_LAYER=1

# Use custom cache directory
export NUMBA_CACHE_DIR=/path/to/persistent/cache

# Enable fast math optimizations
export NUMBA_FASTMATH=1

# Disable bounds checking (production only)
export NUMBA_BOUNDSCHECK=0

# Development debugging
export MOVICI_DEBUG=1  # Enables Numba debugging info
```

### High-Performance Decorator

For performance-critical code paths, use the optimized decorator:

```python
from movici_simulation_core.core.numba_extensions import fast_njit

@fast_njit
def my_performance_critical_function(data):
    # This function will be compiled with optimal settings:
    # - cache=True
    # - fastmath=True
    # - nogil=True
    # - boundscheck=False
    return result
```

## Performance Best Practices

### 1. Warm-up JIT Compilation

Numba functions compile on first use. For consistent performance:

```python
# Warm up critical functions with small data
warm_up_data = np.array([1.0, 2.0])
warm_up_row_ptr = np.array([0, 2])
row_wise_sum(warm_up_data, warm_up_row_ptr)  # Triggers compilation
```

### 2. Use Appropriate Data Types

- Use `np.float64` for precision-critical calculations
- Use `np.float32` for memory-constrained scenarios
- Ensure consistent dtypes across function calls

### 3. Memory Layout Optimization

- Use C-contiguous arrays when possible: `np.ascontiguousarray(data)`
- Avoid unnecessary array copies
- Pre-allocate output arrays when feasible

### 4. Parallel Processing

For large datasets, consider:
- Using `numba.prange()` in compatible functions
- Breaking work into chunks for parallel processing
- Enabling threading layer (done automatically by `configure_numba_performance()`)

## Performance Monitoring

### Timing Critical Operations

```python
import time
import numpy as np
from movici_simulation_core.csr import row_wise_sum

# Generate test data
data = np.random.random(10000).astype(np.float64)
row_ptr = np.arange(0, len(data) + 1, 100)  # 100 rows

# Warm-up
row_wise_sum(data, row_ptr)

# Benchmark
start_time = time.perf_counter()
for _ in range(1000):
    result = row_wise_sum(data, row_ptr)
end_time = time.perf_counter()

print(f"Average time per call: {(end_time - start_time) / 1000 * 1000:.2f} ms")
```

### Memory Usage

Monitor memory usage for large simulations:

```python
import tracemalloc

tracemalloc.start()

# Run your simulation
result = your_simulation_function(data)

current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 1024 / 1024:.1f} MB")
print(f"Peak memory usage: {peak / 1024 / 1024:.1f} MB")
tracemalloc.stop()
```

## Hardware-Specific Optimizations

### CPU Architecture

- **Intel CPUs**: Fast math optimizations work well
- **ARM CPUs**: May need different optimization flags
- **Multi-core**: Enable threading layer for parallel operations

### Memory Considerations

- **Large Datasets**: Consider chunked processing
- **Memory-Bound**: Optimize data layout and minimize copies
- **Cache Efficiency**: Keep frequently accessed data contiguous

## Troubleshooting Performance Issues

### Compilation Time

If compilation is slow:
- Check if persistent caching is enabled
- Verify cache directory is writable
- Consider pre-compiling critical functions

### Runtime Performance

If runtime is slower than expected:
- Verify optimal numba flags are set
- Check data types are appropriate
- Profile with `numba --annotate-html` for hotspots
- Ensure arrays are contiguous

### Memory Issues

If memory usage is high:
- Use appropriate dtypes (float32 vs float64)
- Avoid unnecessary array copies
- Consider streaming/chunked processing for large datasets
