CSV Player Model
================

.. currentmodule:: movici_simulation_core.models.csv_player

Overview
--------

The CSV Player model reads time-series data from CSV files and publishes values to entity attributes at specified time points. This model is essential for injecting external time-varying data into simulations, such as sensor measurements, weather conditions, traffic demands, or any temporal data that drives the simulation.

Key Features
------------

* **Time-based playback**: Automatically advances through CSV data based on simulation time
* **Multiple parameters**: Publish multiple columns from the same CSV file to different attributes
* **Flexible entity targeting**: Assign CSV data to any entity group in the simulation
* **Automatic interpolation**: Values are held constant between time points (step function)
* **Efficient memory usage**: Only loads current values, not entire time series

Common Use Cases
----------------

* Loading measured sensor data (temperature, pollution, traffic counts)
* Injecting time-varying boundary conditions
* Playing back historical scenarios
* Providing external forcing data (weather, demand patterns)
* Testing models with synthetic time series

Configuration Schema
--------------------

.. code-block:: json

   {
     "name": "my_csv_player",
     "type": "csv_player",
     "csv_tape": "time_series_data",
     "entity_group": ["target_dataset", "target_entities"],
     "csv_parameters": [
       {
         "parameter": "column_name",
         "target_attribute": "attribute_name"
       }
     ]
   }

Configuration Parameters
------------------------

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Parameter
     - Type
     - Description
   * - ``csv_tape``
     - string
     - **Required**. Name of the CSV file dataset containing time-series data
   * - ``entity_group``
     - array[string, string]
     - **Required**. Target dataset and entity group [dataset_name, entity_name]
   * - ``csv_parameters``
     - array[object]
     - **Required**. List of parameter mappings from CSV columns to attributes

CSV Parameter Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each parameter in ``csv_parameters`` has:

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Parameter
     - Type
     - Description
   * - ``parameter``
     - string
     - **Required**. Column name in the CSV file to read values from
   * - ``target_attribute``
     - string
     - **Required**. Attribute name in target entities to write values to

CSV File Format
---------------

The CSV file must follow this structure:

.. code-block:: text

   seconds,parameter1,parameter2,parameter3
   0,10.5,20.3,100
   3600,11.2,19.8,105
   7200,12.1,18.5,110
   10800,13.5,17.2,115

Requirements:

* **Time column**: Must have a ``seconds`` column with time values in seconds
* **Sorted time**: Time values must be in ascending order
* **Numeric values**: All parameter columns must contain numeric values
* **No missing values**: Empty cells will cause errors

Data Behavior
-------------

Time Interpolation
~~~~~~~~~~~~~~~~~~

The CSV Player uses a **step function** approach:

* Values remain constant between time points
* At each time point, values jump to the new level
* No interpolation between points
* If simulation time exceeds CSV data, last values are maintained

Entity Mapping
~~~~~~~~~~~~~~

* CSV rows represent time points, not individual entities
* The same value from a CSV column is applied to ALL entities in the target group
* For entity-specific values, use multiple CSV Player instances or consider the Tape Player model

Examples
--------

Example 1: Temperature Data Playback
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CSV file ``temperature_data.csv``:

.. code-block:: text

   seconds,air_temp,ground_temp
   0,15.5,12.3
   3600,16.2,12.8
   7200,17.8,13.5
   10800,19.1,14.2

Configuration:

.. code-block:: json

   {
     "name": "temperature_player",
     "type": "csv_player",
     "csv_tape": "temperature_data",
     "entity_group": ["environment", "weather_stations"],
     "csv_parameters": [
       {
         "parameter": "air_temp",
         "target_attribute": "air_temperature"
       },
       {
         "parameter": "ground_temp",
         "target_attribute": "ground_temperature"
       }
     ]
   }

Example 2: Traffic Demand Patterns
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CSV file ``traffic_demand.csv``:

.. code-block:: text

   seconds,cars,trucks,bikes
   0,1000,200,50
   3600,1500,250,100
   7200,2500,300,200
   10800,2000,280,150
   14400,1200,220,80

Configuration:

.. code-block:: json

   {
     "name": "traffic_demand_player",
     "type": "csv_player",
     "csv_tape": "traffic_demand",
     "entity_group": ["transport", "traffic_zones"],
     "csv_parameters": [
       {
         "parameter": "cars",
         "target_attribute": "car_demand"
       },
       {
         "parameter": "trucks",
         "target_attribute": "truck_demand"
       },
       {
         "parameter": "bikes",
         "target_attribute": "bike_demand"
       }
     ]
   }

Example 3: Pollution Monitoring
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CSV file ``pollution_levels.csv``:

.. code-block:: text

   seconds,pm25,pm10,no2,o3
   0,25.5,45.2,38.1,65.3
   900,26.8,46.5,39.2,64.8
   1800,28.2,48.1,41.5,63.2
   2700,30.1,50.3,43.8,61.5

Configuration:

.. code-block:: json

   {
     "name": "pollution_player",
     "type": "csv_player",
     "csv_tape": "pollution_levels",
     "entity_group": ["monitoring", "air_quality_sensors"],
     "csv_parameters": [
       {
         "parameter": "pm25",
         "target_attribute": "pm25_concentration"
       },
       {
         "parameter": "no2",
         "target_attribute": "no2_concentration"
       }
     ]
   }

Best Practices
--------------

1. **Time Resolution**: Choose appropriate time intervals based on simulation needs
2. **Data Validation**: Verify CSV data before simulation (sorted times, valid values)
3. **Memory Efficiency**: For very long time series, consider splitting into multiple files
4. **Units Consistency**: Ensure CSV values use the same units as expected by models
5. **Missing Data**: Fill gaps in time series before using in simulation

Performance Considerations
--------------------------

* **File Loading**: CSV is loaded once during initialization
* **Memory Usage**: Entire CSV is kept in memory - consider file size
* **Update Frequency**: Model only updates when time matches a CSV time point
* **Large Files**: For files >100MB, consider using NetCDF Player instead

Common Issues and Solutions
---------------------------

**Issue**: "Parameter not found in supplied csv"
   * Check column name spelling matches exactly (case-sensitive)
   * Verify CSV file has the specified column
   * Ensure no extra spaces in column headers

**Issue**: Values not updating during simulation
   * Check time column is named "seconds"
   * Verify time values are in seconds, not other units
   * Ensure simulation time range overlaps with CSV time range

**Issue**: All entities get the same value
   * This is expected behavior - use Tape Player for entity-specific values
   * Or create multiple entity groups with separate CSV Players

Integration with Other Models
-----------------------------

The CSV Player works well with:

* **Area Aggregation**: Provide time-varying source data for aggregation
* **Traffic Assignment**: Supply time-dependent demand matrices
* **Operational Status**: Control entity states based on schedules
* **Unit Conversions**: Convert played values to different units

Comparison with Similar Models
------------------------------

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Model
     - Use Case
     - Key Difference
   * - CSV Player
     - Same value to all entities at each time
     - Simpler, time-series focused
   * - Tape Player
     - Different values per entity over time
     - Entity-specific time series
   * - NetCDF Player
     - Gridded/multidimensional data
     - Handles spatial data

See Also
--------

* :doc:`tape_player` - For entity-specific time series data
* :doc:`netcdf_player` - For gridded spatiotemporal data
* :doc:`/tutorials/data_preparation` - Preparing CSV files for simulation
* :class:`~movici_simulation_core.models.csv_player.csv_player.CSVPlayer` - API reference