NetCDF Player Model
===================

The NetCDF Player model reads spatiotemporal data from NetCDF files and plays it back during simulation, enabling integration of gridded environmental, meteorological, or oceanographic datasets into transport simulations. It supports temporal interpolation and efficient data streaming for large-scale scientific datasets.

Overview
--------

The NetCDF Player is essential for integrating:

- Weather and climate data (temperature, precipitation, wind)
- Environmental conditions (air quality, noise levels)
- Oceanographic data (sea levels, wave heights, currents) 
- Atmospheric data (pressure, humidity, visibility)
- Gridded model outputs from external simulations
- Satellite observation datasets
- Regional climate projections

The model handles large multidimensional datasets efficiently with lazy loading and temporal interpolation capabilities.

Key Features
------------

- **NetCDF4 compatibility**: Reads standard NetCDF files with CF conventions
- **Temporal interpolation**: Automatic time-based data interpolation
- **Lazy loading**: Memory-efficient data access for large files
- **Multiple attributes**: Map multiple NetCDF variables to entity attributes
- **Index-based mapping**: Direct mapping from NetCDF dimensions to entity indices
- **Timeline integration**: Synchronizes with simulation time progression

NetCDF File Requirements
------------------------

File Structure
^^^^^^^^^^^^^^

The NetCDF file must adhere to the following specification:

.. code-block:: text

    dimensions:
        time = N_TIMESTAMPS ;
        entity = N_ENTITIES ;
    
    variables:
        float time(time) ;
            time:units = "seconds since simulation start" ;
            time:long_name = "time" ;
        
        float variable1(time, entity) ;
            variable1:units = "appropriate_units" ;
            variable1:long_name = "descriptive name" ;
        
        float variable2(time, entity) ;
            variable2:units = "appropriate_units" ;

Required Components
^^^^^^^^^^^^^^^^^^^

1. **Time Variable**:
   
   - Must be named ``time``
   - Contains timestamps as seconds since simulation start (t=0)
   - Must be strictly monotonically increasing
   - Supports both integer and floating-point values

2. **Data Variables**:
   
   - First dimension must match the length of ``time``
   - Second dimension must match the number of target entities
   - Must be 32-bit or 64-bit floating-point data
   - Variable names correspond to ``source`` in configuration

3. **Data Types**:
   
   - Supported: ``float32``, ``float64``
   - Integer types are converted to float during processing
   - Missing values handled via NetCDF ``_FillValue`` or ``missing_value``

Configuration
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "weather_data_player",
        "type": "netcdf_player",
        "netcdf_tape": "weather_forecast_2024",
        "entity_group": ["infrastructure", "weather_stations"],
        "attributes": [
            {
                "source": "temperature",
                "target": "weather.temperature"
            },
            {
                "source": "precipitation",
                "target": "weather.rainfall"
            }
        ]
    }

Advanced Configuration
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "environmental_conditions",
        "type": "netcdf_player",
        "netcdf_tape": "regional_climate_model_output",
        "entity_group": ["environment", "monitoring_points"],
        "attributes": [
            {
                "source": "air_temperature",
                "target": "climate.temperature_celsius"
            },
            {
                "source": "relative_humidity", 
                "target": "climate.humidity_percent"
            },
            {
                "source": "wind_speed",
                "target": "climate.wind_speed_ms"
            },
            {
                "source": "surface_pressure",
                "target": "climate.pressure_hpa"
            },
            {
                "source": "visibility",
                "target": "weather.visibility_km"
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
   * - ``netcdf_tape``
     - string
     - Yes
     - Name of NetCDF dataset in simulation
   * - ``entity_group``
     - array
     - Yes
     - Target entity group: [dataset, entity_group]
   * - ``attributes``
     - array
     - Yes
     - Variable-to-attribute mappings
   * - ``attributes[].source``
     - string
     - Yes
     - NetCDF variable name
   * - ``attributes[].target``
     - string
     - Yes
     - Target entity attribute name

Data Requirements
-----------------

Input Data
^^^^^^^^^^

**NetCDF File Structure:**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Component
     - Type
     - Description
   * - Time dimension
     - float/int
     - Timestamps in seconds from simulation start
   * - Entity dimension
     - int
     - Number of target entities (must match)
   * - Data variables
     - float32/64
     - Spatiotemporal data arrays

**Entity Mapping:**

The model uses **index-based mapping** rather than ID-based mapping:

.. code-block:: python

    # NetCDF data structure
    netcdf_data[variable][time_index, entity_index] -> entity_attribute[entity_index]
    
    # Example: 100 weather stations, 48 hourly timestamps
    # NetCDF shape: temperature(48, 100)
    # Maps to: entity_group with 100 entities

Output Data
^^^^^^^^^^^

The model outputs time-interpolated values directly to target entity attributes, maintaining the original data types and units from the NetCDF file.

Examples
--------

Weather Station Network
^^^^^^^^^^^^^^^^^^^^^^^

Reading meteorological data for traffic impact analysis:

.. code-block:: json

    {
        "name": "weather_stations",
        "type": "netcdf_player", 
        "netcdf_tape": "hourly_weather_2024",
        "entity_group": ["meteorology", "weather_stations"],
        "attributes": [
            {
                "source": "temperature_2m",
                "target": "weather.air_temperature"
            },
            {
                "source": "precipitation",
                "target": "weather.hourly_precipitation"
            },
            {
                "source": "wind_speed_10m",
                "target": "weather.wind_speed"
            },
            {
                "source": "visibility",
                "target": "weather.visibility_distance"
            }
        ]
    }

**Sample NetCDF Structure:**

.. code-block:: text

    netcdf hourly_weather_2024 {
    dimensions:
        time = 8760 ;        // 365 days * 24 hours
        station = 150 ;      // 150 weather stations
    variables:
        double time(time) ;
            time:units = "seconds since 2024-01-01 00:00:00" ;
        float temperature_2m(time, station) ;
            temperature_2m:units = "degrees_Celsius" ;
        float precipitation(time, station) ;
            precipitation:units = "mm/hour" ;
        float wind_speed_10m(time, station) ;
            wind_speed_10m:units = "m/s" ;
        float visibility(time, station) ;
            visibility:units = "km" ;
    }

Air Quality Monitoring
^^^^^^^^^^^^^^^^^^^^^^

Environmental data for health impact assessment:

.. code-block:: json

    {
        "name": "air_quality_monitor",
        "type": "netcdf_player",
        "netcdf_tape": "urban_air_quality_model",
        "entity_group": ["environment", "monitoring_sites"],
        "attributes": [
            {
                "source": "no2_concentration",
                "target": "air_quality.no2_ugm3"
            },
            {
                "source": "pm25_concentration", 
                "target": "air_quality.pm25_ugm3"
            },
            {
                "source": "pm10_concentration",
                "target": "air_quality.pm10_ugm3"
            },
            {
                "source": "ozone_concentration",
                "target": "air_quality.o3_ugm3"
            }
        ]
    }

Coastal Infrastructure Monitoring
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sea level and wave data for port operations:

.. code-block:: json

    {
        "name": "coastal_conditions",
        "type": "netcdf_player",
        "netcdf_tape": "marine_forecast_model",
        "entity_group": ["coastal", "tide_gauges"],
        "attributes": [
            {
                "source": "sea_surface_height",
                "target": "marine.tide_level_m"
            },
            {
                "source": "significant_wave_height",
                "target": "marine.wave_height_m"
            },
            {
                "source": "wave_period",
                "target": "marine.wave_period_s"
            },
            {
                "source": "current_speed",
                "target": "marine.current_speed_ms"
            }
        ]
    }

Temporal Interpolation
----------------------

Algorithm Details
^^^^^^^^^^^^^^^^^

The NetCDF Player uses temporal interpolation to provide data at any simulation time:

.. code-block:: python

    def get_interpolated_data(self, current_time):
        # Find nearest time indices
        time_index = np.searchsorted(self.time_values, current_time)
        
        if time_index == 0:
            # Before first timestamp: use first value
            return self.data[:, 0]
        elif time_index >= len(self.time_values):
            # After last timestamp: use last value
            return self.data[:, -1]
        else:
            # Linear interpolation between adjacent timestamps
            t0, t1 = self.time_values[time_index-1:time_index+1]
            v0, v1 = self.data[:, time_index-1:time_index+1]
            
            weight = (current_time - t0) / (t1 - t0)
            return v0 + weight * (v1 - v0)

Interpolation Strategies
^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table:: Temporal Interpolation Methods
   :header-rows: 1
   :widths: 20 30 50

   * - Scenario
     - Method
     - Description
   * - Before first timestamp
     - Constant
     - Use first available value
   * - Between timestamps
     - Linear
     - Weighted interpolation
   * - After last timestamp
     - Constant
     - Use last available value
   * - Exact timestamp match
     - Direct
     - Use exact value

Performance Considerations
--------------------------

Memory Management
^^^^^^^^^^^^^^^^^

- **Lazy loading**: Data loaded only when first accessed
- **Caching strategy**: Entire dataset cached in memory after first load
- **Memory footprint**: Approximately 8 bytes per data point (float64)

.. code-block:: python

    # Memory estimation
    memory_mb = (n_timestamps * n_entities * n_variables * 8) / (1024 * 1024)
    
    # Example: 8760 hours, 1000 entities, 5 variables
    # Memory ≈ (8760 * 1000 * 5 * 8) / 1024²  ≈ 334 MB

Optimization Strategies
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table:: Performance Optimization
   :header-rows: 1
   :widths: 30 30 40

   * - Dataset Size
   - Strategy
   - Implementation
   * - < 100 MB
   - Full caching
   - Load entire file into memory
   * - 100 MB - 1 GB
   - Chunked loading
   - Load time slices on demand
   * - > 1 GB
   - Streaming
   - Process data in temporal chunks

File Optimization
^^^^^^^^^^^^^^^^^

**NetCDF File Preparation:**

.. code-block:: python

    import netCDF4 as nc
    import numpy as np
    
    # Create optimized NetCDF file
    with nc.Dataset('optimized_data.nc', 'w') as f:
        # Create dimensions
        f.createDimension('time', n_times)
        f.createDimension('entity', n_entities)
        
        # Create time variable
        time_var = f.createVariable('time', 'f8', ('time',))
        time_var[:] = time_values
        
        # Create data variable with chunking
        data_var = f.createVariable('temperature', 'f4', 
                                  ('time', 'entity'),
                                  chunksizes=(24, min(1000, n_entities)),
                                  compression='zlib', complevel=4)
        data_var[:] = temperature_data

Best Practices
--------------

NetCDF File Creation
^^^^^^^^^^^^^^^^^^^^

1. **Use appropriate chunk sizes**: Optimize for temporal access patterns
2. **Enable compression**: Use zlib with complevel=4 for good compression ratio
3. **Choose data types wisely**: float32 often sufficient, saves 50% memory
4. **Include metadata**: Use CF conventions for variable descriptions

.. code-block:: python

    # Optimal chunking for time-series access
    chunk_time = min(24, n_timestamps)  # Daily chunks
    chunk_entity = min(1000, n_entities)  # Reasonable spatial chunks
    chunksizes = (chunk_time, chunk_entity)

Data Validation
^^^^^^^^^^^^^^^

.. code-block:: python

    def validate_netcdf_file(filepath, expected_entities):
        with nc.Dataset(filepath, 'r') as f:
            # Check required dimensions
            assert 'time' in f.dimensions
            assert len(f.dimensions) >= 2
            
            # Validate time variable
            assert 'time' in f.variables
            time_data = f.variables['time'][:]
            assert np.all(np.diff(time_data) > 0), "Time must be monotonic"
            
            # Check entity dimension size
            entity_dim = [d for d in f.dimensions if d != 'time'][0]
            assert f.dimensions[entity_dim].size == expected_entities

Integration Guidelines
^^^^^^^^^^^^^^^^^^^^^^

- **Coordinate with data sources**: Ensure entity ordering matches NetCDF
- **Validate time ranges**: Confirm NetCDF covers full simulation period
- **Handle missing data**: Use NetCDF _FillValue conventions
- **Document data sources**: Maintain metadata about file origins

Common Issues and Troubleshooting
----------------------------------

File Loading Errors
^^^^^^^^^^^^^^^^^^^^

**Issue**: "NetCDF file not found" or "Invalid NetCDF structure"

**Solutions**:

- Verify NetCDF file exists in simulation data directory
- Check file permissions and format integrity
- Validate NetCDF structure with ``ncdump -h filename.nc``
- Ensure required variables and dimensions are present

Dimension Mismatches
^^^^^^^^^^^^^^^^^^^^

**Issue**: "Entity dimension size mismatch"

**Solutions**:

- Confirm NetCDF entity dimension matches target entity group size
- Check entity ordering between NetCDF and simulation
- Verify no missing or extra entities in either dataset
- Use ``ncdump -v variable filename.nc`` to inspect data structure

Memory Issues
^^^^^^^^^^^^^

**Issue**: Out of memory with large NetCDF files

**Solutions**:

- Reduce temporal resolution if possible
- Use float32 instead of float64 precision
- Implement chunked loading for very large files
- Consider splitting large files into smaller time periods

Interpolation Problems
^^^^^^^^^^^^^^^^^^^^^^

**Issue**: Unexpected data values or interpolation artifacts

**Solutions**:

- Check for missing or NaN values in NetCDF data
- Verify time variable units and reference time
- Ensure sufficient temporal resolution for smooth interpolation
- Validate data ranges are physically reasonable

Integration with Other Models
-----------------------------

The NetCDF Player integrates effectively with:

- **Operational Status Model**: Environmental conditions for infrastructure status
- **Traffic KPI Model**: Weather effects on emissions and energy consumption
- **Area Aggregation Model**: Spatial averaging of environmental data
- **Data Collector Model**: Store processed environmental data

Advanced Features
-----------------

Custom Time Units
^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Handle different time reference systems
    def convert_time_units(netcdf_time, reference_time):
        """Convert NetCDF time to simulation time"""
        if netcdf_time.units.startswith("days since"):
            return netcdf_time[:] * 86400  # Convert days to seconds
        elif netcdf_time.units.startswith("hours since"):
            return netcdf_time[:] * 3600   # Convert hours to seconds
        else:
            return netcdf_time[:]  # Assume seconds

Multi-File Support
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Handle time-series spanning multiple files
    def load_multi_file_dataset(file_pattern, time_range):
        """Load data from multiple NetCDF files"""
        files = sorted(glob.glob(file_pattern))
        combined_data = []
        combined_time = []
        
        for file in files:
            with nc.Dataset(file) as f:
                file_time = f.variables['time'][:]
                # Filter by time range and combine
                mask = (file_time >= time_range[0]) & (file_time <= time_range[1])
                if np.any(mask):
                    combined_time.extend(file_time[mask])
                    combined_data.append(f.variables['data'][mask, :])
        
        return np.concatenate(combined_data, axis=0), np.array(combined_time)

Quality Control
^^^^^^^^^^^^^^^

.. code-block:: python

    def quality_control_checks(data, variable_name):
        """Perform basic QC on NetCDF data"""
        # Range checks
        if variable_name == 'temperature':
            valid_range = (-50, 60)  # Celsius
        elif variable_name == 'precipitation':
            valid_range = (0, 500)   # mm/h
        
        mask = (data >= valid_range[0]) & (data <= valid_range[1])
        if not np.all(mask):
            warnings.warn(f"Data outside valid range for {variable_name}")
            
        # Missing value detection
        if np.any(np.isnan(data)):
            print(f"Found {np.sum(np.isnan(data))} missing values")

See Also
--------

- :doc:`csv_player` - For tabular time-series data
- :doc:`tape_player` - For recorded simulation data
- :doc:`operational_status` - For environmental impact modeling
- :doc:`data_collector` - For storing processed environmental data

API Reference
-------------

- :class:`movici_simulation_core.models.netcdf_player.NetCDFPlayer`