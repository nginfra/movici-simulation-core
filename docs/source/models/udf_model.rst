User-Defined Function Model
============================

The User-Defined Function (UDF) model enables custom mathematical calculations on entity attributes using expression-based formulas. It provides a flexible way to implement domain-specific computations without writing new model code, supporting complex mathematical operations, conditional logic, and array manipulations.

Overview
--------

The UDF model is invaluable for:

- Custom metric calculations
- Mathematical transformations
- Derived attribute computation
- Business logic implementation
- Scientific formulas
- Data normalization
- Conditional calculations
- Array operations

This model compiles mathematical expressions into efficient code, supporting both scalar and array operations with automatic type handling.

Key Features
------------

- **Expression compiler**: Converts formulas to optimized code
- **Basic operations**: Arithmetic and comparison operators
- **Aggregation functions**: Sum, min, max operations
- **Array support**: Both uniform and CSR array handling
- **Type flexibility**: Automatic type inference and conversion
- **Multiple outputs**: Calculate multiple attributes in one pass
- **Optional inputs**: Handle missing data with default values

Supported Operations
--------------------

Mathematical Operations
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - Category
     - Operations
     - Description
   * - Basic Arithmetic
     - ``+, -, *, /``
     - Standard arithmetic operations
   * - Comparison
     - ``<, <=, >, >=, ==, !=``
     - Logical comparisons

Built-in Functions
^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - Function
     - Syntax
     - Description
   * - ``sum``
     - ``sum(array)``
     - Row-wise sum for CSR arrays, reduces all dimensions except first for uniform arrays
   * - ``min``
     - ``min(a, b, ...)``
     - Element-wise minimum across multiple inputs
   * - ``max``
     - ``max(a, b, ...)``
     - Element-wise maximum across multiple inputs
   * - ``default``
     - ``default(array, default_value)``
     - Replace undefined/missing values with default
   * - ``if``
     - ``if(condition, true_value, false_value)``
     - Conditional selection based on boolean condition

Configuration
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "calculate_metrics",
        "type": "udf_model",
        "entity_group": ["infrastructure", "road_segments"],
        "inputs": {
            "length": "geometry.length",
            "width": "geometry.width",
            "flow": "traffic.vehicle_flow"
        },
        "functions": [
            {
                "expression": "length * width",
                "output": "geometry.area"
            },
            {
                "expression": "flow / (width * 3.5)",
                "output": "traffic.lane_flow"
            }
        ]
    }

Advanced Configuration
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "complex_calculations",
        "type": "udf_model",
        "entity_group": ["network", "links"],
        "inputs": {
            "capacity": "link.capacity",
            "flow": "link.flow",
            "length": "link.length",
            "speed": "link.free_speed",
            "incidents": "link.incident_factor"
        },
        "optional": ["incidents"],
        "functions": [
            {
                "expression": "flow / capacity",
                "output": "performance.volume_capacity_ratio"
            },
            {
                "expression": "if(flow > capacity * 0.9, speed * 0.5, speed)",
                "output": "performance.congested_speed"
            },
            {
                "expression": "length / if(flow > 0, flow / capacity * speed, speed)",
                "output": "performance.travel_time"
            },
            {
                "expression": "capacity * default(incidents, 1)",
                "output": "performance.effective_capacity"
            }
        ]
    }

Configuration Schema
^^^^^^^^^^^^^^^^^^^^

.. list-table:: Configuration Parameters
   :header-rows: 1
   :widths: 20 15 15 50

   * - Parameter
     - Type
     - Required
     - Description
   * - ``entity_group``
     - array
     - Yes
     - Array of [dataset_name, entity_group_name]
   * - ``inputs``
     - object
     - Yes
     - Input attribute mappings
   * - ``inputs.<name>``
     - string
     - Yes
     - Maps variable name to attribute
   * - ``optional``
     - array
     - No
     - List of optional input names from inputs dict
   * - ``functions``
     - array
     - Yes
     - List of calculations
   * - ``functions[].expression``
     - string
     - Yes
     - Mathematical expression
   * - ``functions[].output``
     - string
     - Yes
     - Output attribute name

Expression Syntax
-----------------

Basic Expressions
^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Simple arithmetic
    "a + b"
    "a * b - c"
    "(a + b) / c"

    # Using built-in functions
    "sum(values)"
    "max(a, b, c)"
    "min(a, b)"
    "default(optional_value, 0)"

Conditional Expressions
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # if(condition, true_value, false_value)
    "if(flow > capacity, 1, 0)"
    "if(speed < 30, speed * 0.5, speed)"

    # Nested conditions
    "if(a > b, if(a > c, a, c), if(b > c, b, c))"
    
    # Using default for optional values
    "default(optional_factor, 1) * value"

Array Operations
^^^^^^^^^^^^^^^^

.. code-block:: python

    # Element-wise operations
    "array1 + array2"
    "array * scalar"
    
    # Aggregations
    "sum(array)"  # Row-wise sum
    "max(array1, array2)"  # Element-wise maximum
    "min(array1, array2)"  # Element-wise minimum

Examples
--------

Traffic Flow Metrics
^^^^^^^^^^^^^^^^^^^^

Calculating traffic performance indicators:

.. code-block:: json

    {
        "name": "traffic_metrics",
        "type": "udf_model",
        "entity_group": ["road_network", "segments"],
        "inputs": {
            "volume": "traffic.hourly_volume",
            "capacity": "road.capacity",
            "length": "road.length_km",
            "lanes": "road.num_lanes"
        },
        "functions": [
            {
                "expression": "volume / capacity",
                "output": "performance.v_c_ratio"
            },
            {
                "expression": "volume / lanes",
                "output": "performance.lane_volume"
            },
            {
                "expression": "volume * length",
                "output": "performance.vkt"
            },
            {
                "expression": "if(volume/capacity > 0.8, 1, 0)",
                "output": "performance.congested"
            }
        ]
    }

Environmental Calculations
^^^^^^^^^^^^^^^^^^^^^^^^^^

Computing environmental impact metrics:

.. code-block:: json

    {
        "name": "environmental_impact",
        "type": "udf_model",
        "entity_group": ["infrastructure", "assets"],
        "inputs": {
            "elevation": "terrain.elevation",
            "flood_level": "hazard.flood_depth",
            "value": "asset.monetary_value",
            "vulnerability": "asset.vulnerability_factor"
        },
        "functions": [
            {
                "expression": "flood_level - elevation",
                "output": "hazard.inundation_depth"
            },
            {
                "expression": "if(flood_level > elevation, 1, 0)",
                "output": "hazard.is_flooded"
            },
            {
                "expression": "if(flood_level > elevation, value * vulnerability * (flood_level - elevation) / 2, 0)",
                "output": "risk.damage_cost"
            }
        ]
    }

Simple Metrics Example
^^^^^^^^^^^^^^^^^^^^^^

Computing derived metrics:

.. code-block:: json

    {
        "name": "simple_metrics",
        "type": "udf_model",
        "entity_group": ["projects", "assets"],
        "inputs": {
            "length": "geometry.length",
            "width": "geometry.width",
            "cost_per_sqm": "economics.unit_cost",
            "maintenance_factor": "economics.maintenance_factor"
        },
        "functions": [
            {
                "expression": "length * width",
                "output": "geometry.area"
            },
            {
                "expression": "length * width * cost_per_sqm",
                "output": "economics.total_cost"
            },
            {
                "expression": "length * width * cost_per_sqm * maintenance_factor",
                "output": "economics.maintenance_cost"
            }
        ]
    }

Performance Considerations
--------------------------

Expression Optimization
^^^^^^^^^^^^^^^^^^^^^^^

The compiler optimizes expressions by:

- Common subexpression elimination
- Constant folding
- Dead code removal
- Type-specific operations

.. code-block:: python

    # Original expression
    "(a + b) * c + (a + b) * d"

    # Optimized (common subexpression)
    temp = a + b
    result = temp * c + temp * d

Memory Management
^^^^^^^^^^^^^^^^^

- Reuse intermediate arrays
- In-place operations where possible
- Lazy evaluation for conditionals
- Efficient CSR operations

Computational Efficiency
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Operation Type
     - Relative Cost
     - Optimization Tips
   * - Basic arithmetic
     - Low
     - Vectorize, avoid loops
   * - Conditional (if)
     - Medium
     - Minimize branches
   * - Array aggregation
     - High
     - Cache results when possible

Best Practices
--------------

Expression Design
^^^^^^^^^^^^^^^^^

- Keep expressions readable
- Use meaningful variable names
- Avoid deeply nested conditions
- Document complex formulas

Error Handling
^^^^^^^^^^^^^^

- Check for division by zero
- Handle missing optional inputs
- Validate output ranges
- Use appropriate defaults

.. code-block:: python

    # Safe division
    "if(denominator != 0, numerator / denominator, 0)"

    # Bounds checking
    "max(0, min(100, calculated_value))"

    # Handle optional inputs with default
    "default(optional_value, 1) * base_value"

Testing Expressions
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Test with sample data
    test_inputs = {
        "a": [1, 2, 3],
        "b": [4, 5, 6]
    }

    expression = "a + b"
    expected = [5, 7, 9]

    # Another example with functions
    expression2 = "max(a, b)"  
    expected2 = [4, 5, 6]

Common Issues and Troubleshooting
----------------------------------

Syntax Errors
^^^^^^^^^^^^^

**Issue**: Expression parsing fails

**Solutions**:

- Check parenthesis matching
- Verify function names
- Ensure operators are valid
- Use quotes for string literals

Type Mismatches
^^^^^^^^^^^^^^^

**Issue**: Incompatible operand types

**Solutions**:

- Verify input attribute types
- Cast if necessary
- Check array vs scalar operations
- Ensure consistent dimensions

Division by Zero
^^^^^^^^^^^^^^^^

**Issue**: Runtime error on division

**Solutions**:

- Add conditional checks
- Use if() for safe division
- Provide default values
- Validate input ranges

Performance Issues
^^^^^^^^^^^^^^^^^^

**Issue**: Slow calculation execution

**Solutions**:

- Simplify complex expressions
- Pre-compute constants
- Reduce conditional branches
- Consider splitting calculations

Integration with Other Models
-----------------------------

The UDF model integrates with:

- **All Data Models**: Process any attribute data
- **Data Collector**: Store calculated results
- **Traffic Models**: Custom traffic metrics
- **Environmental Models**: Risk calculations

Advanced Usage
--------------

Custom Function Implementation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To extend the UDF model with additional functions, you can add them to the functions dictionary:

.. code-block:: python

    from movici_simulation_core.models.udf_model.functions import func
    
    @func("custom_function")
    def my_custom_function(arr):
        """Custom function implementation"""
        # Your implementation here
        return result

Multi-Step Calculations
^^^^^^^^^^^^^^^^^^^^^^^^

Chain calculations for complex workflows:

.. code-block:: json

    {
        "functions": [
            {
                "expression": "raw_value * calibration_factor",
                "output": "step1.calibrated"
            },
            {
                "expression": "step1.calibrated + baseline",
                "output": "step2.adjusted"
            },
            {
                "expression": "if(step2.adjusted > threshold, step2.adjusted * penalty, step2.adjusted)",
                "output": "final.result"
            }
        ]
    }

Validation Rules
^^^^^^^^^^^^^^^^

Implement data quality checks:

.. code-block:: json

    {
        "functions": [
            {
                "expression": "if(value >= min_valid, if(value <= max_valid, 1, 0), 0)",
                "output": "quality.is_valid"
            },
            {
                "expression": "if(quality.is_valid, value, default_value)",
                "output": "quality.cleaned_value"
            }
        ]
    }

See Also
--------

- :doc:`data_collector` - Store UDF results
- :doc:`unit_conversions` - Predefined conversions
- :doc:`traffic_kpi` - Traffic-specific calculations
- Creating Models Guide - For complex logic

API Reference
-------------

- :class:`movici_simulation_core.models.udf_model.UDFModel`
- :mod:`movici_simulation_core.models.udf_model.compiler`
- :mod:`movici_simulation_core.models.udf_model.functions`
