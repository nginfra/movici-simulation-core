.. |required| replace:: (**required**)

WNTR Drinking Water Model
==========================

The WNTR drinking water model (``"drinking_water"``) wraps the
`WNTR <https://usepa.github.io/WNTR/>`_ hydraulic simulator to provide an
idiomatic Movici interface for running drinking water network simulations.
The model processes networks containing Pipes, Junctions, Tanks, Reservoirs,
Valves and Pumps, with all data described in terms of Movici entities and
attributes.

Use cases include:

* Simulating hydraulic behavior of drinking water distribution networks
* Analyzing pressure and flow under varying demand scenarios
* Modeling transient tank filling/emptying dynamics
* Evaluating the impact of pump or valve failures on network performance

Goals
-----

* The data model is as much as possible described in terms of entities and attributes
* Data-related options (headloss formula, viscosity, etc.) are stored in the dataset's
  ``"general"`` section
* Solver-related options (trials, accuracy, etc.) are stored in the model config under
  ``"options"``
* It is a nice-to-have if the data model is compatible with other movici network tooling, such
  as the ``shortest_path`` model

Limitations
-----------

* The initial implementation does not have support for chemical reactions
* EPANET ``.inp`` files are not supported directly. External tooling can convert ``.inp`` files
  to Movici datasets
* Patterns are not included in the model. Values that change over time in a predictable
  manner (e.g. a pump rate goes to 70% at t=x) should be produced by one or more
  different models, such as a tape player

Model Characteristics
---------------------

The WNTR model is a transient state dependent model. Its output depends both on an input state that
may change over time and it has an inherent transient behaviour. Even if its input state doesn't
change, it may still change its output state. For WNTR this behaviour may stem from tanks that
may fill or empty over time. Compare this to steady state models which only change their output
state based on changes in their input state: if there are no input state changes, the output state
also doesn't change.

It also means that the output state of the model is dependent on some kind of initial state. In
case of WNTR, the tank level at :math:`t_{1}` requires a tank level at :math:`t_{0}`. In general
it can be stated that the output :math:`Y` of the model can be described as

.. math::

  Y_{t_{n+1}} = F(X_{t_{n+1}}, Y_{t_n}, t)

with:

| :math:`Y_{t_{n+1}}`: Model output state at :math:`t_{n+1}`
| :math:`F`: The calculation model, represented as a function
| :math:`X_{t_{n+1}}`: Model input state at :math:`t_{n+1}`. This is generally state calculated by
    other models
| :math:`Y_{t_n}`: Model output state at :math:`t_n`

.. warning::
  This results in a possible circular dependency where the model both subscribes and publishes to
  an attribute. While the orchestrator prevents a self-dependency, ie it will not call a model on its
  own update, even when it technically subscribes to its own data, the user must still be careful.
  When configuring a scenario containing this model, the initial state should be provided in the
  dataset and not a result of another model's calculation. At all times there must only be one
  publisher of a certain attribute in an entity group in a dataset.

Since the model can act both on internal changes and external changes, it cannot do a full run at
once. It must be able to react to changes from the outside. When it receives an outside change, it
must incorporate those changes into its internal state and then calculate from there on.

.. note:: Pause and Restart

   The WNTR simulator instance is kept alive across timesteps. Each call to ``run_sim()`` advances
   the simulation time cumulatively, preserving internal state such as tank levels. Between calls,
   the model can modify the WNTR network (e.g. changing demands or closing valves) and the next
   ``run_sim()`` picks up from where it left off. This allows external changes to be integrated
   between WNTR simulation steps.

How It Works
------------

1. At initialization, the model builds a WNTR network from the Movici entity groups
   (junctions, tanks, reservoirs, pipes, pumps, valves)
2. Data options from the dataset's ``"general"`` section and solver options from the
   model config are merged and applied to the WNTR network
3. At each simulation step, WNTR runs a hydraulic simulation with the current state
4. Any external state changes received at this timestep (e.g. demand updates, valve
   closures) are applied to the WNTR network for the next step
5. Results (pressures, heads, flows, velocities, tank levels) are written back to
   the corresponding Movici entity attributes

Data Model
----------

The drinking water network data model can be described as follows.

Junctions
^^^^^^^^^

``water_junction_entities``

Junctions are nodes in the drinking water network. They connect pipes and can be used as demand
nodes. Junctions derive from ``PointEntity``.

+----------------------------------------+-----------+---------------------------------------------------+
| Attribute                              | Flags     | Description                                       |
+========================================+===========+===================================================+
| ``geometry.x``                         | INIT      | Location x coordinate (from ``PointEntity``)      |
+----------------------------------------+-----------+---------------------------------------------------+
| ``geometry.y``                         | INIT      | Location y coordinate (from ``PointEntity``)      |
+----------------------------------------+-----------+---------------------------------------------------+
| ``geometry.z``                         | INIT      | Elevation (from ``PointEntity``)                  |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.base_demand``         | INIT      | Base demand on this node, multiplied by the       |
|                                        |           | demand factor to obtain the actual demand         |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.demand_factor``       | OPT       | Scaling factor for the demand                     |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.minimum_pressure``    | OPT       | Per-junction minimum pressure for PDD analysis.   |
|                                        |           | Overrides the global ``minimum_pressure`` from    |
|                                        |           | the dataset's ``"general"`` section. NaN values   |
|                                        |           | fall back to the global setting                   |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.required_pressure``   | OPT       | Per-junction required (nominal) pressure for PDD  |
|                                        |           | analysis. Overrides the global                    |
|                                        |           | ``required_pressure``. NaN values fall back to    |
|                                        |           | the global setting                                |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.pressure_exponent``   | OPT       | Per-junction pressure exponent for PDD analysis.  |
|                                        |           | Overrides the global ``pressure_exponent``. NaN   |
|                                        |           | values fall back to the global setting            |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.demand``              | PUB       | Effective demand (base_demand * demand_factor)    |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.pressure``            | PUB       | Dynamic pressure at the node                      |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.head``                | PUB       | Total head at the node (elevation + pressure)     |
+----------------------------------------+-----------+---------------------------------------------------+

Tanks
^^^^^

``water_tank_entities``

Tanks are buffers for drinking water. They are one of the transient elements of the drinking water
model — as a simulation progresses, tanks may fill up or empty over time. Tanks derive from
``PointEntity``.

+----------------------------------------+-----------+---------------------------------------------------+
| Attribute                              | Flags     | Description                                       |
+========================================+===========+===================================================+
| ``geometry.x``                         | INIT      | Location x coordinate (from ``PointEntity``)      |
+----------------------------------------+-----------+---------------------------------------------------+
| ``geometry.y``                         | INIT      | Location y coordinate (from ``PointEntity``)      |
+----------------------------------------+-----------+---------------------------------------------------+
| ``geometry.z``                         | INIT      | Elevation at tank bottom (from ``PointEntity``)   |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.overflow``            | OPT       | Whether a tank can overflow when full             |
|                                        |           | (max_level reached). Default: ``False``           |
+----------------------------------------+-----------+---------------------------------------------------+
| ``shape.diameter``                     | OPT       | Tank diameter for a cylindrical tank              |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.min_level``           | OPT       | Minimum level to be able to drain (Default: 0)    |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.max_level``           | INIT      | Maximum level. If a tank is overflowable, it will |
|                                        |           | overflow beyond this level                        |
+----------------------------------------+-----------+---------------------------------------------------+
| ``shape.volume_curve``                 | OPT       | Curve of (x,y) pairs defining the tank volume     |
|                                        |           | over depth. Data type shape: (2,)-csr. Used for   |
|                                        |           | non-cylindrical tanks                             |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.level``               | INIT, PUB | Water level (m) in the tank. Required as an       |
|                                        |           | initial value                                     |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.pressure``            | PUB       | Dynamic pressure in the tank                      |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.head``                | PUB       | Total head in the tank (elevation + pressure)     |
+----------------------------------------+-----------+---------------------------------------------------+

The shape and volume of the tank can either be of constant diameter for cylindrical tanks, or the
volume can be defined by a volume curve. Either is valid, so they must be ``OPT`` attributes.
If neither a diameter nor a volume curve is provided, WNTR will use default values (diameter=0).

.. note:: Tank Overflow Behavior

   If a tank is set to overflow (``drinking_water.overflow = True``), water added when at max_level
   is lost (spilled). If overflow is ``False`` and the tank reaches max_level, the connected pipe
   flows and pump operations are constrained — the network will find a new equilibrium where
   inflow matches outflow, potentially causing backpressure or pump shutoffs.

.. note:: Tank Level vs Volume Attributes

   WNTR uses ``min_level`` and ``max_level`` for all tank types. For volume curve tanks,
   ``min_vol`` can also be specified and WNTR will derive the corresponding min_level from
   the curve. The ``max_level`` is always used as the upper bound. If both ``min_vol`` and
   ``min_level`` are specified, the higher effective level takes precedence.

Reservoirs
^^^^^^^^^^

``water_reservoir_entities``

A reservoir is a tank that never empties. It has a fixed head (which can change by varying the
head factor). Reservoirs derive from ``PointEntity``.

+----------------------------------------+-----------+---------------------------------------------------+
| Attribute                              | Flags     | Description                                       |
+========================================+===========+===================================================+
| ``geometry.x``                         | INIT      | Location x coordinate (from ``PointEntity``)      |
+----------------------------------------+-----------+---------------------------------------------------+
| ``geometry.y``                         | INIT      | Location y coordinate (from ``PointEntity``)      |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.base_head``           | INIT      | Base head of the reservoir                        |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.head_factor``         | OPT       | Head multiplier (Default: 1)                      |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.head``                | PUB       | Calculated as base_head * head_factor             |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.pressure``            | PUB       | Dynamic pressure at the reservoir                 |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.demand``              | PUB       | Demand at the reservoir                           |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.flow``                | PUB       | Total flow rate out of the reservoir              |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.flow_rate.magnitude`` | PUB       | Absolute flow rate                                |
+----------------------------------------+-----------+---------------------------------------------------+

.. note::
   Reservoirs are not calculated using an elevation, so ``geometry.z`` is not used.

.. note:: Reservoirs as Sources and Drains

   Reservoirs can act as both sources (water flows out) and drains (water flows in),
   depending on the hydraulic conditions. A reservoir with lower head than connected nodes will
   act as a drain. Reservoirs can connect directly to pipes — no pump is required. Flow direction
   is determined by head differences.

Pipes
^^^^^

``water_pipe_entities``

Pipes are links that transport water from one node (Junction, Tank, Reservoir) at a high head to
another node at a lower head and experience a pressure drop (head loss) while doing so. Pipes
derive from ``LinkEntity``.

+----------------------------------------+-----------+---------------------------------------------------+
| Attribute                              | Flags     | Description                                       |
+========================================+===========+===================================================+
| ``topology.from_node_id``              | INIT      | Node id on the from side (from ``LinkEntity``)    |
+----------------------------------------+-----------+---------------------------------------------------+
| ``topology.to_node_id``                | INIT      | Node id on the to side (from ``LinkEntity``)      |
+----------------------------------------+-----------+---------------------------------------------------+
| ``shape.diameter``                     | INIT      | Pipe diameter                                     |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.roughness``           | INIT      | Pipe roughness coefficient (Hazen-Williams        |
|                                        |           | C-factor). Typical range 100-150. Higher values   |
|                                        |           | indicate smoother pipes                           |
+----------------------------------------+-----------+---------------------------------------------------+
| ``shape.length``                       | OPT       | Pipe length (Default: 100 m)                      |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.minor_loss``          | OPT       | Minor loss coefficient (Default: 0). Additional   |
|                                        |           | head loss from curves and bends, proportional to  |
|                                        |           | flow velocity squared                             |
+----------------------------------------+-----------+---------------------------------------------------+
| ``operational.status``                 | OPT       | Whether the pipe is open (``True``) or closed     |
|                                        |           | (``False``)                                       |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.check_valve``         | OPT       | Restricts flow to from_node → to_node direction   |
|                                        |           | only. Default: ``False``                          |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.flow``                | PUB       | Water flow rate through the pipe                  |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.flow_rate.magnitude`` | PUB       | Absolute flow rate                                |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.velocity``            | PUB       | Water velocity (always positive, use flow sign    |
|                                        |           | for direction)                                    |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.link_status``         | PUB       | WNTR link status (0=Closed, 1=Open, 2=Active,    |
|                                        |           | 3=CV)                                             |
+----------------------------------------+-----------+---------------------------------------------------+

.. note:: The dataset's ``"general"`` section stores data-related WNTR hydraulic options
   (headloss formula, viscosity, specific gravity, demand model, etc.). These are read from
   ``TrackedState`` during initialization and applied to the WNTR network via
   ``NetworkWrapper.configure_options()``. See the Configuration Options section below for the
   full split between dataset general and model config.

.. note:: Check Valve Direction

   Flow direction is indicated by the sign of flow (positive = from_node to to_node, negative =
   to_node to from_node). Velocity is always positive (absolute value of flow divided by pipe area).
   Check valves (``drinking_water.check_valve = True``) restrict flow to the from_node → to_node
   direction only. Reverse flow (from to_node back to from_node) is prevented.

Pumps
^^^^^

``water_pump_entities``

Pumps are links in the network. They have a direction and pump water (increase the head) from one
node (reservoir, tank, junction) to another. Pumps derive from ``LinkEntity``.

+----------------------------------------+-----------+---------------------------------------------------+
| Attribute                              | Flags     | Description                                       |
+========================================+===========+===================================================+
| ``topology.from_node_id``              | INIT      | Node id on the from side (from ``LinkEntity``)    |
+----------------------------------------+-----------+---------------------------------------------------+
| ``topology.to_node_id``                | INIT      | Node id on the to side (from ``LinkEntity``)      |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.pump_type``           | INIT      | Pump type: ``power`` or ``head``                  |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.power``               | OPT       | Fixed power for a ``power`` pump. Required for    |
|                                        |           | power pumps                                       |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.head_curve``          | OPT       | Head/flow curve for a ``head`` pump as (x,y)      |
|                                        |           | pairs. Data type shape: (2,)-csr. Required for    |
|                                        |           | head pumps                                        |
+----------------------------------------+-----------+---------------------------------------------------+
| ``operational.status``                 | OPT       | Whether the pump is open (``True``) or closed     |
|                                        |           | (``False``). Default: ``True``                    |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.flow``                | PUB       | Pump flow rate                                    |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.flow_rate.magnitude`` | PUB       | Absolute flow rate                                |
+----------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.link_status``         | PUB       | WNTR link status (0=Closed, 1=Open, 2=Active,    |
|                                        |           | 3=CV)                                             |
+----------------------------------------+-----------+---------------------------------------------------+

.. note:: Pump Status

   We model pump status as a boolean (``operational.status``): ``True`` = open/active, ``False`` = closed.
   The WNTR "active" status (open with specific speed) is handled by combining ``operational.status = True``
   with a ``drinking_water.speed`` value. This simplifies the interface while maintaining full functionality.

.. note:: Pump power / speed

   ``power`` pumps can operate at a fixed power, although this power can be updated during a simulation.
   ``head`` pumps can only be turned on or off. When on, they operate according to their head curve

Valves
^^^^^^

``water_valve_entities``

Valves are links that reduce flow in a controlled manner. There are many types of valves that
each operate in their own way. Valves derive from ``LinkEntity``.

+--------------------------------------------+-----------+---------------------------------------------------+
| Attribute                                  | Flags     | Description                                       |
+============================================+===========+===================================================+
| ``topology.from_node_id``                  | INIT      | Node id on the from side (from ``LinkEntity``)    |
+--------------------------------------------+-----------+---------------------------------------------------+
| ``topology.to_node_id``                    | INIT      | Node id on the to side (from ``LinkEntity``)      |
+--------------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.valve_type``              | INIT      | Valve type: ``PRV``, ``PSV``, ``FCV``, or ``TCV`` |
+--------------------------------------------+-----------+---------------------------------------------------+
| ``shape.diameter``                         | INIT      | Valve diameter                                    |
+--------------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.valve_pressure``          | OPT       | Pressure setting for ``PRV`` or ``PSV``.          |
|                                            |           | Required for these valve types                    |
+--------------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.valve_flow``              | OPT       | Flow setting for ``FCV``. Required for this       |
|                                            |           | valve type                                        |
+--------------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.valve_loss_coefficient``  | OPT       | Loss coefficient for ``TCV``. Required for this   |
|                                            |           | valve type. Must be higher than its minor loss    |
+--------------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.minor_loss``              | OPT       | Minor loss coefficient (Default: 0). Head loss    |
|                                            |           | when the valve is fully open, proportional to     |
|                                            |           | flow velocity squared                             |
+--------------------------------------------+-----------+---------------------------------------------------+
| ``operational.status``                     | OPT       | Active (``True``) or Closed (``False``).          |
|                                            |           | Default: Active                                   |
+--------------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.flow``                    | PUB       | Valve flow rate                                   |
+--------------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.flow_rate.magnitude``     | PUB       | Absolute flow rate                                |
+--------------------------------------------+-----------+---------------------------------------------------+
| ``drinking_water.link_status``             | PUB       | WNTR link status (0=Closed, 1=Open, 2=Active,    |
|                                            |           | 3=CV)                                             |
+--------------------------------------------+-----------+---------------------------------------------------+

.. note::
   GPV (General Purpose Valve) and PBV (Pressure Breaker Valve) are not supported by the
   WNTRSimulator.

.. note:: Valve Types Explained

   - **PRV** (Pressure Reducing): Limits downstream pressure to the set value
   - **PSV** (Pressure Sustaining): Maintains upstream pressure at the set value
   - **FCV** (Flow Control): Limits flow to the set value
   - **TCV** (Throttle Control): Simulates partially closed valve via loss coefficient

.. note:: Valve Status

   Valves support ``operational.status`` to set the initial state: ``True`` = Active (valve
   regulates normally using its setting), ``False`` = Closed (no flow). The WNTR "Active"
   status means the valve actively enforces its setting (pressure, flow, or coefficient).
   Setting ``operational.status`` to ``True`` restores normal regulation; it does **not** set
   the valve to "Open" (which in WNTR terminology means the valve acts as a fully open pipe,
   ignoring its setting).

Controls
^^^^^^^^

Controls are not handled by the drinking water model directly, but are instead handed over to
the :ref:`rules-model`.

Configuration Options
---------------------

WNTR options are split between two sources. Both are merged at initialization and applied to the
WNTR network via ``NetworkWrapper.configure_options()``. They contribute disjoint keys to the same
WNTR options structure.

Data Options
^^^^^^^^^^^^

Stored in the dataset's ``"general"`` section. These describe physical properties of the water
network:

+-------------------------+---------+-----------------------------------------------------------+
| Option                  | Type    | Description                                               |
+=========================+=========+===========================================================+
| ``headloss``            | string  | Headloss formula: ``"H-W"`` (Hazen-Williams).             |
|                         |         | Default: ``"H-W"``                                        |
+-------------------------+---------+-----------------------------------------------------------+
| ``viscosity``           | number  | Kinematic viscosity. Default: 1.0                         |
+-------------------------+---------+-----------------------------------------------------------+
| ``specific_gravity``    | number  | Specific gravity of the fluid. Default: 1.0               |
+-------------------------+---------+-----------------------------------------------------------+
| ``demand_model``        | string  | Demand model: ``"DDA"`` or ``"PDA"``. Default: ``"DDA"``  |
+-------------------------+---------+-----------------------------------------------------------+
| ``demand_multiplier``   | number  | Global demand multiplier. Default: 1.0                    |
+-------------------------+---------+-----------------------------------------------------------+
| ``minimum_pressure``    | number  | Global minimum pressure for PDD analysis                  |
+-------------------------+---------+-----------------------------------------------------------+
| ``required_pressure``   | number  | Global required (nominal) pressure for PDD analysis       |
+-------------------------+---------+-----------------------------------------------------------+
| ``pressure_exponent``   | number  | Global pressure exponent for PDD analysis                 |
+-------------------------+---------+-----------------------------------------------------------+

Solver Options
^^^^^^^^^^^^^^

Stored in the model config under the ``"options"`` key. These control the WNTR solver behavior:

+-------------------------+---------+-----------------------------------------------------------+
| Option                  | Type    | Description                                               |
+=========================+=========+===========================================================+
| ``trials``              | integer | Maximum number of solver trials. Default: 200             |
+-------------------------+---------+-----------------------------------------------------------+
| ``accuracy``            | number  | Convergence accuracy. Default: 0.001                      |
+-------------------------+---------+-----------------------------------------------------------+
| ``headerror``           | number  | Maximum head error for convergence                        |
+-------------------------+---------+-----------------------------------------------------------+
| ``flowchange``          | number  | Maximum flow change for convergence                       |
+-------------------------+---------+-----------------------------------------------------------+
| ``damplimit``           | number  | Accuracy limit for damping                                |
+-------------------------+---------+-----------------------------------------------------------+
| ``checkfreq``           | integer | Frequency of status checks                                |
+-------------------------+---------+-----------------------------------------------------------+
| ``maxcheck``            | integer | Maximum number of status checks                           |
+-------------------------+---------+-----------------------------------------------------------+
| ``unbalanced``          | string  | Action if simulation is unbalanced                        |
+-------------------------+---------+-----------------------------------------------------------+
| ``unbalanced_value``    | number  | Value for unbalanced option                               |
+-------------------------+---------+-----------------------------------------------------------+

.. note:: The WNTRSimulator only supports the Hazen-Williams (``"H-W"``) headloss formula.

Example Configuration
^^^^^^^^^^^^^^^^^^^^^

Dataset general section with data options:

.. code-block:: json

    {
        "general": {
            "hydraulic": {
                "headloss": "H-W",
                "viscosity": 1.0,
                "specific_gravity": 1.0,
                "demand_model": "PDA",
                "minimum_pressure": 0.0,
                "required_pressure": 20.0,
                "pressure_exponent": 0.5
            }
        }
    }

Model config with solver options:

.. code-block:: json

    {
        "name": "water_simulation",
        "type": "drinking_water",
        "dataset": "water_network",
        "options": {
            "hydraulic_timestep": 3600,
            "hydraulic": {
                "trials": 200,
                "accuracy": 0.001
            }
        }
    }

Other Considerations
--------------------

Names, IDs and References
^^^^^^^^^^^^^^^^^^^^^^^^^

WNTR internally works with names for objects. For consistency, entity IDs (cast to strings) are
used as WNTR object names. It may be tempting to use the ``reference`` field instead of the ID,
but there is no guarantee that every object will have a ``reference``. Mixing ``reference`` and
``id`` (e.g. falling back to the ``id`` when an entity does not have a ``reference``) creates a
risk of name collisions.

Units
^^^^^

Units must be in SI or SI-derived. Suggested values:

* length: m
* pressure (head): m
* diameter: m

See `WNTR Units <https://usepa.github.io/WNTR/units.html>`_.

When converting data from EPANET sources, units must be converted to SI properly.

Notes
-----

* Headloss is not available as a published attribute. The WNTRSimulator has removed headloss
  from its results output for performance reasons.
* Controls (rule-based or conditional operations) are delegated to the :ref:`rules-model` and
  not handled within this model.
* The headloss formula is stored in the dataset ``"general"`` section under ``"hydraulic"`` →
  ``"headloss"``. Only ``"H-W"`` (Hazen-Williams) is supported.

Config Schema Reference
-----------------------

DrinkingWaterConfig
^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``dataset``: ``string`` Name of the drinking water network dataset |required|
  | ``options``: :ref:`DrinkingWaterOptions` Solver and timing options for the WNTR simulator

.. _DrinkingWaterOptions:

DrinkingWaterOptions
^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``hydraulic_timestep``: ``integer`` Hydraulic simulation timestep in seconds (default: 3600)
  | ``report_timestep``: ``integer`` Report timestep in seconds (default: same as hydraulic_timestep)
  | ``hydraulic``: :ref:`DrinkingWaterHydraulicOptions` Hydraulic solver settings

.. _DrinkingWaterHydraulicOptions:

DrinkingWaterHydraulicOptions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``trials``: ``integer`` Maximum number of solver trials (default: 200)
  | ``accuracy``: ``number`` Convergence accuracy (default: 0.001)
  | ``headerror``: ``number`` Maximum head error for convergence
  | ``flowchange``: ``number`` Maximum flow change for convergence
  | ``damplimit``: ``number`` Accuracy limit for damping
  | ``checkfreq``: ``integer`` Frequency of status checks
  | ``maxcheck``: ``integer`` Maximum number of status checks
  | ``unbalanced``: ``string`` Action if simulation is unbalanced
  | ``unbalanced_value``: ``number`` Value for unbalanced option
