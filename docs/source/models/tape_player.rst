.. |required| replace:: (**required**)

Tape Player
===========

The tape player model (``"tape_player"``) replays pre-recorded time-series data
during a simulation. It reads data from tape files and publishes the recorded
attribute values at their designated timestamps.

Use cases include:

* Injecting external scenario data into a simulation
* Replaying recorded simulation results
* Providing time-varying boundary conditions

Tape File Format
----------------

Tape files must be in JSON or msgpack format with a ``data`` section containing:

* ``tabular_data_name``: Name of the target dataset to update
* ``time_series``: List of timestamps in seconds
* ``data_series``: List of data updates, one per timestamp

Example tape file structure:

.. code-block:: json

    {
        "name": "my_tapefile",
        "type": "tabular",
        "data": {
            "tabular_data_name": "road_network",
            "time_series": [0, 3600, 7200],
            "data_series": [
                {
                    "road_segment_entities": {
                        "id": [101, 102],
                        "transport.capacity": [1000, 1500]
                    }
                },
                {
                    "road_segment_entities": {
                        "id": [101, 102],
                        "transport.capacity": [900, 1400]
                    }
                },
                {
                    "road_segment_entities": {
                        "id": [101, 102],
                        "transport.capacity": [800, 1300]
                    }
                }
            ]
        }
    }

Configuration Options
---------------------

+----------+---------------+-----------------------------------------------------+
| Option   | Type          | Description                                         |
+==========+===============+=====================================================+
| tabular  | string / list | Name of the tape file dataset, or a list of names   |
+----------+---------------+-----------------------------------------------------+

Example Configuration
---------------------

Single tape file:

.. code-block:: json

    {
        "name": "scenario_player",
        "type": "tape_player",
        "tabular": "scenario_tapefile"
    }

Multiple tape files:

.. code-block:: json

    {
        "name": "scenario_player",
        "type": "tape_player",
        "tabular": ["capacity_tapefile", "demand_tapefile"]
    }

Creating Tape Files
-------------------

Tape files can be created using the preprocessing utilities:

.. code-block:: python

    from movici_simulation_core.preprocessing.tapefile import (
        InterpolatingTapefile,
        TimeDependentAttribute,
    )

    # Create tapefile from CSV with yearly data
    tapefile = InterpolatingTapefile(
        entity_data={"id": [1, 2, 3], "reference": ["e1", "e2", "e3"]},
        dataset_name="my_dataset",
        entity_group_name="my_entities",
        reference="reference",
        tapefile_name="my_tapefile",
    )

    # Add time-dependent attribute from CSV
    tapefile.add_attribute(
        TimeDependentAttribute(
            name="some_attribute",
            csv_file="yearly_values.csv",
            key="name",
        )
    )

    # Write the tapefile
    tapefile.dump("my_tapefile.json")

The CSV file should have the format:

.. code-block:: text

    name,2020,2025,2030
    e1,100,110,120
    e2,100,90,85
    e3,50,55,60

Values are linearly interpolated between defined years.

See Also
--------

* :mod:`movici_simulation_core.preprocessing.tapefile` - Tape file creation utilities

Config Schema Reference
-----------------------

TapePlayerConfig
^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``tabular``: ``string`` | ``array`` Name of the tape file dataset, or a list of names |required|
