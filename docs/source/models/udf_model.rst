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
- **Math functions**: Comprehensive mathematical operations
- **Array support**: Both uniform and CSR array handling
- **Type flexibility**: Automatic type inference and conversion
- **Multiple outputs**: Calculate multiple attributes in one pass
- **Optional inputs**: Handle missing or optional data gracefully

Supported Operations
--------------------

Mathematical Functions
^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - Category
     - Functions
     - Description
   * - Basic
     - ``+, -, *, /, **, %``
     - Arithmetic operations
   * - Comparison
     - ``<, <=, >, >=, ==, !=``
     - Logical comparisons
   * - Trigonometric
     - ``sin, cos, tan, asin, acos, atan``
     - Trigonometric functions
   * - Exponential
     - ``exp, log, log10, sqrt, pow``
     - Exponential and logarithmic
   * - Rounding
     - ``floor, ceil, round, abs``
     - Rounding and absolute value
   * - Statistical
     - ``min, max, mean, sum``
     - Array aggregation functions
   * - Conditional
     - ``where, if_else``
     - Conditional operations

Configuration
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "calculate_metrics",
        "type": "udf_model",
        "entity_group": {
            "dataset": "infrastructure",
            "entity": "road_segments"
        },
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
        "entity_group": {
            "dataset": "network",
            "entity": "links"
        },
        "inputs": {
            "capacity": "link.capacity",
            "flow": "link.flow",
            "length": "link.length",
            "speed": "link.free_speed"
        },
        "optional": {
            "incidents": "link.incident_factor"
        },
        "functions": [
            {
                "expression": "flow / capacity",
                "output": "performance.volume_capacity_ratio"
            },
            {
                "expression": "where(flow > capacity * 0.9, speed * 0.5, speed)",
                "output": "performance.congested_speed"
            },
            {
                "expression": "length / where(flow > 0, flow / capacity * speed, speed)",
                "output": "performance.travel_time"
            },
            {
                "expression": "if_else(incidents > 0, capacity * incidents, capacity)",
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
     - object
     - Yes
     - Target entity group specification
   * - ``entity_group.dataset``
     - string
     - Yes
     - Dataset containing entities
   * - ``entity_group.entity``
     - string
     - Yes
     - Entity group name
   * - ``inputs``
     - object
     - Yes
     - Input attribute mappings
   * - ``inputs.<name>``
     - string
     - Yes
     - Maps variable name to attribute
   * - ``optional``
     - object
     - No
     - Optional input mappings
   * - ``optional.<name>``
     - string
     - No
     - Optional attribute (defaults to 0 if missing)
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
    "a ** 2 + b ** 2"

    # Mathematical functions
    "sqrt(a ** 2 + b ** 2)"
    "sin(angle) * radius"
    "log(value) / log(10)"
    "exp(-distance / decay_factor)"

Conditional Expressions
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # where(condition, true_value, false_value)
    "where(flow > capacity, 1, 0)"
    "where(speed < 30, speed * 0.5, speed)"

    # if_else for optional values
    "if_else(optional_factor > 0, value * optional_factor, value)"

    # Nested conditions
    "where(a > b, where(a > c, a, c), where(b > c, b, c))"

Array Operations
^^^^^^^^^^^^^^^^

.. code-block:: python

    # Element-wise operations
    "array1 + array2"
    "array * scalar"

    # Aggregations (if supported)
    "sum(array)"
    "mean(array)"
    "max(array1, array2)"

Examples
--------

Traffic Flow Metrics
^^^^^^^^^^^^^^^^^^^^

Calculating traffic performance indicators:

.. code-block:: json

    {
        "name": "traffic_metrics",
        "type": "udf_model",
        "entity_group": {
            "dataset": "road_network",
            "entity": "segments"
        },
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
                "expression": "where(volume/capacity > 0.8, 1, 0)",
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
        "entity_group": {
            "dataset": "infrastructure",
            "entity": "assets"
        },
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
                "expression": "where(flood_level > elevation, 1, 0)",
                "output": "hazard.is_flooded"
            },
            {
                "expression": "where(flood_level > elevation, value * vulnerability * (flood_level - elevation) / 2, 0)",
                "output": "risk.damage_cost"
            }
        ]
    }

Economic Indicators
^^^^^^^^^^^^^^^^^^^

Financial and economic calculations:

.. code-block:: json

    {
        "name": "economic_indicators",
        "type": "udf_model",
        "entity_group": {
            "dataset": "projects",
            "entity": "investments"
        },
        "inputs": {
            "cost": "project.capital_cost",
            "benefit": "project.annual_benefit",
            "lifetime": "project.years",
            "rate": "economics.discount_rate"
        },
        "functions": [
            {
                "expression": "benefit / cost",
                "output": "economics.benefit_cost_ratio"
            },
            {
                "expression": "benefit * ((1 - (1 + rate) ** (-lifetime)) / rate)",
                "output": "economics.present_value"
            },
            {
                "expression": "benefit * ((1 - (1 + rate) ** (-lifetime)) / rate) - cost",
                "output": "economics.net_present_value"
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
    "sqrt(a*a + b*b) + sqrt(a*a + b*b) * 2"

    # Optimized (common subexpression)
    temp = sqrt(a*a + b*b)
    result = temp + temp * 2

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
   * - Trigonometric
     - Medium
     - Pre-compute if possible
   * - Conditional
     - Medium
     - Minimize branches
   * - Array aggregation
     - High
     - Cache results

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
    "where(denominator != 0, numerator / denominator, 0)"

    # Bounds checking
    "max(0, min(100, calculated_value))"

    # Handle optional inputs
    "if_else(optional > 0, value * optional, value)"

Testing Expressions
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Test with sample data
    test_inputs = {
        "a": [1, 2, 3],
        "b": [4, 5, 6]
    }

    expression = "sqrt(a**2 + b**2)"
    expected = [4.12, 5.39, 6.71]

    # Validate results
    assert all(abs(result - expect) < 0.01
              for result, expect in zip(calculated, expected))

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
- Use where() for safe division
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

Custom Function Library
^^^^^^^^^^^^^^^^^^^^^^^

Extend with domain-specific functions:

.. code-block:: python

    # Register custom functions
    def haversine_distance(lat1, lon1, lat2, lon2):
        """Calculate great circle distance"""
        R = 6371  # Earth radius in km
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c

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
                "expression": "where(step2.adjusted > threshold, step2.adjusted * penalty, step2.adjusted)",
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
                "expression": "where(value >= min_valid and value <= max_valid, 1, 0)",
                "output": "quality.is_valid"
            },
            {
                "expression": "where(quality.is_valid, value, default_value)",
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
