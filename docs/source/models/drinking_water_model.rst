WNTR Drinking Water Model Integration
=====================================

Goals
#####

Create a model that wraps around WNTR and provides an idiomatic Movici interface to running
simulations using the WNTR model:

- The model can process a network containing: Pipes, Junctions, Tanks, Reservoirs, Valves and Pumps
- The data model is as much as possible described in terms of entities and attributes
- Data-related options (headloss formula, viscosity, etc.) are stored in the dataset's
  ``"general"`` section
- Solver-related options (trials, accuracy, etc.) are stored in the model config under
  ``"options"``
- It is a nice-to-have if the data model is compatible with other movici network tooling, such
  as the ``shortest_path`` model

Limitations
###########

- The initial implementation does not have support for chemical reactions
- EPANET ``.inp`` files are not supported directly. External tooling can convert ``.inp`` files
  to Movici datasets
- Patterns are not included in the model. Values that change over time in a predictable
  manner (e.g. a pump rate goes to 70% at t=x) should be produced by one or more
  different models, such as a tape player

Model Characteristics
#####################

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
| :math:`Y_{t_n}`: Model output state ate :math:`t_n` 

.. warning::
  This results in a possible circular dependency where the model both subscribes and publishes to 
  an attribute. While the orchestrator prevents a self-dendency, ie it will not call a model on its
  own update, even when it technically subsribes to its own data, the user must still be careful 
  When configuring a scenario containing this model, the initial state should be proviced in the
  dataset and not a result of another model's calculation. At all times there must only be one
  publisher of a certain attribute in an entity group in a dataset

Since the model can act both on internal changes and external changes, it cannot do a full run at
once. It must be able to react to changes from the outside. When it receives an outside change, it
must incorporate those changes into its internal state and then calculate from there on

.. note:: Pause and Restart

   WNTR supports pausing and restarting simulations using ``sim.run_sim(convergence_error=True)``
   followed by ``sim.run_sim()`` with modified network state. When WNTR encounters non-convergence
   or a control action time, it can pause and allow modifications before continuing. This allows
   our model to integrate external changes between WNTR simulation steps.

Data Model
##########

The drinking water network data model can be described as following

Junctions
---------

``water_junction_entities``

Junctions are nodes in the drinking water network. They connect pipes and can be used as demand
nodes. Junctions derive from ``PointEntity`` and contain the following attributes:

- ``geometry.x`` (``INIT``): location x coordinate (inherited from ``PointEntity``) 
- ``geometry.y`` (``INIT``): location y coordinate (inherited from ``PointEntity``) 
- ``geometry.z`` (``INIT``): elevation (inherited from ``PointEntity``). This can be redeclared to
  be ``INIT`` so that it is declared required 
- ``drinking_water.base_demand`` (``INIT``): The base demand on this node, this may be multiplied
  by the  demand factor to obtain the total/actual demand
- ``drinking_water.demand_factor`` (``OPT``): a scaling factor for the demand
- ``drinking_water.minimum_pressure`` (``OPT``): Per-junction minimum pressure for PDD analysis.
  Overrides the global ``minimum_pressure`` from the dataset's ``"general"`` section. NaN values
  fall back to the global setting.
- ``drinking_water.required_pressure`` (``OPT``): Per-junction required (nominal) pressure for
  PDD analysis. Overrides the global ``required_pressure`` from the dataset's ``"general"``
  section. NaN values fall back to the global setting.
- ``drinking_water.pressure_exponent`` (``OPT``): Per-junction pressure exponent for PDD
  analysis. Overrides the global ``pressure_exponent`` from the dataset's ``"general"`` section.
  NaN values fall back to the global setting.
- ``drinking_water.demand`` (``INIT``): The effective demand (ie. base_demand * demand_factor)
- ``drinking_water.pressure`` (``PUB``): The dynamic pressure at the node.
- ``drinking_water.head`` (``PUB``): The static (total) head at the node (elevation + pressure)

.. note:: About demand_deficit

   The ``demand_deficit`` attribute has been removed from the implementation. It is not a standard
   WNTR attribute and would need to be calculated manually if required (actual_demand - required_demand
   when pressure is insufficient).

Water Tanks
-----------

``water_tank_entities``

Tanks are buffers for drinking water, they are one of the transient elements of the drinking water
model, as a simulation progresses, tanks may fill up or empty over time. Tanks derive from
``PointEntity`` and contain the following attributes:


- ``geometry.x`` (``INIT``): location x coordinate (inherited from ``PointEntity``) 
- ``geometry.y`` (``INIT``): location y coordinate (inherited from ``PointEntity``) 
- ``geometry.z`` (``INIT``): elevation at tank bottom (inherited from ``PointEntity``). This can
  be redeclared to be ``INIT`` so that it is declared required 
- ``drinking_water.overflow`` (``OPT``): boolean to indicate whether a tank can overflow when full
  (max_level reached). Default: ``False``

.. note:: Tank Overflow Behavior

   If a tank is set to overflow (``drinking_water.overflow = True``), water added when at max_level
   is lost (spilled). If overflow is ``False`` and the tank reaches max_level, the connected pipe
   flows and pump operations are constrained - the network will find a new equilibrium where
   inflow matches outflow, potentially causing backpressure or pump shutoffs.

The shape and volume of the tank can either be of constant diameter for cylindrical tanks, or the
volume can be defined by a volume curve. Either is valid, so they must be ``OPT`` attributes.
However, at runtime, we should check if we have the required attributes for either (for each pump).
If we encounter pumps that do not have either a diameter or a volume curve defined, we should raise
:class:`movici_simulation_core.exceptions.NotReady` in the :meth:`TrackedModel.initialize` method
to indicate that we're still waiting for data. The associated attributes for tank volume for a
constant diameter tank are:

- ``shape.diameter`` (``OPT``): tank diameter for a constant diameter tank
- ``drinking_water.min_level`` (``OPT``): Minimum level to be able to drain (Default: 0)
- ``drinking_water.max_level`` (``OPT``): Maximum level. If a tank is overflowable, it will
  overflow beyond this level.

For a non-cylindrical tank we must supply the following attributes:

- ``shape.volume_curve`` (``OPT``): a curve (multiple (x,y) pairs that define the tank volume over
  the depth of the tank). This can be defined as a (2,)-csr attribute.
- ``drinking_water.min_volume`` (``OPT``): Minimum volume to be able to drain

.. note:: Tank Level vs Volume Attributes

   WNTR uses ``min_level`` and ``max_level`` for all tank types. For volume curve tanks,
   ``min_vol`` can also be specified and WNTR will derive the corresponding min_level from
   the curve. The ``max_level`` is always used as the upper bound. If both ``min_vol`` and
   ``min_level`` are specified, the higher effective level takes precedence.

The following attributes are published by the model

- ``drinking_water.level`` (``INIT|PUB``). Water level (m) in the tank. Also required as an initial
  value
- ``drinking_water.pressure`` (``PUB``): The dynamic pressure in the tank
- ``drinking_water.head`` (``PUB``): The static (total) head in the tank (elevation + pressure)

Water Reservoir Entities
------------------------

``water_reservoir_entities``

A reservoir is a tank that never empties. It has a fixed head (which can change by varying the
multiplier). Reservoir derive from ``PointEntity`` and contain the following attributes:

- ``geometry.x`` (``INIT``): location x coordinate (inherited from ``PointEntity``) 
- ``geometry.y`` (``INIT``): location y coordinate (inherited from ``PointEntity``)
- ``drinking_water.base_head`` (``INIT``): the base head of the reservoir
- ``drinking_water.head_factor`` (``OPT``): head multiplier (Default: 1)
- ``drinking_water.head`` (``PUB``): calculated as base_head * head_factor
- ``drinking_water.flow`` (``PUB``): Total water flow rate flowing out of the reservoir

.. note:: 
   Reservoirs are not calculated using an elevation, so we don't care about the ``geometry.z``

.. note:: Reservoirs as Sources and Drains

   Yes, reservoirs can act as both sources (water flows out) and drains (water flows in),
   depending on the hydraulic conditions. A reservoir with lower head than connected nodes will
   act as a drain. Reservoirs can connect directly to pipes - no pump is required. Flow direction
   is determined by head differences.

Pipes
-----

``water_pipe_entities``

Pipes are links that tranport water from one node (Junction, Tank, Reservoir(?)) at a high head to
another node at a lower head and experience a pressure drop (head loss) while doing so. Pipes
derive from ``LinkEntity`` and ``LineEntity`` and contain the following attributes

- ``geometry.linestring_2d`` (``OPT``): 2D linestring geometry. From ``LineEntity``
- ``geometry.linestring_3d`` (``OPT``): 3D Linestring geometry. From ``LineEntity``. ``LineEntity``
  can be used to determine if at least one of them is set
- ``shape.length`` (``OPT``): can be used to precalculate and provide the line length if neither
  linestring_2d or linestring_3d is set. Otherwise we can calculate the line length (should use
  numba for speed)
- ``topology.from_node_id`` (``INIT``): Node id on the from side (pipe start). From ``LinkEntity``
- ``topology.to_node_id`` (``INIT``): Node id on the to side (pipe end). From ``LinkEntity``
- ``shape.diameter`` (``INIT``): Pipe diameter
- ``drinking_water.roughness`` (``INIT``): Pipe roughness factor. These values are tied to the
  headloss calculation method used. The headloss formula is stored in the dataset ``"general"``
  section under ``"hydraulic"`` → ``"headloss"`` (e.g. ``"H-W"``, ``"D-W"``, ``"C-M"``)
- ``drinking_water.minor_loss`` (``OPT``): Minor loss coefficient (Default 0). When a pipe has 
  curves and bends, addtional head loss may occur, these losses are bundled into a single
  coefficient and are proportional to the flow velocity squared
- ``operational.status`` (``OPT|PUB``): Optional init param to determine if  a pipe is open
  (``True``) or closed (``False``). The model also outputs this property (in case certain control
  schemes close or reopen a pipe)
- ``drinking_water.check_valve`` (``OPT``): Boolean to indicate that flow is restricted to one
  direction. Default: False
- ``drinking_water.flow`` (``PUB``): Water flow rate through the pipe
- ``drinking_water.velocity`` (``PUB``): water velocity (I presume that the sign of the velocity
  indicates the directionality)
- ``drinking_water.headloss`` (``PUB``): calculated headloss in the pipe

.. note:: The dataset's ``"general"`` section stores data-related WNTR hydraulic options
   (headloss formula, viscosity, specific gravity, demand model, etc.). These are read from
   ``TrackedState`` during initialization and applied to the WNTR network via
   ``NetworkWrapper.configure_options()``. See the Options section below for the full split
   between dataset general and model config.

.. note:: Check Valve Direction

   Yes, flow direction is indicated by the sign of velocity/flow (positive = from_node to to_node).
   Check valves (``drinking_water.check_valve = True``) restrict flow to the from_node → to_node
   direction only. Reverse flow (from to_node back to from_node) is prevented.

Pumps
-----

``water_pump_entities``
  
Pumps are links in the network. They have a direction and pump water (increase the head) from one
node (reservoir, tank, junction) to another. Pumps derive from ``LinkEntity`` and have the
following attributes

- ``topology.from_node_id`` (``INIT``): Node id on the from side (pipe start). From ``LinkEntity``
- ``topology.to_node_id`` (``INIT``): Node id on the to side (pipe end). From ``LinkEntity``
- ``type`` (``INIT``): enum attribute for the curve's type. Either ``power`` or ``head``
- ``drinking_water.power`` (``OPT``): fixed power for a ``power`` pump. Required for a ``power``
  pump
- ``drinking_water.speed`` (``OPT``): relative pump speed. Default 1
- ``drinking_water.head_curve`` (``OPT``): head/flow curve for a ``head`` pump as (x,y)-pairs.
  data type shape can be (2,)-csr. Required for a ``head`` pump
- ``operational.status`` (``OPT|PUB``): Whether the pump is open (``True``) or closed (``False``).
  Default ``True``
- ``drinking_water.flow`` (``PUB``): pump flow rate


.. note:: Pump Status

   We model pump status as a boolean (``operational.status``): ``True`` = open/active, ``False`` = closed.
   The WNTR "active" status (open with specific speed) is handled by combining ``operational.status = True``
   with a ``drinking_water.speed`` value. This simplifies the interface while maintaining full functionality.

.. note:: Power Pump Speed

   For ``power`` pumps, the speed setting is **ignored** by WNTR. Power pumps provide constant power
   regardless of the speed setting. For ``head`` pumps, speed scales the pump curve: speed=1 is nominal,
   speed=0.8 reduces head and flow by 80%, etc.

Valves
------

``water_valve_entities``

Valves are links that reduce flow in a controlled manner. There are many types of valves that 
each operate in their own way. Valves derive from ``LinkEntity`` and have the following attributes:

- ``topology.from_node_id`` (``INIT``): Node id on the from side (pipe start). From ``LinkEntity``
- ``topology.to_node_id`` (``INIT``): Node id on the to side (pipe end). From ``LinkEntity``
- ``type`` (``INIT``). Valve type as an enum. one of ``PRV``, ``PSV``, ``PBV``, ``FCV``, ``TCV`` or
  ``GPV``
- ``shape.diameter``. Valve diameter. 
- ``drinking_water.valve_pressure`` (``OPT``): Pressure setting for a ``PRV``, ``PSV`` or ``PBV``.
  Required when using one of these valve types
- ``drinking_water.valve_flow`` (``OPT``): Flow setting for a ``FCV``. Required when using this
  type of valve
- ``drinking_water.valve_loss_coefficient`` (``OPT``). Loss coefficient for a ``TCV``. Required
  when using this type of valve. Must be higher than its minor loss 
- ``drinking_water.valve_open_factor (``OPT``): open fraction for a ``PCV`` valve. Required
  when using this type of valve
- ``drinking_water.valve_curve`` (``OPT``). Valve curve for a ``GPV`` as (x,y) pairs. Required
  when using this type of valve. Data shape can be (2,)-csr
- ``drinking_water.minor_loss`` (``OPT``): Minor loss coefficient (Default 0). The headloss
  coefficient when a valve is fully open. The head loss scales with this coefficient and is
  proportional to the flow velocity squared

.. note::
   We have the option of grouping the setting attribute for ``PRV``, ``PSV``, ``PBV``, ``FCV``
   and ``TCV`` into a single attribute called ``drinking_water.valve_setting`` and have the
   meaning be derived from the valve type. We would still need a separate attribute for the ``GPV``
   setting, since it's a curve and not a simple floating point number.

.. note:: Valve Types Explained

   - **PRV** (Pressure Reducing): Limits downstream pressure to the set value
   - **PSV** (Pressure Sustaining): Maintains upstream pressure at the set value
   - **PBV** (Pressure Breaker): Reduces pressure by a fixed amount
   - **FCV** (Flow Control): Limits flow to the set value
   - **TCV** (Throttle Control): Simulates partially closed valve via loss coefficient
   - **GPV** (General Purpose): Custom headloss-vs-flow relationship via curve

.. note:: Valve Status

   Valves do not have an ``operational.status`` attribute in our implementation. The valve setting
   (pressure, flow, or coefficient) determines the valve behavior. Setting a valve_pressure of 0
   for a PRV effectively closes it. This simplifies the interface and matches EPANET INP behavior.

Controls
--------

Controls are not handled by the drinking water model directly, but are instead handed over to
the :ref:`rules-model`

Other considerations
####################

Names, IDs and reference
------------------------

WNTR internally works with names for objects. For our own consistency we may want to just use our
id's when giving WNTR objects names, perhaps cast to strings. It may be tempting to use the 
``reference`` field instead of the id, but there is no guarantee that every object will have
``reference`` and if we mix and match ``reference`` and ``id`` (eg. fall back to the ``id`` when
an entity does not have a ``reference``) there is a risk of collisions.


Options
-------

WNTR options are split between two sources:

**Data options** — stored in the dataset's ``"general"`` section. These describe physical
properties of the water network:

- ``headloss``: Headloss formula (``"H-W"``, ``"D-W"``, ``"C-M"``). Default: ``"H-W"``
- ``viscosity``: Kinematic viscosity. Default: 1.0
- ``specific_gravity``: Specific gravity of the fluid. Default: 1.0
- ``demand_model``: Demand model (``"DDA"`` or ``"PDA"``). Default: ``"DDA"``
- ``demand_multiplier``: Global demand multiplier. Default: 1.0
- ``minimum_pressure``: Global minimum pressure for PDD analysis
- ``required_pressure``: Global required (nominal) pressure for PDD analysis
- ``pressure_exponent``: Global pressure exponent for PDD analysis

Example dataset general section::

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

**Solver options** — stored in the model config under the ``"options"`` key. These control the
WNTR solver behavior:

- ``trials``: Maximum number of solver trials. Default: 200
- ``accuracy``: Convergence accuracy. Default: 0.001
- ``headerror``: Maximum head error for convergence
- ``flowchange``: Maximum flow change for convergence
- ``damplimit``: Accuracy limit for damping
- ``checkfreq``: Frequency of status checks
- ``maxcheck``: Maximum number of status checks
- ``unbalanced``: Action if simulation is unbalanced
- ``unbalanced_value``: Value for unbalanced option

Example model config::

    {
        "dataset": "water_network",
        "hydraulic_timestep": 3600,
        "simulation_duration": 3600,
        "options": {
            "hydraulic": {
                "trials": 200,
                "accuracy": 0.001
            }
        }
    }

Both sources are merged at initialization and applied to the WNTR network via
``NetworkWrapper.configure_options()``. They contribute disjoint keys to the same WNTR options
structure.

.. note:: The WNTRSimulator only supports the Hazen-Williams (``"H-W"``) headloss formula.
   The EpanetSimulator also supports Chezy-Manning (``"C-M"``).

Units
-----

Units must be in SI or SI-derived. Suggested values:

- length: m
- pressure (head): m 
- headloss: dependent on the pipe headloss calculation method
- diameter: m

see `WNTR Units <https://usepa.github.io/WNTR/units.html>`_

When converting data from EPANET sources, units must be converted to SI properly.

