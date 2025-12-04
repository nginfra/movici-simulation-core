WNTR Drinking Water Model Integration
=====================================

Goals
#####

Create a model that wraps around WNTR and provides an idiomatic Movici interface to running
simulations using the WNTR model:

- The model can process a network containing: Pipes, Junctions, Tanks, Reservoirs, Valves and Pumps
- The data model is as much as possible described in terms of entities and attributes
- The model config may contain global parameters, such as a specific density or which headloss
  equation to use
- It is a nice-to-have if the data model is compatible with other movici network tooling, such
  as the ``shortest_path`` model
- While WNTR has more features than are supported by EPANET ``.inp`` files, we focus on those
  features that can be described in ``.inp`` files

Limitations
###########

- The initial implementation does not have support for chemical reactions
- We don't support epanet ``.inp`` files directly, but we can provide tooling to convert an
  ``.inp`` file to a movici dataset
- Patterns are not included in the model. Patterns values that change over time in a predictable
  manner, eg a pump rate goes to 70% at t=x. These changes should be produced by one or morejkk
  different models, such as a tape player. We can provide tooling to create tapefile datasets from
  ``.inp`` files

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

.. admonition:: Question

   Since the model can only calculate small timesteps at a time, it can be helpful if it can be
   "paused" at a certain internal timestamp and then "resumed" later on. Is there a way in WNTR
   to "continue" from an existing result with small changes to the input state? There is some
   documentation that alludes to this
   `here <https://usepa.github.io/WNTR/hydraulics.html#pause-and-restart>`_

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
- ``drinking_water.demand`` (``INIT``): The effective demand (ie. base_demand * demand_factor)
- ``drinking_water.pressure`` (``PUB``): The dynamic pressure at the node.
- ``drinking_water.head`` (``PUB``): The static (total) head at the node (elevation + pressure)

.. admonition:: Question

   In the PR, currently there is a ``demand_deficit`` attribute, that takes data from the WNTR
   result. However, I cannot find anything in the WNTR documentation about this attribute. Where
   did you find out about this attribute and what does it mean?

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

.. admonition :: Question

   Tanks can be specified to be overflowable. If set to be overflowable, any water added when it
   is at max capacity (max level) is removed. What happens to a tank when it's full but not
   overflowable

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

.. admonition :: Question

   We can specifiy min_level and min_volume which represent the minimum (residual) level or volume
   for a tank to empty out (the tank does not empty out beyond it's minimum level/volume). There is
   also max_level. But there is not max_volume. How do these attributes work? Can they be combined
   or are they restricted to the tank type (either constant diameter or volume curve)? Which one 
   takes precedence? I have now made the assumption that it must either take one group of
   attributes, or the other, but that may not be right.

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

.. admonition:: Question

   Reservoirs can be used as infinite water sources. But can they also be used as water drains?
   Related question: does a reservoir need to be connected to a pump, or can it also connect to
   a pipe?

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
  headloss calculation method used. The specific method will be stored in the dataset ``"general"``
  section under the ``"headloss_method"`` key
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

.. note:: A dataset's "general" section may be used to add keys specific to datasets of a given
   type. We can there specify that for a dataset of type ``"drinking_water_network"`` we require
   a ``"headloss_method"`` key that specifies which headloss calculation method should be used.
   However, we need to implement retrieving the general section from ``TrackedState``. This is
   currently not yet possible, but very doable to implement. Also we do not have logic that can
   validate the ``"general"`` section, so we must be careful when using this part of the dataset

.. admonition:: Question

   I think the flow direction is given by the sign of the velocity, but are we sure? Also, to what
   direction is the flow restricted if a check valve is set? from -> to direction or reverse? I
   hope that it allows flow from -> to

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


.. admonition:: Question

   In WNTR, a pump status may be ``open``, ``active`` or ``closed`` where ``active`` is a
   subcategory of ``open``, but with a specific speed set. Can we get away with just modeling this
   with ``open`` and ``closed`` (ie, ``operational.status`` set to ``True`` or ``False``)?

.. admonition:: Question

   When configuring a ``power`` pump, the documentation states that it is a fixed power pump. Does
   that also mean that the speed value is ignored in that case? How does the speed affect the pump
   in case of a head pump? What is the meaning of speed = 1? (nominal pump speed)

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

.. admonition:: Question

   It might be useful to figure out exactly how the different valve types are modeled, so that we
   are confident in what they do and what the various settings mean

.. admonition:: Question

   As with pumps, in WNTR a valve status may be ``open``, ``active`` or ``closed``. However, in
   an EPANET ``.inp`` file, a valve does not have such a status. It only has a setting, based on
   the valve type. What does it mean when a valve is given an ``open`` or ``close`` status in WNTR?
   Should we support this? It might be easier to not expose this behaviour for now.

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

The model has the following configuration options:

- Viscosity: optional set the viscosity (default 1)
- Specific gravity: optional set the specific gravity (default 1)
- timestep: if we have transient behaviour, this is the interval that will govern our "next_time"
- rtol: relative tolerance for convergence (default 1e-3, see WNTR HydraulicOptions)

Let's keep the other options at their default vdalue

Units
-----

Units must be in SI or SI-derived. Suggested values:

- length: m
- pressure (head): m 
- headloss: dependent on the pipe headloss calculation method
- diameter: m

see `WNTR Units <https://usepa.github.io/WNTR/units.html>`_

When creating dataset from inp files, the units must be converted properly. 

