Data Collector Model
====================

.. currentmodule:: movici_simulation_core.models.data_collector

Overview
--------

The Data Collector model captures and stores simulation state data at each time step, enabling post-simulation analysis, debugging, and result visualization. It acts as a passive observer that subscribes to data changes and saves them to persistent storage without affecting the simulation itself.

This model is essential for:

* **Result Analysis**: Capturing time-series data for post-processing
* **Debugging**: Recording intermediate states to diagnose issues
* **Visualization**: Providing data for creating animations or plots
* **Model Validation**: Comparing simulation outputs with expected results
* **Data Export**: Converting simulation results to standard formats

Key Features
------------

* **Selective Data Capture**: Filter which datasets and attributes to collect
* **Multiple Storage Backends**: Support for disk storage with extensible architecture
* **Concurrent Processing**: Asynchronous I/O for minimal simulation impact
* **Flexible Filtering**: Collect all data or specify detailed filters
* **Automatic Timestamping**: Each snapshot includes timestamp and iteration info
* **JSON Export**: Standard format for interoperability

Configuration Schema
--------------------

.. code-block:: json

   {
     "name": "my_data_collector",
     "type": "data_collector", 
     "gather_filter": {
       "dataset_name": {
         "entity_group": ["attribute1", "attribute2"]
       }
     },
     "aggregate_updates": false,
     "storage_dir": "/path/to/output"
   }

Configuration Parameters
------------------------

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Parameter
     - Type
     - Description
   * - ``gather_filter``
     - object/string/null
     - **Optional**. Data filter specification. Use ``"*"`` for all data, ``null`` for no filter, or object for selective filtering
   * - ``aggregate_updates``
     - boolean
     - **Optional**. If true, aggregates multiple updates within the same time step. Default: false
   * - ``storage_dir``
     - string
     - **Optional**. Directory path for storing collected data. Overrides global storage settings

Data Filtering
--------------

The ``gather_filter`` parameter controls which data is collected:

No Filter (Collect Everything)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: json

   {
     "gather_filter": "*"
   }

Selective Filtering
~~~~~~~~~~~~~~~~~~~

.. code-block:: json

   {
     "gather_filter": {
       "transport_network": {
         "road_segments": ["traffic_flow", "vehicle_speed"],
         "intersections": ["queue_length"]
       },
       "sensors": {
         "traffic_counters": ["vehicle_count"]
       }
     }
   }

Filter Structure:
   * **Dataset level**: Top-level keys are dataset names
   * **Entity group level**: Second-level keys are entity group names
   * **Attribute level**: Arrays contain attribute names to collect

Storage Behavior
----------------

File Organization
~~~~~~~~~~~~~~~~~

The Data Collector creates files with the naming pattern:

.. code-block:: text

   t{timestamp}_{iteration}_{model_name}.json

Example files:

.. code-block:: text

   output_directory/
   ├── t0_0_traffic_model.json
   ├── t3600_1_traffic_model.json
   ├── t7200_2_traffic_model.json
   └── ...

File Content Format
~~~~~~~~~~~~~~~~~~~

Each JSON file contains:

.. code-block:: json

   {
     "model_name": {
       "dataset_name": {
         "entity_group_name": {
           "attribute_name": [values...],
           "id": [entity_ids...]
         }
       }
     }
   }

Data Aggregation
~~~~~~~~~~~~~~~~

When ``aggregate_updates`` is true:
   * Multiple updates within the same timestamp are combined
   * Useful for models that update multiple times per time step
   * Reduces file count and storage requirements

Examples
--------

Example 1: Basic Traffic Data Collection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Collect all traffic-related data:

.. code-block:: json

   {
     "name": "traffic_collector",
     "type": "data_collector",
     "gather_filter": {
       "road_network": {
         "road_segments": ["traffic_flow", "occupancy", "speed"],
         "intersections": ["queue_length", "delay"]
       }
     },
     "storage_dir": "./results/traffic_analysis"
   }

Example 2: Environmental Monitoring
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Collect sensor and pollution data:

.. code-block:: json

   {
     "name": "env_collector", 
     "type": "data_collector",
     "gather_filter": {
       "sensors": {
         "air_quality": ["pm25", "pm10", "no2"],
         "weather": ["temperature", "humidity", "wind_speed"]
       },
       "pollution_model": {
         "emission_sources": ["emission_rate"],
         "monitoring_points": ["concentration"]
       }
     },
     "aggregate_updates": true,
     "storage_dir": "./results/environmental"
   }

Example 3: Complete System State
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Capture everything for debugging:

.. code-block:: json

   {
     "name": "debug_collector",
     "type": "data_collector", 
     "gather_filter": "*",
     "storage_dir": "./debug/full_state"
   }

Example 4: Minimal Energy Data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Collect only specific energy metrics:

.. code-block:: json

   {
     "name": "energy_collector",
     "type": "data_collector",
     "gather_filter": {
       "energy_system": {
         "power_plants": ["generation"],
         "substations": ["load", "voltage"],
         "transmission_lines": ["current", "losses"]
       }
     },
     "storage_dir": "./results/energy"
   }

Performance Considerations
--------------------------

I/O Performance
~~~~~~~~~~~~~~~

* **Concurrent writing**: Uses thread pool for asynchronous file operations
* **Storage impact**: Large datasets may generate significant disk I/O
* **Memory usage**: Data is serialized and written promptly to minimize memory footprint

Simulation Impact
~~~~~~~~~~~~~~~~~

* **Minimal overhead**: Data collection runs in background threads
* **No blocking**: Simulation continues while data is being written
* **Selective filtering**: Reduces overhead by collecting only needed data

Storage Requirements
~~~~~~~~~~~~~~~~~~~~

* **File count**: One file per model per time step
* **File size**: Depends on data volume and number of entities
* **Directory cleanup**: Storage directory is cleared at simulation start

Best Practices
--------------

1. **Selective Filtering**: Use specific filters to avoid collecting unnecessary data
2. **Storage Location**: Use fast storage (SSD) for large simulations
3. **Directory Management**: Use descriptive storage directory names with timestamps
4. **Data Validation**: Check collected data immediately after simulation
5. **Cleanup Strategy**: Archive or compress old results regularly

Common Issues and Solutions
---------------------------

**Issue**: "No storage_dir set" error
   * Set ``storage_dir`` in model config or global settings
   * Ensure the parent directory exists and is writable

**Issue**: Large file sizes or slow performance
   * Use more selective ``gather_filter`` to reduce data volume
   * Check available disk space and I/O performance
   * Consider increasing thread pool size for faster writing

**Issue**: Missing expected data in output files
   * Verify filter specification matches actual dataset/entity/attribute names
   * Check that models are actually publishing the expected data
   * Use ``"*"`` filter temporarily to see all available data

**Issue**: Files not created or empty output directory
   * Check directory permissions
   * Verify models are generating updates
   * Look for error messages in simulation logs

Data Processing
---------------

Post-Simulation Analysis
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import json
   import pandas as pd
   from pathlib import Path
   
   def load_time_series(data_dir, dataset, entity_group, attribute):
       """Load time series from collected data files"""
       results = []
       for file_path in sorted(Path(data_dir).glob("*.json")):
           with open(file_path) as f:
               data = json.load(f)
           
           # Extract timestamp from filename
           timestamp = int(file_path.stem.split('_')[0][1:])
           
           # Get attribute values
           values = data.get(dataset, {}).get(entity_group, {}).get(attribute, [])
           
           results.append({
               'timestamp': timestamp,
               'values': values
           })
       
       return pd.DataFrame(results)

Integration with Analysis Tools
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Pandas**: Load JSON files for time-series analysis
* **Matplotlib/Plotly**: Create visualizations from collected data
* **NumPy**: Perform numerical analysis on collected arrays
* **GeoPandas**: Analyze spatial patterns in collected geographic data

Extension Points
----------------

Custom Storage Strategies
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from movici_simulation_core.models.data_collector import StorageStrategy, DataCollector
   
   class DatabaseStorageStrategy(StorageStrategy):
       def __init__(self, connection_string):
           self.connection = connect(connection_string)
       
       @classmethod
       def choose(cls, model_config, settings, **_):
           return cls(model_config['database_url'])
       
       def store(self, info):
           # Store to database instead of files
           pass
   
   # Register the custom strategy
   DataCollector.add_storage_strategy("database", DatabaseStorageStrategy)

See Also
--------

* :doc:`/tutorials/data_preparation` - Preparing data for collection
* :doc:`/in_depth/data_masks` - Understanding data filtering
* :class:`~movici_simulation_core.models.data_collector.data_collector.DataCollector` - API reference
* :doc:`csv_player` - For playing back collected data