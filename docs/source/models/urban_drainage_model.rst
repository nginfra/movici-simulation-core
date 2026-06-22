.. |required| replace:: (**required**)

SWMM Urban Drainage Model
=========================

The urban drainage model (``"urban_drainage"``) wraps the EPA `Storm Water
Management Model (SWMM)
<https://www.epa.gov/water-research/storm-water-management-model-swmm>`_ engine,
through `pyswmm <https://www.pyswmm.org/>`_, to provide an idiomatic Movici
interface for simulating storm-water and sewer drainage networks. It models how
rainfall becomes runoff, how that runoff (plus any sanitary or externally imposed
inflow) is routed through conduits, pumps, orifices, weirs, outlets and storage
units, and where the network surcharges, floods or discharges. All data is
described in terms of Movici entities and attributes.

This page is written for Movici users who want to set up or run an urban-drainage
simulation: it covers the purpose of the model, the physics and terminology behind
it, the dataset you must supply (entities and attributes), the results it
publishes, the configuration options, and the caveats to be aware of. It is not a
substitute for the SWMM5 Reference Manual, which defines the underlying physics in
full.

Use cases include:

* Routing storm water and sewage through pipe networks (dynamic-wave hydraulics)
* Rainfall-runoff and infiltration analysis over subcatchments
* Flood and surcharge analysis at manholes and storage basins
* Real-time control studies, driving pumps, orifices and weirs from other models
* Coupling drainage behaviour with other Movici models in a scenario

Goals
-----

* The data model is described, as much as possible, in terms of entities and
  attributes
* Simulation options (routing method, flow units, infiltration model, time steps)
  are stored in the model config under ``"options"``; they may also be supplied in
  the dataset's ``"general"`` section, which takes precedence
* Existing SWMM ``.inp`` files can be imported into Movici datasets through the
  ``"swmm"`` dataset-creator source (the runtime model itself reads Movici data,
  not ``.inp`` files)

Limitations
-----------

* **Dividers** are not modelled; under dynamic-wave routing SWMM treats them as
  ordinary junctions
* Link **velocity** is not published (the live engine exposes no usable per-link
  velocity); the Froude number is published instead
* Outfalls support ``FREE`` / ``NORMAL`` / ``FIXED`` boundaries only; ``TIDAL``
  and ``TIMESERIES`` (which need referenced boundary data) are not supported and
  raise a clear error
* Water quality / pollutants, LID controls and groundwater are out of scope
* Only one SWMM simulation may be open per process (see *Model Characteristics*)

Model Characteristics
---------------------

The urban drainage model is a **transient, forward-only** model. A single live
SWMM simulation is opened at initialization and advanced forward to each Movici
moment; SWMM cannot rewind, so the model never steps backwards. Like other
transient models its output state depends on an initial state and evolves over
time even when the input state is unchanged (for example a storage basin draining
between updates).

* **Time stepping.** Movici calls ``update(moment)`` at the ``report_timestep``
  cadence (default 300 s); internally SWMM routes at the finer
  ``hydraulic_timestep`` (default 60 s). At ``t=0`` the model reports the initial
  conditions without stepping.
* **Minimum step.** SWMM advances in whole seconds, so the effective minimum step
  is 1 second; a fractional Movici ``time_scale`` is rounded down when stepping
  (the model logs a warning when the time scale is non-integer).
* **Control latency.** Control inputs are applied to the live engine *before* each
  forward step, so a value supplied at time *t* governs the step from *t* onward -
  a one-step latency, as in real-time control.
* **Calendar.** SWMM tags every step with an absolute date/time, which it uses for
  time-of-day-dependent inputs (evaporation, rainfall series) and for the
  timestamps in its report. The model anchors that calendar to the Movici timeline
  reference so they line up with the scenario's world time (falling back to a fixed
  epoch when no timeline is set).
* **One simulation per process.** EPA-SWMM permits only a single open simulation
  per process. Only one urban drainage model can therefore run in a given process;
  additional instances must run in separate processes (e.g. a distributed
  simulation). Opening a second simulation raises a clear error.

Hydrology and Routing
---------------------

A drainage simulation couples two processes:

* **Hydrology** turns rainfall into runoff. Each subcatchment receives rainfall
  from its rain gage, loses part of it to infiltration (into pervious soil) and to
  depression storage, and converts the rest into a runoff flow delivered to the
  node it drains to.
* **Hydraulics** moves that water through the network. *Routing* is the
  computation of how the flow rate and water depth in each link - and the water
  level at each node - change over time as water is conveyed downstream, stored,
  surcharges or floods.

The network is built from **nodes** (junctions, outfalls and storage units) joined
by **links** (conduits and the regulators: pumps, orifices, weirs and outlets),
each link connecting a ``from`` node to a ``to`` node. Subcatchments sit outside
the pipe network and deliver their runoff to a single node; rain gages supply the
rainfall that drives the subcatchments. Surface water therefore enters the network
as subcatchment runoff (or as an externally imposed ``generated_inflow`` at a
node) - the model does not separately represent street inlets or grates.

The routing method is chosen with the ``flow_routing`` option (see the Innovyze
`Routing of Flows
<https://help-innovyze.atlassian.net/wiki/spaces/infoswmm/pages/17597742/Routing+of+Flows+and+Pollutants>`_
overview):

* **STEADY** - each reporting step is treated as an independent steady, uniform
  flow. Fastest, but it ignores storage, backwater and travel time; suitable only
  for preliminary or long-term continuity analysis.
* **KINWAVE** (kinematic wave) - flow and cross-sectional area vary along the
  conduit and in time, but a conduit cannot convey more than its full-flow
  capacity and there is no backwater, surcharging or pressurised flow; excess
  water is ponded or lost.
* **DYNWAVE** (dynamic wave) - solves the full Saint-Venant equations, so it
  handles backwater, flow reversal, surcharging, pressurised flow and looped or
  branched networks. It is the **default** and is recommended for drainage
  networks.

How It Works
------------

1. At initialization the model synthesises a transient SWMM ``.inp`` file from the
   Movici entity groups and opens a live ``Simulation`` on it.
2. Each ``update(moment)`` applies the current control inputs (rainfall, node
   inflow, regulator settings) to the live SWMM objects.
3. It then advances the simulation forward to the requested moment.
4. Finally it reads the per-element results (depth, head, flooding, flow, runoff,
   ...) back into the published Movici attributes.

Data Model
----------

Each SWMM object type maps to a Movici entity group, listed below with its full
attribute set. The ``Flags`` column uses ``INIT`` (required static input), ``OPT``
(optional input or runtime control) and ``PUB`` (published result). Geometry and
topology come from the underlying Movici entity type. Units assume the default
metric ``flow_units = CMS`` (metres, m³/s, mm/hr, hectares); selecting US
``flow_units`` switches depths and rates to inches.

Junctions
^^^^^^^^^

``drainage_junction_entities``

Junctions are the manholes and pipe-connection nodes of the drainage network. They receive piped flow from connecting links and the runoff of any subcatchment that drains to them; the model does not separately represent street inlets or grates. Junctions derive from ``PointEntity``.

+-------------------------------------+-------+-----------------------------------------------------------------+
| Attribute                           | Flags | Description                                                     |
+=====================================+=======+=================================================================+
| ``geometry.x``                      | OPT   | Map x location ([COORDINATES]); display only (from PointEntity) |
+-------------------------------------+-------+-----------------------------------------------------------------+
| ``geometry.y``                      | OPT   | Map y location ([COORDINATES]); display only (from PointEntity) |
+-------------------------------------+-------+-----------------------------------------------------------------+
| ``urban_drainage.invert_elevation`` | INIT  | Node invert (bottom) elevation (m)                              |
+-------------------------------------+-------+-----------------------------------------------------------------+
| ``urban_drainage.max_depth``        | OPT   | Depth from invert to ground; 0 = unlimited (m)                  |
+-------------------------------------+-------+-----------------------------------------------------------------+
| ``urban_drainage.initial_depth``    | OPT   | Water depth at the start of the run (m)                         |
+-------------------------------------+-------+-----------------------------------------------------------------+
| ``urban_drainage.surcharge_depth``  | OPT   | Head allowed above max_depth before flooding (m)                |
+-------------------------------------+-------+-----------------------------------------------------------------+
| ``urban_drainage.ponded_area``      | OPT   | Ponded surface area when flooded (m²)                           |
+-------------------------------------+-------+-----------------------------------------------------------------+
| ``urban_drainage.generated_inflow`` | OPT   | Externally imposed point inflow (m³/s)                          |
+-------------------------------------+-------+-----------------------------------------------------------------+
| ``urban_drainage.water_depth``      | PUB   | Water depth above the invert (m)                                |
+-------------------------------------+-------+-----------------------------------------------------------------+
| ``urban_drainage.hydraulic_head``   | PUB   | Hydraulic head = invert + depth (m)                             |
+-------------------------------------+-------+-----------------------------------------------------------------+
| ``urban_drainage.flooding``         | PUB   | Surface flooding / overflow rate (m³/s)                         |
+-------------------------------------+-------+-----------------------------------------------------------------+
| ``urban_drainage.total_inflow``     | PUB   | Total inflow to the node (m³/s)                                 |
+-------------------------------------+-------+-----------------------------------------------------------------+
| ``urban_drainage.total_outflow``    | PUB   | Total outflow from the node (m³/s)                              |
+-------------------------------------+-------+-----------------------------------------------------------------+
| ``urban_drainage.lateral_inflow``   | PUB   | External + runoff inflow to the node (m³/s)                     |
+-------------------------------------+-------+-----------------------------------------------------------------+
| ``urban_drainage.stored_volume``    | PUB   | Water volume held at the node (m³)                              |
+-------------------------------------+-------+-----------------------------------------------------------------+

Outfalls
^^^^^^^^

``drainage_outfall_entities``

Outfalls are terminal nodes that impose a downstream boundary condition on the network. Outfalls derive from ``PointEntity``.

+-------------------------------------+-------+-----------------------------------------------------------------------+
| Attribute                           | Flags | Description                                                           |
+=====================================+=======+=======================================================================+
| ``geometry.x``                      | OPT   | Map x location ([COORDINATES]); display only (from PointEntity)       |
+-------------------------------------+-------+-----------------------------------------------------------------------+
| ``geometry.y``                      | OPT   | Map y location ([COORDINATES]); display only (from PointEntity)       |
+-------------------------------------+-------+-----------------------------------------------------------------------+
| ``urban_drainage.invert_elevation`` | INIT  | Node invert (bottom) elevation (m)                                    |
+-------------------------------------+-------+-----------------------------------------------------------------------+
| ``urban_drainage.outfall_type``     | INIT  | Boundary type: FREE / NORMAL / FIXED (TIDAL / TIMESERIES unsupported) |
+-------------------------------------+-------+-----------------------------------------------------------------------+
| ``urban_drainage.fixed_stage``      | OPT   | Fixed boundary water-surface elevation, used by FIXED (m)             |
+-------------------------------------+-------+-----------------------------------------------------------------------+
| ``urban_drainage.flap_gate``        | OPT   | Flap gate preventing reverse (tidal) flow (bool)                      |
+-------------------------------------+-------+-----------------------------------------------------------------------+
| ``urban_drainage.generated_inflow`` | OPT   | Externally imposed point inflow (m³/s)                                |
+-------------------------------------+-------+-----------------------------------------------------------------------+
| ``urban_drainage.water_depth``      | PUB   | Water depth above the invert (m)                                      |
+-------------------------------------+-------+-----------------------------------------------------------------------+
| ``urban_drainage.hydraulic_head``   | PUB   | Hydraulic head = invert + depth (m)                                   |
+-------------------------------------+-------+-----------------------------------------------------------------------+
| ``urban_drainage.flooding``         | PUB   | Surface flooding / overflow rate (m³/s)                               |
+-------------------------------------+-------+-----------------------------------------------------------------------+
| ``urban_drainage.total_inflow``     | PUB   | Total inflow to the node (m³/s)                                       |
+-------------------------------------+-------+-----------------------------------------------------------------------+
| ``urban_drainage.total_outflow``    | PUB   | Total outflow from the node (m³/s)                                    |
+-------------------------------------+-------+-----------------------------------------------------------------------+
| ``urban_drainage.lateral_inflow``   | PUB   | External + runoff inflow to the node (m³/s)                           |
+-------------------------------------+-------+-----------------------------------------------------------------------+
| ``urban_drainage.stored_volume``    | PUB   | Water volume held at the node (m³)                                    |
+-------------------------------------+-------+-----------------------------------------------------------------------+

Storage units
^^^^^^^^^^^^^

``drainage_storage_entities``

Storage units are ponds, basins and tanks with a stage-storage relationship. The shape is selected by ``storage_geometry``; when it is omitted the shape is inferred (a ``storage_curve`` means TABULAR, otherwise FUNCTIONAL). Each shape reads a different subset of the parameters below. Storage units derive from ``PointEntity``.

+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| Attribute                                      | Flags | Description                                                                                    |
+================================================+=======+================================================================================================+
| ``geometry.x``                                 | OPT   | Map x location ([COORDINATES]); display only (from PointEntity)                                |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``geometry.y``                                 | OPT   | Map y location ([COORDINATES]); display only (from PointEntity)                                |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.invert_elevation``            | INIT  | Node invert (bottom) elevation (m)                                                             |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.max_depth``                   | INIT  | Maximum water depth (m)                                                                        |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.storage_geometry``            | OPT   | Shape: FUNCTIONAL / TABULAR / CYLINDRICAL / CONICAL / PARABOLIC / PYRAMIDAL                    |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.storage_constant``            | OPT   | FUNCTIONAL constant surface area A0 (m²)                                                       |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.storage_coefficient``         | OPT   | FUNCTIONAL area coefficient A1                                                                 |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.storage_exponent``            | OPT   | FUNCTIONAL area exponent A2 (area = A0 + A1·depth^A2)                                          |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.storage_curve``               | OPT   | TABULAR (depth m, area m²) curve; (2,)-csr                                                     |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.storage_geometry_parameters`` | OPT   | Geometric (L, W, Z); (3,) (m; Z = side slope for CONICAL/PYRAMIDAL, full height for PARABOLIC) |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.initial_depth``               | OPT   | Water depth at the start of the run (m)                                                        |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.surcharge_depth``             | OPT   | Head allowed above max_depth before flooding (m)                                               |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.ponded_area``                 | OPT   | Ponded surface area when flooded (m²)                                                          |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.generated_inflow``            | OPT   | Externally imposed point inflow (m³/s)                                                         |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.water_depth``                 | PUB   | Water depth above the invert (m)                                                               |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.hydraulic_head``              | PUB   | Hydraulic head = invert + depth (m)                                                            |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.flooding``                    | PUB   | Surface flooding / overflow rate (m³/s)                                                        |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.total_inflow``                | PUB   | Total inflow to the node (m³/s)                                                                |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.total_outflow``               | PUB   | Total outflow from the node (m³/s)                                                             |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.lateral_inflow``              | PUB   | External + runoff inflow to the node (m³/s)                                                    |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+
| ``urban_drainage.stored_volume``               | PUB   | Water volume held at the node (m³)                                                             |
+------------------------------------------------+-------+------------------------------------------------------------------------------------------------+

Conduits
^^^^^^^^

``drainage_conduit_entities``

Conduits are the pipes and channels that carry gravity flow between two nodes. Conduits derive from ``LinkEntity``.

+-------------------------------------------+-------+---------------------------------------------------------------+
| Attribute                                 | Flags | Description                                                   |
+===========================================+=======+===============================================================+
| ``topology.from_node_id``                 | INIT  | Upstream node id (from LinkEntity)                            |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``topology.to_node_id``                   | INIT  | Downstream node id (from LinkEntity)                          |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``shape.length``                          | INIT  | Conduit length (m, > 0)                                       |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``urban_drainage.roughness``              | INIT  | Manning's roughness coefficient n                             |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``urban_drainage.cross_section_shape``    | INIT  | Cross-section shape (CIRCULAR, RECT_CLOSED, ...)              |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``urban_drainage.cross_section_geometry`` | INIT  | Geom1-Geom4 (m), (4,); per shape (CIRCULAR: Geom1 = diameter) |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``urban_drainage.barrels``                | OPT   | Number of parallel identical barrels (default 1)              |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``urban_drainage.inlet_offset``           | OPT   | Inlet height above the upstream node invert (m)               |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``urban_drainage.outlet_offset``          | OPT   | Outlet height above the downstream node invert (m)            |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``urban_drainage.initial_flow``           | OPT   | Flow at the start of the run (m³/s)                           |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``urban_drainage.target_setting``         | OPT   | Control setting 0-1 (1 = fully open)                          |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``urban_drainage.flow``                   | PUB   | Flow rate through the link (m³/s)                             |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``urban_drainage.flow_depth``             | PUB   | Water depth inside the link (m)                               |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``urban_drainage.flow_volume``            | PUB   | Water volume stored in the link (m³)                          |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``urban_drainage.froude_number``          | PUB   | Froude number (-)                                             |
+-------------------------------------------+-------+---------------------------------------------------------------+
| ``urban_drainage.current_setting``        | PUB   | Applied control setting 0-1 (-)                               |
+-------------------------------------------+-------+---------------------------------------------------------------+

Pumps
^^^^^

``drainage_pump_entities``

Pumps lift water from the inlet node to the outlet node. With no ``pump_curve`` (or an ``IDEAL`` type) the pump passes its inlet inflow. Pumps derive from ``LinkEntity``.

+------------------------------------+-------+--------------------------------------------------------+
| Attribute                          | Flags | Description                                            |
+====================================+=======+========================================================+
| ``topology.from_node_id``          | INIT  | Upstream node id (from LinkEntity)                     |
+------------------------------------+-------+--------------------------------------------------------+
| ``topology.to_node_id``            | INIT  | Downstream node id (from LinkEntity)                   |
+------------------------------------+-------+--------------------------------------------------------+
| ``urban_drainage.pump_curve_type`` | OPT   | Pump curve type: IDEAL / PUMP1 / PUMP2 / PUMP3 / PUMP4 |
+------------------------------------+-------+--------------------------------------------------------+
| ``urban_drainage.pump_curve``      | OPT   | (2,)-csr pump curve points; axes depend on the type    |
+------------------------------------+-------+--------------------------------------------------------+
| ``urban_drainage.startup_depth``   | OPT   | Inlet depth that switches the pump on (m)              |
+------------------------------------+-------+--------------------------------------------------------+
| ``urban_drainage.shutoff_depth``   | OPT   | Inlet depth that switches the pump off (m)             |
+------------------------------------+-------+--------------------------------------------------------+
| ``urban_drainage.target_setting``  | OPT   | Pump relative speed 0-1                                |
+------------------------------------+-------+--------------------------------------------------------+
| ``urban_drainage.flow``            | PUB   | Flow rate through the link (m³/s)                      |
+------------------------------------+-------+--------------------------------------------------------+
| ``urban_drainage.flow_depth``      | PUB   | Water depth inside the link (m)                        |
+------------------------------------+-------+--------------------------------------------------------+
| ``urban_drainage.flow_volume``     | PUB   | Water volume stored in the link (m³)                   |
+------------------------------------+-------+--------------------------------------------------------+
| ``urban_drainage.froude_number``   | PUB   | Froude number (-)                                      |
+------------------------------------+-------+--------------------------------------------------------+
| ``urban_drainage.current_setting`` | PUB   | Applied control setting 0-1 (-)                        |
+------------------------------------+-------+--------------------------------------------------------+

Orifices
^^^^^^^^

``drainage_orifice_entities``

Orifices are submerged openings (side or bottom) that regulate flow. Orifices derive from ``LinkEntity``.

+-------------------------------------------+-------+------------------------------------------------+
| Attribute                                 | Flags | Description                                    |
+===========================================+=======+================================================+
| ``topology.from_node_id``                 | INIT  | Upstream node id (from LinkEntity)             |
+-------------------------------------------+-------+------------------------------------------------+
| ``topology.to_node_id``                   | INIT  | Downstream node id (from LinkEntity)           |
+-------------------------------------------+-------+------------------------------------------------+
| ``urban_drainage.orifice_type``           | INIT  | Orientation: SIDE / BOTTOM                     |
+-------------------------------------------+-------+------------------------------------------------+
| ``urban_drainage.orifice_shape``          | INIT  | Opening shape: CIRCULAR / RECT_CLOSED          |
+-------------------------------------------+-------+------------------------------------------------+
| ``urban_drainage.cross_section_geometry`` | INIT  | Opening dimensions Geom1-Geom4 (m), (4,)       |
+-------------------------------------------+-------+------------------------------------------------+
| ``urban_drainage.discharge_coefficient``  | INIT  | Discharge coefficient (-)                      |
+-------------------------------------------+-------+------------------------------------------------+
| ``urban_drainage.crest_height``           | OPT   | Opening height above the inlet node invert (m) |
+-------------------------------------------+-------+------------------------------------------------+
| ``urban_drainage.flap_gate``              | OPT   | Flap gate preventing reverse flow (bool)       |
+-------------------------------------------+-------+------------------------------------------------+
| ``urban_drainage.target_setting``         | OPT   | Opening fraction 0-1                           |
+-------------------------------------------+-------+------------------------------------------------+
| ``urban_drainage.flow``                   | PUB   | Flow rate through the link (m³/s)              |
+-------------------------------------------+-------+------------------------------------------------+
| ``urban_drainage.flow_depth``             | PUB   | Water depth inside the link (m)                |
+-------------------------------------------+-------+------------------------------------------------+
| ``urban_drainage.flow_volume``            | PUB   | Water volume stored in the link (m³)           |
+-------------------------------------------+-------+------------------------------------------------+
| ``urban_drainage.froude_number``          | PUB   | Froude number (-)                              |
+-------------------------------------------+-------+------------------------------------------------+
| ``urban_drainage.current_setting``        | PUB   | Applied control setting 0-1 (-)                |
+-------------------------------------------+-------+------------------------------------------------+

Weirs
^^^^^

``drainage_weir_entities``

Weirs are crested structures that regulate overflow. Weirs derive from ``LinkEntity``.

+-------------------------------------------+-------+--------------------------------------------------------------------+
| Attribute                                 | Flags | Description                                                        |
+===========================================+=======+====================================================================+
| ``topology.from_node_id``                 | INIT  | Upstream node id (from LinkEntity)                                 |
+-------------------------------------------+-------+--------------------------------------------------------------------+
| ``topology.to_node_id``                   | INIT  | Downstream node id (from LinkEntity)                               |
+-------------------------------------------+-------+--------------------------------------------------------------------+
| ``urban_drainage.weir_type``              | INIT  | Weir type: TRANSVERSE / SIDEFLOW / V-NOTCH / TRAPEZOIDAL / ROADWAY |
+-------------------------------------------+-------+--------------------------------------------------------------------+
| ``urban_drainage.cross_section_geometry`` | INIT  | Opening Geom1-Geom4 (m), (4,): height, length, side slope          |
+-------------------------------------------+-------+--------------------------------------------------------------------+
| ``urban_drainage.discharge_coefficient``  | INIT  | Weir discharge coefficient (-)                                     |
+-------------------------------------------+-------+--------------------------------------------------------------------+
| ``urban_drainage.crest_height``           | OPT   | Crest height above the inlet node invert (m)                       |
+-------------------------------------------+-------+--------------------------------------------------------------------+
| ``urban_drainage.flap_gate``              | OPT   | Flap gate preventing reverse flow (bool)                           |
+-------------------------------------------+-------+--------------------------------------------------------------------+
| ``urban_drainage.target_setting``         | OPT   | Opening fraction 0-1                                               |
+-------------------------------------------+-------+--------------------------------------------------------------------+
| ``urban_drainage.flow``                   | PUB   | Flow rate through the link (m³/s)                                  |
+-------------------------------------------+-------+--------------------------------------------------------------------+
| ``urban_drainage.flow_depth``             | PUB   | Water depth inside the link (m)                                    |
+-------------------------------------------+-------+--------------------------------------------------------------------+
| ``urban_drainage.flow_volume``            | PUB   | Water volume stored in the link (m³)                               |
+-------------------------------------------+-------+--------------------------------------------------------------------+
| ``urban_drainage.froude_number``          | PUB   | Froude number (-)                                                  |
+-------------------------------------------+-------+--------------------------------------------------------------------+
| ``urban_drainage.current_setting``        | PUB   | Applied control setting 0-1 (-)                                    |
+-------------------------------------------+-------+--------------------------------------------------------------------+

Outlets
^^^^^^^

``drainage_outlet_entities``

Outlets are flow-control links with a head/depth-discharge rating. Outlets derive from ``LinkEntity``.

+---------------------------------------+-------+------------------------------------------------------+
| Attribute                             | Flags | Description                                          |
+=======================================+=======+======================================================+
| ``topology.from_node_id``             | INIT  | Upstream node id (from LinkEntity)                   |
+---------------------------------------+-------+------------------------------------------------------+
| ``topology.to_node_id``               | INIT  | Downstream node id (from LinkEntity)                 |
+---------------------------------------+-------+------------------------------------------------------+
| ``urban_drainage.outlet_rating_type`` | INIT  | FUNCTIONAL or TABULAR, rated by DEPTH or HEAD        |
+---------------------------------------+-------+------------------------------------------------------+
| ``urban_drainage.crest_height``       | OPT   | Outlet height above the inlet node invert (m)        |
+---------------------------------------+-------+------------------------------------------------------+
| ``urban_drainage.rating_coefficient`` | OPT   | FUNCTIONAL coefficient (flow = coeff·x^expon)        |
+---------------------------------------+-------+------------------------------------------------------+
| ``urban_drainage.rating_exponent``    | OPT   | FUNCTIONAL exponent                                  |
+---------------------------------------+-------+------------------------------------------------------+
| ``urban_drainage.rating_curve``       | OPT   | TABULAR (head-or-depth m, flow m³/s) curve; (2,)-csr |
+---------------------------------------+-------+------------------------------------------------------+
| ``urban_drainage.flap_gate``          | OPT   | Flap gate preventing reverse flow (bool)             |
+---------------------------------------+-------+------------------------------------------------------+
| ``urban_drainage.target_setting``     | OPT   | Opening fraction 0-1                                 |
+---------------------------------------+-------+------------------------------------------------------+
| ``urban_drainage.flow``               | PUB   | Flow rate through the link (m³/s)                    |
+---------------------------------------+-------+------------------------------------------------------+
| ``urban_drainage.flow_depth``         | PUB   | Water depth inside the link (m)                      |
+---------------------------------------+-------+------------------------------------------------------+
| ``urban_drainage.flow_volume``        | PUB   | Water volume stored in the link (m³)                 |
+---------------------------------------+-------+------------------------------------------------------+
| ``urban_drainage.froude_number``      | PUB   | Froude number (-)                                    |
+---------------------------------------+-------+------------------------------------------------------+
| ``urban_drainage.current_setting``    | PUB   | Applied control setting 0-1 (-)                      |
+---------------------------------------+-------+------------------------------------------------------+

Subcatchments
^^^^^^^^^^^^^

``drainage_subcatchment_entities``

Subcatchments are surfaces that turn rainfall into runoff. They are not part of the pipe network: each routes its runoff to one node (``outlet_node_id``) and is driven by the gage referenced through ``raingage_id``. Subcatchments derive from ``PolygonEntity``.

+------------------------------------------+-------+----------------------------------------------------------------------+
| Attribute                                | Flags | Description                                                          |
+==========================================+=======+======================================================================+
| ``geometry.polygon``                     | OPT   | Subcatchment outline ([POLYGONS]); display only (from PolygonEntity) |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.area``                  | INIT  | Subcatchment area (ha)                                               |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.width``                 | INIT  | Characteristic overland-flow width (m)                               |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.percent_impervious``    | INIT  | Impervious fraction of the area (%)                                  |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.slope``                 | INIT  | Average surface slope (%)                                            |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.outlet_node_id``        | INIT  | Id of the node the runoff drains to                                  |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.raingage_id``           | INIT  | Id of the rain gage driving the rainfall                             |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.n_imperv``              | OPT   | Manning's n for the impervious sub-area                              |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.n_perv``                | OPT   | Manning's n for the pervious sub-area                                |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.s_imperv``              | OPT   | Depression storage depth, impervious (mm)                            |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.s_perv``                | OPT   | Depression storage depth, pervious (mm)                              |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.pct_zero``              | OPT   | Impervious area with no depression storage (%)                       |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.max_infiltration_rate`` | OPT   | Horton maximum infiltration rate (mm/hr)                             |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.min_infiltration_rate`` | OPT   | Horton minimum infiltration rate (mm/hr)                             |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.decay_constant``        | OPT   | Horton decay constant (1/hr)                                         |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.dry_time``              | OPT   | Time for fully saturated soil to dry (days)                          |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.suction_head``          | OPT   | Green-Ampt soil capillary suction head (mm)                          |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.conductivity``          | OPT   | Saturated hydraulic conductivity (mm/hr)                             |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.initial_deficit``       | OPT   | Green-Ampt initial moisture deficit (fraction)                       |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.curve_number``          | OPT   | SCS curve number (-)                                                 |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.rainfall``              | PUB   | Rainfall reaching the subcatchment (mm/hr)                           |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.runoff``                | PUB   | Surface runoff flow (m³/s)                                           |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.runon``                 | PUB   | Run-on received from other subcatchments (m³/s)                      |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.infiltration_loss``     | PUB   | Infiltration loss rate (mm/hr)                                       |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.evaporation_loss``      | PUB   | Evaporation loss rate (mm/hr)                                        |
+------------------------------------------+-------+----------------------------------------------------------------------+
| ``urban_drainage.snow_depth``            | PUB   | Snow depth, water equivalent (mm)                                    |
+------------------------------------------+-------+----------------------------------------------------------------------+

Which infiltration parameters are read depends on the configured ``infiltration`` model: **Horton** uses ``max_infiltration_rate`` / ``min_infiltration_rate`` / ``decay_constant`` / ``dry_time``; **Green-Ampt** uses ``suction_head`` / ``conductivity`` / ``initial_deficit``; **Curve Number** uses ``curve_number`` / ``conductivity`` / ``dry_time``. Unspecified parameters fall back to sensible defaults for the active unit system.

Rain gages
^^^^^^^^^^

``drainage_raingage_entities``

Rain gages are the rainfall sources for subcatchments. Rainfall is normally driven at runtime by another model publishing ``rainfall_intensity``. Rain gages derive from ``PointEntity``.

+---------------------------------------+-------+-------------------------------------------------------------+
| Attribute                             | Flags | Description                                                 |
+=======================================+=======+=============================================================+
| ``geometry.x``                        | OPT   | Map x location ([SYMBOLS]); display only (from PointEntity) |
+---------------------------------------+-------+-------------------------------------------------------------+
| ``geometry.y``                        | OPT   | Map y location ([SYMBOLS]); display only (from PointEntity) |
+---------------------------------------+-------+-------------------------------------------------------------+
| ``urban_drainage.rainfall_format``    | OPT   | Series format: INTENSITY / VOLUME / CUMULATIVE              |
+---------------------------------------+-------+-------------------------------------------------------------+
| ``urban_drainage.rainfall_interval``  | OPT   | Rainfall recording interval (s)                             |
+---------------------------------------+-------+-------------------------------------------------------------+
| ``urban_drainage.rainfall_intensity`` | OPT   | Runtime rainfall override (mm/hr)                           |
+---------------------------------------+-------+-------------------------------------------------------------+
| ``urban_drainage.rainfall``           | PUB   | Rainfall reported by the gage (mm/hr)                       |
+---------------------------------------+-------+-------------------------------------------------------------+

Controls
--------

The model does not implement internal SWMM controls or rules. Operational control
is supplied externally, typically by the :ref:`rules-model`, through these
optional inputs:

* ``urban_drainage.target_setting`` on a regulator (pump speed, or orifice / weir
  opening fraction, 0-1)
* ``urban_drainage.generated_inflow`` at a node (an imposed point inflow)
* ``urban_drainage.rainfall_intensity`` on a rain gage (the runtime rainfall)

These take effect on the forward step following the update in which they change
(see *Control latency*).

Configuration Options
---------------------

Simulation options are given in the model config under the ``"options"`` key. The
same keys may also be supplied in the dataset's ``"general"`` section; the two are
merged at initialization, with the dataset's ``"general"`` section taking
precedence (so the Movici wake cadence and the SWMM report step stay consistent).

+------------------------+---------+---------------------------------------------------------------------------------------------+
| Option                 | Type    | Description                                                                                 |
+========================+=========+=============================================================================================+
| ``hydraulic_timestep`` | integer | SWMM routing (hydraulic) step in seconds. Default: 60                                       |
+------------------------+---------+---------------------------------------------------------------------------------------------+
| ``report_timestep``    | integer | Movici wake cadence and SWMM report step in seconds. Default: 300                           |
+------------------------+---------+---------------------------------------------------------------------------------------------+
| ``flow_units``         | string  | CMS / LPS / MLD (metric) or CFS / GPM / MGD (US). Default: CMS                              |
+------------------------+---------+---------------------------------------------------------------------------------------------+
| ``flow_routing``       | string  | Routing method: STEADY / KINWAVE / DYNWAVE. Default: DYNWAVE                                |
+------------------------+---------+---------------------------------------------------------------------------------------------+
| ``infiltration``       | string  | HORTON / MODIFIED_HORTON / GREEN_AMPT / MODIFIED_GREEN_AMPT / CURVE_NUMBER. Default: HORTON |
+------------------------+---------+---------------------------------------------------------------------------------------------+

Example Configuration
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

    {
        "name": "drainage_simulation",
        "type": "urban_drainage",
        "dataset": "drainage_network",
        "options": {
            "hydraulic_timestep": 60,
            "report_timestep": 300,
            "flow_units": "CMS",
            "flow_routing": "DYNWAVE",
            "infiltration": "HORTON"
        }
    }

Other Considerations
--------------------

Names, IDs and References
^^^^^^^^^^^^^^^^^^^^^^^^^

SWMM identifies objects by name. The model derives each SWMM name from the Movici
entity id (cast to a string) with a per-type prefix, so names are unique across
entity groups and link endpoints / subcatchment outlets resolve unambiguously:
``J`` junctions, ``OF`` outfalls, ``ST`` storage, ``C`` conduits, ``PU`` pumps,
``OR`` orifices, ``W`` weirs, ``OU`` outlets, ``S`` subcatchments and ``RG`` rain
gages (e.g. junction id 12 becomes ``J12``).

Units
^^^^^

Units follow SWMM's unit system, which is selected by ``flow_units``: the metric
``CMS`` / ``LPS`` / ``MLD`` use metres, m³/s and millimetres; the US
``CFS`` / ``GPM`` / ``MGD`` use feet, ft³/s and inches. The metric ``CMS`` default
is assumed throughout this page. When importing data, make sure depths, lengths
and rates match the configured unit system.

Notes
-----

* Link velocity is not published; the Froude number is published instead.
* SWMM advances in whole seconds, so the smallest meaningful step is 1 second.
* Existing SWMM ``.inp`` files can be converted to Movici datasets with the
  ``"swmm"`` dataset-creator source; the runtime model reads Movici data only.

Config Schema Reference
-----------------------

UrbanDrainageConfig
^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``dataset``: ``string`` Name of the urban_drainage_network dataset |required|
  | ``options``: :ref:`UrbanDrainageOptions` SWMM simulation options

.. _UrbanDrainageOptions:

UrbanDrainageOptions
^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``hydraulic_timestep``: ``number`` SWMM routing step in seconds (default: 60)
  | ``report_timestep``: ``number`` Report / wake cadence in seconds (default: 300)
  | ``flow_units``: ``string`` Flow units: CMS / LPS / MLD / CFS / GPM / MGD (default: CMS)
  | ``flow_routing``: ``string`` Routing method: STEADY / KINWAVE / DYNWAVE (default: DYNWAVE)
  | ``infiltration``: ``string`` Infiltration model (default: HORTON)
