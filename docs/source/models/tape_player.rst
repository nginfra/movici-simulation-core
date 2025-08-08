Tape Player Model
=================

The Tape Player model replays pre-recorded simulation data from JSON or MessagePack files, enabling reproducible scenarios, testing with historical data, and integration of external simulation results. It acts as a time-series data source that injects recorded state changes at precise timestamps.

Overview
--------

The Tape Player model is essential for:

- Replaying recorded simulation runs
- Testing with historical data sequences
- Integrating external model outputs
- Creating reproducible test scenarios
- Debugging complex simulation behaviors
- Benchmarking model performance

It supports efficient data formats and can handle large-scale time-series data with minimal memory overhead.

Key Features
------------

- **Format flexibility**: Supports JSON and MessagePack formats
- **Time synchronization**: Precise timestamp-based playback
- **Dynamic attributes**: Automatically registers attributes from data
- **Efficient loading**: Lazy loading and caching mechanisms
- **Batch updates**: Processes multiple attributes simultaneously
- **Compression support**: Works with compressed MessagePack files

Configuration
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "historical_replay",
        "type": "tape_player",
        "tabular": "recorded_simulation_2023"
    }

Multiple Dataset Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "multi_source_replay",
        "type": "tape_player",
        "tabular": ["weather_data", "traffic_patterns", "incident_log"]
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
   * - ``tabular``
     - string or array
     - Yes
     - Dataset name(s) containing recorded data

Data Format
-----------

JSON Format
^^^^^^^^^^^

Structure for JSON tape files:

.. code-block:: json

    {
        "timestamps": [0, 3600, 7200, 10800],
        "entities": {
            "roads": {
                "traffic_flow": [
                    [100, 150, 120, 90],
                    [200, 250, 220, 180],
                    [150, 180, 160, 140],
                    [120, 140, 130, 110]
                ],
                "average_speed": [
                    [80, 75, 78, 82],
                    [70, 65, 68, 72],
                    [75, 70, 73, 77],
                    [85, 80, 83, 87]
                ]
            },
            "intersections": {
                "queue_length": [
                    [5, 8, 6, 4],
                    [10, 15, 12, 8],
                    [7, 10, 8, 6],
                    [3, 5, 4, 2]
                ]
            }
        }
    }

MessagePack Format
^^^^^^^^^^^^^^^^^^

Binary format with same structure as JSON but more efficient:

.. code-block:: python

    import msgpack
    
    data = {
        "timestamps": [0, 3600, 7200, 10800],
        "entities": {
            "entity_group": {
                "attribute_name": [
                    # Time series data
                ]
            }
        }
    }
    
    # Save as MessagePack
    with open("recording.msgpack", "wb") as f:
        msgpack.pack(data, f)

Data Requirements
-----------------

Input File Structure
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``timestamps``
     - array[int]
     - Simulation timestamps in seconds
   * - ``entities``
     - object
     - Entity groups and their attributes
   * - ``entities.<group>``
     - object
     - Specific entity group data
   * - ``entities.<group>.<attr>``
     - array[array]
     - Time series data [time][entity]

Output Data
^^^^^^^^^^^

The model outputs attributes exactly as recorded in the tape file, maintaining data types and array structures.

Examples
--------

Traffic Simulation Replay
^^^^^^^^^^^^^^^^^^^^^^^^^

Replaying recorded traffic patterns:

.. code-block:: json

    {
        "name": "morning_rush_replay",
        "type": "tape_player",
        "tabular": "morning_traffic_2024_01_15"
    }

**Tape file structure:**

.. code-block:: json

    {
        "timestamps": [0, 900, 1800, 2700, 3600],
        "entities": {
            "road_segments": {
                "vehicle_count": [
                    [50, 55, 60, 65, 70],
                    [45, 50, 55, 60, 65],
                    [40, 45, 50, 55, 60]
                ],
                "occupancy_rate": [
                    [0.2, 0.25, 0.3, 0.35, 0.4],
                    [0.18, 0.23, 0.28, 0.33, 0.38],
                    [0.15, 0.2, 0.25, 0.3, 0.35]
                ]
            }
        }
    }

Weather Data Integration
^^^^^^^^^^^^^^^^^^^^^^^^

Playing weather station recordings:

.. code-block:: json

    {
        "name": "weather_replay",
        "type": "tape_player",
        "tabular": "weather_station_data"
    }

**Tape file with multiple parameters:**

.. code-block:: json

    {
        "timestamps": [0, 3600, 7200, 10800, 14400],
        "entities": {
            "weather_stations": {
                "temperature": [
                    [15.2, 16.5, 18.3, 20.1, 19.5],
                    [14.8, 16.2, 18.0, 19.8, 19.2]
                ],
                "precipitation": [
                    [0.0, 0.0, 2.1, 5.3, 3.2],
                    [0.0, 0.0, 1.8, 4.9, 2.8]
                ],
                "wind_speed": [
                    [5.5, 6.2, 8.1, 10.3, 9.5],
                    [5.2, 5.9, 7.8, 9.9, 9.1]
                ]
            }
        }
    }

Multi-Source Synchronization
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Combining multiple tape sources:

.. code-block:: json

    {
        "name": "integrated_replay",
        "type": "tape_player",
        "tabular": [
            "infrastructure_status",
            "demand_patterns",
            "external_events"
        ]
    }

Creating Tape Files
-------------------

From Simulation Results
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    import json
    from movici_simulation_core import Simulation
    
    # Run simulation and collect results
    results = simulation.run()
    
    # Format as tape file
    tape_data = {
        "timestamps": results.timestamps,
        "entities": {}
    }
    
    for entity_group, attributes in results.entities.items():
        tape_data["entities"][entity_group] = {}
        for attr_name, time_series in attributes.items():
            tape_data["entities"][entity_group][attr_name] = time_series
    
    # Save as JSON
    with open("simulation_tape.json", "w") as f:
        json.dump(tape_data, f)

From External Data Sources
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    import pandas as pd
    import msgpack
    
    # Load external data
    df = pd.read_csv("sensor_data.csv")
    
    # Convert to tape format
    tape_data = {
        "timestamps": df["timestamp"].unique().tolist(),
        "entities": {
            "sensors": {}
        }
    }
    
    # Pivot data for each attribute
    for column in df.columns:
        if column != "timestamp" and column != "sensor_id":
            pivoted = df.pivot(
                index="timestamp",
                columns="sensor_id",
                values=column
            )
            tape_data["entities"]["sensors"][column] = pivoted.values.tolist()
    
    # Save as MessagePack for efficiency
    with open("sensor_tape.msgpack", "wb") as f:
        msgpack.pack(tape_data, f)

Performance Considerations
--------------------------

File Format Selection
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - Format
     - Use Case
     - Characteristics
   * - JSON
     - Development, debugging
     - Human-readable, larger files, slower parsing
   * - MessagePack
     - Production, large datasets
     - Binary, compact, fast parsing, compression support

Memory Management
^^^^^^^^^^^^^^^^^

- Lazy loading: Data loaded only when needed
- Streaming: Process timestamps sequentially
- Caching: Recently used data kept in memory
- Cleanup: Release data after playback

Optimization Strategies
^^^^^^^^^^^^^^^^^^^^^^^

- Pre-sort timestamps for sequential access
- Use appropriate data types (int vs float)
- Compress large MessagePack files
- Split very large recordings into chunks

Best Practices
--------------

Data Preparation
^^^^^^^^^^^^^^^^

- Validate timestamp monotonicity
- Ensure consistent array dimensions
- Use appropriate numerical precision
- Document data sources and units

File Management
^^^^^^^^^^^^^^^

- Use descriptive file names with dates
- Implement versioning for tape formats
- Store metadata separately if needed
- Consider compression for archival

Integration Guidelines
^^^^^^^^^^^^^^^^^^^^^^

- Synchronize with simulation clock
- Handle missing timestamps gracefully
- Validate attribute compatibility
- Document expected data ranges

Common Issues and Troubleshooting
----------------------------------

Timestamp Mismatch
^^^^^^^^^^^^^^^^^^

**Issue**: Simulation time doesn't align with tape timestamps

**Solutions**:

- Verify timestamp units (seconds vs milliseconds)
- Check simulation start time configuration
- Ensure timestamps are sorted
- Validate time step consistency

Data Dimension Errors
^^^^^^^^^^^^^^^^^^^^^

**Issue**: Array dimensions don't match entity counts

**Solutions**:

- Verify entity group sizes
- Check for added/removed entities
- Validate tape file generation process
- Ensure consistent array shapes

Format Parsing Errors
^^^^^^^^^^^^^^^^^^^^^

**Issue**: Unable to load tape file

**Solutions**:

- Verify file format (JSON vs MessagePack)
- Check for file corruption
- Validate JSON syntax
- Ensure MessagePack compatibility

Memory Overflow
^^^^^^^^^^^^^^^

**Issue**: Large tape files cause memory issues

**Solutions**:

- Use MessagePack format
- Implement chunked playback
- Reduce data precision if appropriate
- Stream data instead of full loading

Integration with Other Models
-----------------------------

The Tape Player model works with:

- **Data Collector Model**: Create tapes from simulation outputs
- **CSV Player Model**: Alternative for tabular time-series
- **NetCDF Player Model**: For gridded spatial-temporal data
- **All Analysis Models**: Provide input data for processing

Advanced Usage
--------------

Tape Manipulation
^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Merge multiple tapes
    def merge_tapes(tape1, tape2):
        merged = {
            "timestamps": sorted(set(tape1["timestamps"] + tape2["timestamps"])),
            "entities": {**tape1["entities"], **tape2["entities"]}
        }
        return merged
    
    # Filter tape by time range
    def filter_tape(tape, start_time, end_time):
        indices = [i for i, t in enumerate(tape["timestamps"])
                  if start_time <= t <= end_time]
        filtered = {
            "timestamps": [tape["timestamps"][i] for i in indices],
            "entities": {}
        }
        # Filter entity data accordingly
        return filtered

Tape Validation
^^^^^^^^^^^^^^^

.. code-block:: python

    def validate_tape(tape_data):
        # Check required fields
        assert "timestamps" in tape_data
        assert "entities" in tape_data
        
        # Verify timestamp ordering
        assert all(tape_data["timestamps"][i] <= tape_data["timestamps"][i+1]
                  for i in range(len(tape_data["timestamps"])-1))
        
        # Check data consistency
        n_times = len(tape_data["timestamps"])
        for entity_group, attributes in tape_data["entities"].items():
            for attr_name, data in attributes.items():
                assert len(data) == n_times, f"Length mismatch in {entity_group}.{attr_name}"

See Also
--------

- :doc:`data_collector` - For creating tape files
- :doc:`csv_player` - For CSV-based time series
- :doc:`netcdf_player` - For gridded data playback
- :doc:`time_window_status` - For time-based status changes

API Reference
-------------

- :class:`movici_simulation_core.models.tape_player.TapePlayerModel`