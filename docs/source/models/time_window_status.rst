Time Window Status Model
========================

The Time Window Status model manages time-based activation and deactivation of entity states, enabling scheduled operations, temporal restrictions, and time-dependent behaviors in simulations. It tracks when entities should be active based on defined time windows and updates target entity statuses accordingly.

Overview
--------

This model is essential for simulating:

- Scheduled maintenance windows
- Operating hours of facilities
- Time-restricted zones (e.g., bus lanes)
- Planned construction periods
- Seasonal service availability
- Peak/off-peak operational modes
- Event-based temporary changes

The model parses time window specifications and maintains status updates throughout the simulation timeline.

Key Features
------------

- **Flexible time formats**: Support for various time window specifications
- **Multi-target updates**: Update multiple entity groups from single source
- **Dynamic status tracking**: Real-time status changes based on simulation time
- **Batch processing**: Efficient handling of multiple time windows
- **Timeline awareness**: Respects simulation time progression
- **Status propagation**: Cascading status updates to dependent entities

Configuration
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "maintenance_windows",
        "type": "time_window_status",
        "source": {
            "dataset": "maintenance_schedule",
            "entity_group": "scheduled_maintenance",
            "time_window_begin": "maintenance.start_time",
            "time_window_end": "maintenance.end_time"
        },
        "targets": [
            {
                "dataset": "infrastructure",
                "entity_group": "road_segments",
                "status_property": "operational.under_maintenance"
            }
        ]
    }

Advanced Configuration
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "complex_scheduling",
        "type": "time_window_status",
        "source": {
            "dataset": "operations",
            "entity_group": "time_restrictions",
            "time_window_begin": "restriction.start",
            "time_window_end": "restriction.end"
        },
        "targets": [
            {
                "dataset": "transport",
                "entity_group": "bus_lanes",
                "status_property": "access.bus_only"
            },
            {
                "dataset": "transport",
                "entity_group": "loading_zones",
                "status_property": "access.loading_allowed"
            },
            {
                "dataset": "parking",
                "entity_group": "parking_spaces",
                "status_property": "availability.restricted"
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
   * - ``source``
     - object
     - Yes
     - Source configuration with time windows
   * - ``source.dataset``
     - string
     - Yes
     - Dataset containing time window data
   * - ``source.entity_group``
     - string
     - Yes
     - Entity group with time windows
   * - ``source.time_window_begin``
     - string
     - Yes
     - Attribute with window start times
   * - ``source.time_window_end``
     - string
     - Yes
     - Attribute with window end times
   * - ``targets``
     - array
     - Yes
     - List of target configurations
   * - ``targets[].dataset``
     - string
     - Yes
     - Target dataset name
   * - ``targets[].entity_group``
     - string
     - Yes
     - Target entity group
   * - ``targets[].status_property``
     - string
     - Yes
     - Status attribute to update

Data Requirements
-----------------

Input Data
^^^^^^^^^^

**Source Time Windows:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - Time window begin
     - array[string]
     - Start times (ISO format or seconds)
   * - Time window end
     - array[string]
     - End times (ISO format or seconds)
   * - ``id``
     - array[int]
     - Entity identifiers

**Time Format Examples:**

.. code-block:: python

    # Absolute timestamps (seconds since epoch)
    time_window_begin = [1609459200, 1609545600, 1609632000]
    time_window_end = [1609466400, 1609552800, 1609639200]
    
    # ISO 8601 format
    time_window_begin = [
        "2021-01-01T00:00:00Z",
        "2021-01-02T00:00:00Z",
        "2021-01-03T00:00:00Z"
    ]
    time_window_end = [
        "2021-01-01T02:00:00Z",
        "2021-01-02T02:00:00Z",
        "2021-01-03T02:00:00Z"
    ]
    
    # Relative times (seconds from simulation start)
    time_window_begin = ["0", "3600", "7200"]
    time_window_end = ["1800", "5400", "9000"]

Output Data
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Attribute
     - Type
     - Description
   * - Target status properties
     - array[bool]
     - True if within time window, False otherwise
   * - ``active_windows``
     - array[int]
     - Count of active windows per entity

Examples
--------

Bus Lane Restrictions
^^^^^^^^^^^^^^^^^^^^^

Time-based bus lane access control:

.. code-block:: json

    {
        "name": "bus_lane_hours",
        "type": "time_window_status",
        "source": {
            "dataset": "traffic_management",
            "entity_group": "bus_lane_schedules",
            "time_window_begin": "schedule.morning_start",
            "time_window_end": "schedule.evening_end"
        },
        "targets": [
            {
                "dataset": "road_network",
                "entity_group": "lanes",
                "status_property": "restriction.bus_only"
            }
        ]
    }

**Sample Schedule Data:**

.. code-block:: python

    bus_lane_schedules = {
        "id": [1, 2, 3],
        "schedule.morning_start": ["07:00:00", "06:30:00", "07:30:00"],
        "schedule.evening_end": ["19:00:00", "20:00:00", "18:30:00"]
    }

Construction Windows
^^^^^^^^^^^^^^^^^^^^

Managing construction period impacts:

.. code-block:: json

    {
        "name": "construction_periods",
        "type": "time_window_status",
        "source": {
            "dataset": "project_planning",
            "entity_group": "construction_projects",
            "time_window_begin": "project.start_date",
            "time_window_end": "project.end_date"
        },
        "targets": [
            {
                "dataset": "transport",
                "entity_group": "affected_roads",
                "status_property": "construction.active"
            },
            {
                "dataset": "transport",
                "entity_group": "detour_routes",
                "status_property": "detour.required"
            }
        ]
    }

Facility Operating Hours
^^^^^^^^^^^^^^^^^^^^^^^^

Modeling service availability:

.. code-block:: json

    {
        "name": "facility_hours",
        "type": "time_window_status",
        "source": {
            "dataset": "facilities",
            "entity_group": "service_centers",
            "time_window_begin": "hours.open",
            "time_window_end": "hours.close"
        },
        "targets": [
            {
                "dataset": "services",
                "entity_group": "service_points",
                "status_property": "availability.open"
            },
            {
                "dataset": "parking",
                "entity_group": "visitor_parking",
                "status_property": "access.allowed"
            }
        ]
    }

Algorithm Details
-----------------

The model processes time windows through:

1. **Time Window Parsing**:
   
   .. code-block:: python
   
       def parse_time_window(begin_str, end_str):
           # Convert various formats to timestamps
           if is_iso_format(begin_str):
               begin = parse_iso8601(begin_str)
           elif is_numeric(begin_str):
               begin = float(begin_str)
           else:
               begin = parse_time_expression(begin_str)
           
           # Similar for end time
           return begin, end

2. **Status Evaluation**:
   
   .. code-block:: python
   
       def evaluate_status(current_time, windows):
           for window in windows:
               if window.begin <= current_time < window.end:
                   return True
           return False

3. **Target Updates**:
   
   - Map source entities to targets
   - Apply status based on time window
   - Propagate changes to dependent systems

4. **Timeline Management**:
   
   - Track upcoming window changes
   - Schedule status updates
   - Handle overlapping windows

Time Window Specifications
--------------------------

Supported Formats
^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - Format
     - Example
     - Description
   * - Absolute seconds
     - ``1609459200``
     - Unix timestamp
   * - ISO 8601
     - ``2021-01-01T00:00:00Z``
     - Standard datetime
   * - Relative seconds
     - ``3600``
     - Seconds from simulation start
   * - Time expression
     - ``+2h30m``
     - Relative time expression

Special Cases
^^^^^^^^^^^^^

- **Open-ended windows**: Use very large end time or special value
- **Recurring windows**: Implement through multiple window entries
- **Instantaneous events**: Set begin and end to same value
- **Permanent activation**: Set window to cover entire simulation

Performance Considerations
--------------------------

Optimization Strategies
^^^^^^^^^^^^^^^^^^^^^^^

- Pre-sort windows by start time
- Index windows for binary search
- Cache active window evaluations
- Batch status updates

Scalability
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Window Count
     - Update Frequency
     - Recommendations
   * - < 100
     - Any
     - Simple iteration acceptable
   * - 100-1,000
     - High
     - Use interval trees
   * - > 1,000
     - High
     - Implement spatial-temporal indexing

Best Practices
--------------

Time Window Design
^^^^^^^^^^^^^^^^^^

- Use consistent time formats
- Account for time zone considerations
- Validate window overlaps
- Document time resolution requirements

Status Management
^^^^^^^^^^^^^^^^^

- Clear naming for status properties
- Consider status dependencies
- Implement status change logging
- Handle status conflicts appropriately

Integration Planning
^^^^^^^^^^^^^^^^^^^^

- Synchronize with simulation clock
- Consider cascade effects
- Plan for status persistence
- Design rollback capabilities

Common Issues and Troubleshooting
----------------------------------

Windows Not Activating
^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Status remains false despite being in time window

**Solutions**:

- Verify time format parsing
- Check simulation current time
- Ensure time units match (seconds vs milliseconds)
- Validate window begin < end

Incorrect Status Updates
^^^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Status changes at wrong times

**Solutions**:

- Review time zone handling
- Check for off-by-one errors
- Verify simulation time step
- Inspect window boundary conditions

Performance Degradation
^^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Slow updates with many windows

**Solutions**:

- Implement window indexing
- Cache evaluation results
- Process only changed windows
- Use efficient data structures

Integration with Other Models
-----------------------------

The Time Window Status model works with:

- **Operational Status Model**: Combine time and condition-based status
- **Overlap Status Model**: Time-dependent spatial overlaps
- **Traffic Assignment Model**: Time-varying network availability
- **Data Collector Model**: Record status change history

Advanced Features
-----------------

Complex Scheduling
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Recurring weekly schedule
    def create_weekly_schedule(day_schedules):
        windows = []
        for week in range(52):
            for day, (start, end) in day_schedules.items():
                week_offset = week * 7 * 24 * 3600
                day_offset = day * 24 * 3600
                windows.append({
                    "begin": week_offset + day_offset + start,
                    "end": week_offset + day_offset + end
                })
        return windows

Status Inheritance
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Cascade status through hierarchy
    def propagate_status(parent_status, child_entities):
        for child in child_entities:
            child.status = parent_status and child.local_condition

Conflict Resolution
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Handle overlapping windows
    def resolve_conflicts(windows, resolution_strategy="any"):
        if resolution_strategy == "any":
            return any(w.is_active for w in windows)
        elif resolution_strategy == "all":
            return all(w.is_active for w in windows)
        elif resolution_strategy == "priority":
            return max(windows, key=lambda w: w.priority).is_active

See Also
--------

- :doc:`operational_status` - For condition-based status
- :doc:`overlap_status` - For spatial status conditions
- :doc:`tape_player` - For time-series data playback
- :doc:`data_collector` - For status history recording

API Reference
-------------

- :class:`movici_simulation_core.models.time_window_status.TimeWindowStatusModel`
- :mod:`movici_simulation_core.models.time_window_status.dataset`