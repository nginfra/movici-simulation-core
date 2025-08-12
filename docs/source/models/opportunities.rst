Opportunities Model
===================

The Opportunities model tracks and analyzes economic opportunities in infrastructure projects by monitoring which opportunities are taken versus missed based on overlap status and activity states. It calculates associated costs and impacts, providing crucial metrics for investment decision-making and project prioritization.

Overview
--------

This model evaluates opportunity costs in scenarios where:

- Infrastructure improvements create economic opportunities
- Overlapping projects affect opportunity realization
- Time-sensitive opportunities may be missed
- Cost-benefit analysis drives decision-making

The model is essential for:

- Investment portfolio optimization
- Project prioritization analysis
- Economic impact assessment
- Opportunity cost calculation
- Resource allocation planning

Key Features
------------

- **Opportunity tracking**: Monitors taken vs missed opportunities
- **Cost calculation**: Computes opportunity and missed opportunity costs
- **Overlap integration**: Links opportunities to geometric overlaps
- **Length-based costing**: Calculates costs based on affected infrastructure length
- **Real-time updates**: Responds to changing overlap status

Configuration
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "infrastructure_opportunities",
        "type": "opportunities",
        "overlap_dataset": "infrastructure_overlaps",
        "opportunity_taken_property": "opportunity.is_taken",
        "total_length_property": "opportunity.affected_length",
        "opportunity_entity": "road_segments",
        "cost_per_meter": 1500.0
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
   * - ``overlap_dataset``
     - string
     - Yes
     - Dataset containing overlap information
   * - ``opportunity_taken_property``
     - string
     - Yes
     - Boolean attribute indicating if opportunity was taken
   * - ``total_length_property``
     - string
     - Yes
     - Output attribute for total affected length
   * - ``opportunity_entity``
     - string
     - Yes
     - Target entity group for opportunity analysis
   * - ``cost_per_meter``
     - float
     - Yes
     - Cost multiplier per meter of infrastructure

Data Requirements
-----------------

Input Data
^^^^^^^^^^

**Overlap Dataset:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``overlap.active``
     - array[bool]
     - Whether each overlap is currently active
   * - ``overlap.entity_ids``
     - array[int]
     - IDs of entities involved in overlaps

**Opportunity Entities:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``opportunity.is_taken``
     - array[bool]
     - Whether opportunity was taken
   * - ``geometry.length``
     - array[float]
     - Length of infrastructure segments (meters)

Output Data
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - ``opportunity.cost``
     - array[float]
     - Cost of taken opportunities
   * - ``opportunity.missed_cost``
     - array[float]
     - Cost of missed opportunities
   * - ``opportunity.affected_length``
     - array[float]
     - Total length affected by opportunities
   * - ``opportunity.total_value``
     - array[float]
     - Combined value of all opportunities

Examples
--------

Road Network Upgrade Opportunities
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Analyzing opportunities for road network improvements:

.. code-block:: json

    {
        "name": "road_upgrade_opportunities",
        "type": "opportunities",
        "overlap_dataset": "road_project_overlaps",
        "opportunity_taken_property": "upgrade.implemented",
        "total_length_property": "upgrade.total_length",
        "opportunity_entity": "road_segments",
        "cost_per_meter": 2000.0
    }

**Analysis Scenario:**

.. code-block:: python

    # Input data
    road_segments = {
        "id": [1, 2, 3, 4],
        "geometry.length": [1000, 1500, 800, 2000],  # meters
        "upgrade.implemented": [True, True, False, False]
    }

    overlaps = {
        "active": [True, True, False, True],
        "entity_ids": [1, 2, 3, 4]
    }

    # Calculations
    # Segment 1: Taken opportunity, active overlap
    #   Cost = 1000 * 2000 = 2,000,000
    # Segment 2: Taken opportunity, active overlap
    #   Cost = 1500 * 2000 = 3,000,000
    # Segment 3: Missed opportunity (not taken), inactive overlap
    #   Missed cost = 0 (overlap not active)
    # Segment 4: Missed opportunity (not taken), active overlap
    #   Missed cost = 2000 * 2000 = 4,000,000

Rail Electrification Project
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Evaluating electrification opportunities:

.. code-block:: json

    {
        "name": "rail_electrification",
        "type": "opportunities",
        "overlap_dataset": "rail_corridor_overlaps",
        "opportunity_taken_property": "electrification.completed",
        "total_length_property": "electrification.track_length",
        "opportunity_entity": "rail_tracks",
        "cost_per_meter": 5000.0
    }

Port Expansion Opportunities
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Maritime infrastructure investment analysis:

.. code-block:: json

    {
        "name": "port_expansion",
        "type": "opportunities",
        "overlap_dataset": "port_development_zones",
        "opportunity_taken_property": "expansion.executed",
        "total_length_property": "expansion.berth_length",
        "opportunity_entity": "port_berths",
        "cost_per_meter": 15000.0
    }

Algorithm Details
-----------------

The model performs opportunity analysis through:

1. **Overlap Status Check**:

   - Identifies active overlaps from overlap dataset
   - Maps overlaps to opportunity entities

2. **Opportunity Classification**:

   - **Taken**: opportunity_taken = True AND overlap_active = True
   - **Missed**: opportunity_taken = False AND overlap_active = True
   - **Inactive**: overlap_active = False (no cost impact)

3. **Cost Calculation**:

   .. code-block:: python

       if overlap_active and opportunity_taken:
           opportunity_cost = entity_length * cost_per_meter
           missed_cost = 0
       elif overlap_active and not opportunity_taken:
           opportunity_cost = 0
           missed_cost = entity_length * cost_per_meter
       else:
           opportunity_cost = 0
           missed_cost = 0

4. **Aggregation**:

   - Sum costs across all entities
   - Calculate total affected length
   - Generate summary statistics

Best Practices
--------------

Data Preparation
^^^^^^^^^^^^^^^^

- Ensure accurate infrastructure length measurements
- Verify overlap dataset completeness
- Use consistent units for lengths (typically meters)
- Validate opportunity status before analysis

Cost Modeling
^^^^^^^^^^^^^

- Research appropriate cost-per-meter values
- Consider regional cost variations
- Account for inflation in multi-year projects
- Include indirect costs where relevant

Scenario Analysis
^^^^^^^^^^^^^^^^^

- Run multiple scenarios with different opportunity selections
- Perform sensitivity analysis on cost parameters
- Compare opportunity portfolios for optimization
- Consider temporal aspects of opportunity windows

Integration Guidelines
^^^^^^^^^^^^^^^^^^^^^^

- Link with overlap_status model for geometric analysis
- Combine with financial models for NPV calculations
- Use with visualization tools for opportunity mapping
- Integrate with decision support systems

Performance Considerations
--------------------------

Optimization Strategies
^^^^^^^^^^^^^^^^^^^^^^^

- Pre-filter inactive overlaps to reduce computation
- Batch process opportunities by region or type
- Cache frequently accessed cost calculations
- Use vectorized operations for large datasets

Scalability
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Number of Opportunities
     - Processing Time
     - Recommendations
   * - < 1,000
     - < 1 second
     - Process all at once
   * - 1,000 - 10,000
     - 1-5 seconds
     - Consider batching by region
   * - > 10,000
     - > 5 seconds
     - Implement parallel processing

Common Issues and Troubleshooting
----------------------------------

Zero Opportunity Costs
^^^^^^^^^^^^^^^^^^^^^^

**Issue**: All opportunity costs calculated as zero

**Solutions**:

- Verify overlap active status is correctly set
- Check opportunity_taken boolean values
- Ensure entity lengths are non-zero
- Validate cost_per_meter is properly configured

Mismatched Overlaps
^^^^^^^^^^^^^^^^^^^

**Issue**: Overlaps don't correspond to opportunity entities

**Solutions**:

- Verify entity ID mapping between datasets
- Check overlap dataset references correct entities
- Ensure consistent entity group naming
- Validate overlap generation process

Unrealistic Cost Values
^^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Calculated costs seem too high or low

**Solutions**:

- Review cost_per_meter parameter
- Check length units (meters vs kilometers)
- Verify entity length attributes
- Consider regional cost adjustments

Integration with Other Models
-----------------------------

The Opportunities model works effectively with:

- **Overlap Status Model**: Provides geometric overlap detection
- **Unit Conversions Model**: Standardizes cost units
- **Traffic Demand Model**: Links opportunities to demand changes
- **Data Collector Model**: Stores opportunity analysis results

Economic Analysis Extensions
-----------------------------

Advanced calculations can include:

- **Net Present Value (NPV)**: Discounted future opportunity values
- **Internal Rate of Return (IRR)**: Investment efficiency metrics
- **Payback Period**: Time to recover opportunity costs
- **Risk-Adjusted Returns**: Probability-weighted opportunity values

See Also
--------

- :doc:`overlap_status` - For geometric overlap detection
- :doc:`unit_conversions` - For cost standardization
- :doc:`data_collector` - For storing analysis results
- :doc:`udf_model` - For custom opportunity calculations

API Reference
-------------

- :class:`movici_simulation_core.models.opportunities.OpportunitiesModel`
- :mod:`movici_simulation_core.models.opportunities.dataset`
