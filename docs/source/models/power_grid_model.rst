.. |required| replace:: (**required**)

.. _power-grid-model:

Power Grid Calculation Model
============================

The power grid calculation model (``"power_grid_calculation"``) wraps the
`power-grid-model <https://power-grid-model.readthedocs.io/>`_ (PGM) C++ solver to
provide an idiomatic Movici interface for steady-state electrical network analysis.
The model processes networks containing Nodes, Lines, Cables, Transformers,
Three-Winding Transformers, Loads, Generators, Sources, Shunts, Sensors, Faults and
Tap Regulators, with all data described in terms of Movici entities and attributes.

The same model object supports three distinct calculation types — **power flow**,
**state estimation** and **short circuit** — selected through the model config.

Use cases include:

* Computing voltages, currents and power flows under varying load/generation scenarios
* Checking bus voltages and line loading against operational limits
* Estimating the most likely network state from (noisy) sensor measurements
* Computing fault currents for protection design and equipment rating

Goals
-----

* The data model is as much as possible described in terms of entities and attributes
* Each electrical component type maps onto a dedicated entity group whose attributes
  mirror the corresponding power-grid-model component fields
* Calculation- and solver-related options (calculation type, algorithm, symmetry, tap
  changing) are stored in the model config, not in the dataset
* It is a nice-to-have if the data model is compatible with other Movici network tooling,
  such as the ``shortest_path`` model, by reusing ``topology`` and ``connection`` attributes

Limitations
-----------

* Short-circuit results are produced per phase (shape ``(n, 3)``) but only **phase A** is
  written back to Movici attributes (see :ref:`pgm-power-flow-vs-short-circuit`)
* Only **symmetric** power-flow / state-estimation outputs are published; asymmetric
  (per-phase) outputs are not surfaced as separate attributes
* Time patterns are not part of the model. Values that change over time (e.g. a load
  profile) should be produced by another model, such as a tape player, and fed in through
  the ``SUB`` attributes
* The network topology is fixed at initialization. Loads, generation and sensor
  measurements can change between steps, but components cannot be added or removed

Calculation Types
-----------------

The calculation type is selected with the model config ``calculation_type`` key. It
determines which solver routine runs and which entity groups must be present.

.. list-table::
   :header-rows: 1
   :widths: 22 44 34

   * - Type
     - Computes
     - Requires
   * - ``power_flow``
     - Steady-state voltages, branch power flows, currents and loading
     - At least one source (slack bus)
   * - ``state_estimation``
     - Most-likely network state fitted to sensor measurements
     - At least one voltage, power or current sensor
   * - ``short_circuit``
     - Fault currents and per-phase voltages for a defined fault
     - At least one fault (and a source)

Model Characteristics
---------------------

The power grid model is a **steady-state** model. Its output state depends only on its
input state: if no input changes, the output does not change either. Compare this to a
transient model (such as the WNTR drinking water model), whose output can keep evolving
even when its input is constant. In general the output :math:`Y` can be described as

.. math::

  Y_{t_{n}} = F(X_{t_{n}})

with:

| :math:`Y_{t_{n}}`: Model output state at :math:`t_{n}` (voltages, currents, power flows)
| :math:`F`: The power-grid-model calculation
| :math:`X_{t_{n}}`: Model input state at :math:`t_{n}` (loads, generation, measurements)

Because there is no internal time-dependent state, the model can recompute the full
network solution on every update. Incoming changes (new load values, generation setpoints
or sensor measurements) are applied to the live PGM model first, and then a fresh
calculation is run.

.. note:: Source Required

   At least one ``electrical_source_entities`` entity (the slack bus) must be defined, or
   network construction raises a ``ValueError``. The source fixes the voltage reference for
   power flow and provides the equivalent grid impedance (``short_circuit_power``,
   ``rx_ratio``) for short-circuit analysis.

How It Works
------------

1. At ``setup``, all electrical entity groups are registered. Only the node group is
   mandatory in the dataset; every other group is optional and simply contributes nothing
   when absent.
2. At ``initialize``, each entity group is handed to a dedicated **processor** that builds
   the corresponding power-grid-model input array. The arrays are concatenated per PGM
   component type and a single ``PowerGridModel`` is constructed.
3. On each ``update``, processors with subscribable attributes build sparse **update
   arrays** for the elements whose load / generation / measurement values changed, and
   these are applied to the live PGM model.
4. The configured calculation (power flow, state estimation or short circuit) is run.
5. Results are written back to the ``PUB`` attributes of each entity group.

.. note:: Processor Architecture

   Each Movici entity type maps to one processor (e.g. ``NodeProcessor``,
   ``TransformerProcessor``, ``FaultProcessor``). Several processors may share one PGM
   component: nodes and virtual nodes both build PGM ``node`` arrays, and lines, cables
   and links all build PGM ``line`` arrays. The wrapper concatenates them transparently.
   Entity IDs are used directly as PGM component IDs, since IDs are unique within a dataset.

.. note:: Virtual Nodes and Links

   ``electrical_virtual_node_entities`` and ``electrical_link_entities`` mirror the
   virtual-node / virtual-link pattern from traffic assignment. Virtual nodes are merged
   with regular nodes when building the PGM ``node`` component. Links carry no electrical
   parameters and are converted to **near-zero-impedance** PGM lines
   (``r1 = x1 = 1e-6``), so they connect virtual nodes to the main network without an
   appreciable voltage drop.

Data Model
----------

The electrical network data model can be described as follows. Unless noted otherwise,
all quantities are in SI units: voltage in V, current in A, active power in W, reactive
power in VAr, apparent power in VA, resistance/reactance in :math:`\Omega`, capacitance
in F, conductance/susceptance in S, and angles in radians.

Nodes
^^^^^

``electrical_node_entities``

Nodes are the buses of the electrical network — the connection points where lines,
transformers and appliances meet. Nodes derive from ``PointEntity``. Their geometry
(``geometry.x/y/z``) is not used by the calculation and is excluded from the model.

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``electrical.rated_voltage``                   | INIT        | Rated (nominal) line voltage of the bus (V,            |
|                                                |             | ``u_rated``)                                           |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.voltage_pu``                      | PUB         | Voltage magnitude in per-unit of the rated voltage     |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.voltage_angle``                   | PUB         | Voltage angle (rad)                                    |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.voltage``                         | PUB         | Absolute voltage magnitude (V)                         |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.active_power``                    | PUB         | Net active power injected at the node (W). Not         |
|                                                |             | available in short-circuit results                     |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reactive_power``                  | PUB         | Net reactive power injected at the node (VAr). Not     |
|                                                |             | available in short-circuit results                     |
+------------------------------------------------+-------------+--------------------------------------------------------+

Virtual Nodes
^^^^^^^^^^^^^

``electrical_virtual_node_entities``

Virtual nodes are conceptual connection points to the external grid where sources attach.
They have the same attributes as regular nodes but derive from a plain ``EntityGroup`` and
may not carry geometry. During network construction they are merged with the regular nodes.

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``electrical.rated_voltage``                   | INIT        | Rated (nominal) voltage of the virtual bus (V)         |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.voltage_pu``                      | PUB         | Voltage magnitude in per-unit                          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.voltage_angle``                   | PUB         | Voltage angle (rad)                                    |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.voltage``                         | PUB         | Absolute voltage magnitude (V)                         |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.active_power``                    | PUB         | Net active power injected (W)                          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reactive_power``                  | PUB         | Net reactive power injected (VAr)                      |
+------------------------------------------------+-------------+--------------------------------------------------------+

Lines
^^^^^

``electrical_line_entities``

Lines are branches that transport power between two nodes, characterised by their
series impedance and shunt capacitance. Lines derive from ``LinkEntity``.

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``topology.from_node_id``                      | INIT        | Node id on the from side (from ``LinkEntity``)         |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``topology.to_node_id``                        | INIT        | Node id on the to side (from ``LinkEntity``)           |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.resistance``                      | INIT        | Series resistance (:math:`\Omega`, ``r1``)             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reactance``                       | INIT        | Series reactance (:math:`\Omega`, ``x1``)              |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.capacitance``                     | INIT        | Shunt capacitance (F, ``c1``)                          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tan_delta``                       | INIT        | Loss tangent of the shunt capacitance (``tan1``)       |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.rated_current``                   | OPT         | Rated current (A, ``i_n``). Used to compute            |
|                                                |             | ``loading``. When omitted, no current limit is applied |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.from_status``                     | OPT         | Whether the from end is connected (1) or open (0).     |
|                                                |             | Default: 1                                             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.to_status``                       | OPT         | Whether the to end is connected (1) or open (0).       |
|                                                |             | Default: 1                                             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.current_from``                    | PUB         | Current at the from end (A)                            |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.current_to``                      | PUB         | Current at the to end (A)                              |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.power_from``                      | PUB         | Active power at the from end (W). Not in short-circuit |
|                                                |             | results                                                |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.power_to``                        | PUB         | Active power at the to end (W). Not in short-circuit   |
|                                                |             | results                                                |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reactive_power_from``             | PUB         | Reactive power at the from end (VAr). Not in short-    |
|                                                |             | circuit results                                        |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reactive_power_to``               | PUB         | Reactive power at the to end (VAr). Not in short-      |
|                                                |             | circuit results                                        |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.loading``                         | PUB         | Loading as a fraction of rated current (0-1+). Not in  |
|                                                |             | short-circuit results                                  |
+------------------------------------------------+-------------+--------------------------------------------------------+

Cables
^^^^^^

``electrical_cable_entities``

Cables are underground lines. They have the same electrical characteristics and the same
attributes as lines, and are treated identically to lines in the calculation. They exist
as a separate entity group purely so that overhead lines and underground cables can be
modelled and styled distinctly.

See :ref:`the Lines table <power-grid-model>` above — the attribute set is identical.

Links
^^^^^

``electrical_link_entities``

Links are zero-impedance connections, typically tying a virtual node to the main network.
They carry no electrical parameters and are converted internally to near-zero-impedance
lines. Links derive from ``LinkEntity``.

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``topology.from_node_id``                      | INIT        | Node id on the from side (from ``LinkEntity``)         |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``topology.to_node_id``                        | INIT        | Node id on the to side (from ``LinkEntity``)           |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.from_status``                     | OPT         | Whether the from end is connected (1) or open (0).     |
|                                                |             | Default: 1                                             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.to_status``                       | OPT         | Whether the to end is connected (1) or open (0).       |
|                                                |             | Default: 1                                             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.current_from``                    | PUB         | Current at the from end (A)                            |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.current_to``                      | PUB         | Current at the to end (A)                              |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.power_from``                      | PUB         | Active power at the from end (W)                       |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.power_to``                        | PUB         | Active power at the to end (W)                         |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reactive_power_from``             | PUB         | Reactive power at the from end (VAr)                   |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reactive_power_to``               | PUB         | Reactive power at the to end (VAr)                     |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.loading``                         | PUB         | Loading fraction (typically near zero for links)       |
+------------------------------------------------+-------------+--------------------------------------------------------+

Transformers (Two-Winding)
^^^^^^^^^^^^^^^^^^^^^^^^^^

``electrical_transformer_entities``

A two-winding transformer connects two nodes at (potentially) different voltage levels and
can change voltage via a tap changer. Transformers derive from ``LinkEntity``. The
short-circuit voltage (``uk``) and copper loss (``pk``) are standard nameplate parameters
from the transformer's short-circuit test.

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``topology.from_node_id``                      | INIT        | Node id on the from (primary) side                     |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``topology.to_node_id``                        | INIT        | Node id on the to (secondary) side                     |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.primary_voltage``                 | INIT        | Rated voltage of the from winding (V, ``u1``)          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.secondary_voltage``               | INIT        | Rated voltage of the to winding (V, ``u2``)            |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.rated_power``                     | INIT        | Rated apparent power (VA, ``sn``)                      |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.short_circuit_voltage``           | INIT        | Relative short-circuit voltage (p.u., ``uk``)          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.copper_loss``                     | INIT        | Load (copper) loss at rated power (W, ``pk``)          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.no_load_current``                 | INIT        | Relative no-load (magnetising) current (p.u., ``i0``)  |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.no_load_loss``                    | INIT        | No-load (iron) loss (W, ``p0``)                        |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.winding_from``                    | OPT         | From-side winding connection (enum, see Enumerations). |
|                                                |             | Default: 1 (wye_n)                                     |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.winding_to``                      | OPT         | To-side winding connection (enum). Default: 1 (wye_n)  |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.clock``                           | OPT         | Clock number / vector-group phase shift (0-12).        |
|                                                |             | Default: 0                                             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tap_side``                        | OPT         | Side the tap changer is on (0=from, 1=to). Default: 0  |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tap_position``                    | OPT         | Current tap position. Default: 0                       |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tap_min``                         | OPT         | Tap position at minimum voltage. Default: 0            |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tap_max``                         | OPT         | Tap position at maximum voltage. Default: 0            |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tap_nom``                         | OPT         | Nominal tap position. Default: 0                       |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tap_size``                        | OPT         | Voltage step per tap position (V). Default: 0          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.from_status``                     | OPT         | From-side connection status. Default: 1                |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.to_status``                       | OPT         | To-side connection status. Default: 1                  |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.current_from``                    | PUB         | Current at the from side (A)                           |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.current_to``                      | PUB         | Current at the to side (A)                             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.power_from``                      | PUB         | Active power at the from side (W). Not in short-       |
|                                                |             | circuit results                                        |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.power_to``                        | PUB         | Active power at the to side (W). Not in short-circuit  |
|                                                |             | results                                                |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reactive_power_from``             | PUB         | Reactive power at the from side (VAr). Not in short-   |
|                                                |             | circuit results                                        |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reactive_power_to``               | PUB         | Reactive power at the to side (VAr). Not in short-     |
|                                                |             | circuit results                                        |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.loading``                         | PUB         | Loading as a fraction of rated power. Not in short-    |
|                                                |             | circuit results                                        |
+------------------------------------------------+-------------+--------------------------------------------------------+

Three-Winding Transformers
^^^^^^^^^^^^^^^^^^^^^^^^^^

``electrical_three_winding_transformer_entities``

A three-winding transformer connects **three** nodes at potentially different voltage
levels (PGM component ``three_winding_transformer``). It is modelled internally as three
windings joined in a star, with the short-circuit voltage and copper loss given **per
winding pair** (1-2, 1-3, 2-3). Unlike the two-winding transformer, it does not derive
from ``LinkEntity`` — it references its three nodes explicitly via
``electrical.node_1_id`` / ``node_2_id`` / ``node_3_id``.

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``electrical.node_1_id``                       | INIT        | Node id of winding 1 (primary)                         |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.node_2_id``                       | INIT        | Node id of winding 2 (secondary)                       |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.node_3_id``                       | INIT        | Node id of winding 3 (tertiary)                        |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.primary_voltage``                 | INIT        | Rated voltage of winding 1 (V, ``u1``)                 |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.secondary_voltage``               | INIT        | Rated voltage of winding 2 (V, ``u2``)                 |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tertiary_voltage``                | INIT        | Rated voltage of winding 3 (V, ``u3``)                 |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.rated_power_1``                   | INIT        | Rated apparent power of winding 1 (VA, ``sn_1``)       |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.rated_power_2``                   | INIT        | Rated apparent power of winding 2 (VA, ``sn_2``)       |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.rated_power_3``                   | INIT        | Rated apparent power of winding 3 (VA, ``sn_3``)       |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.short_circuit_voltage_12``        | INIT        | Relative short-circuit voltage, pair 1-2 (p.u.,        |
|                                                |             | ``uk_12``)                                             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.short_circuit_voltage_13``        | INIT        | Relative short-circuit voltage, pair 1-3 (p.u.,        |
|                                                |             | ``uk_13``)                                             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.short_circuit_voltage_23``        | INIT        | Relative short-circuit voltage, pair 2-3 (p.u.,        |
|                                                |             | ``uk_23``)                                             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.copper_loss_12``                  | INIT        | Copper loss, pair 1-2 (W, ``pk_12``)                   |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.copper_loss_13``                  | INIT        | Copper loss, pair 1-3 (W, ``pk_13``)                   |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.copper_loss_23``                  | INIT        | Copper loss, pair 2-3 (W, ``pk_23``)                   |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.no_load_current``                 | INIT        | Relative no-load current (p.u., ``i0``)                |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.no_load_loss``                    | INIT        | No-load loss (W, ``p0``)                               |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.status_1``                        | OPT         | Connection status of winding 1. Default: 1             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.status_2``                        | OPT         | Connection status of winding 2. Default: 1             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.status_3``                        | OPT         | Connection status of winding 3. Default: 1             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.winding_1``                       | OPT         | Winding 1 connection type (enum). Default: 1 (wye_n)   |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.winding_2``                       | OPT         | Winding 2 connection type (enum). Default: 1 (wye_n)   |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.winding_3``                       | OPT         | Winding 3 connection type (enum). Default: 1 (wye_n)   |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.clock_12``                        | OPT         | Clock number of winding 2 relative to 1 (0-12).        |
|                                                |             | Default: 0                                             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.clock_13``                        | OPT         | Clock number of winding 3 relative to 1 (0-12).        |
|                                                |             | Default: 0                                             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tap_side``                        | OPT         | Side the tap changer is on. Default: 0                 |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tap_position``                    | OPT         | Current tap position. Default: 0                       |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tap_min``                         | OPT         | Tap position at minimum voltage. Default: 0            |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tap_max``                         | OPT         | Tap position at maximum voltage. Default: 0            |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tap_nom``                         | OPT         | Nominal tap position. Default: 0                       |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tap_size``                        | OPT         | Voltage step per tap position (V). Default: 0          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.current_1``                       | PUB         | Current at winding 1 (A, ``i_1``)                      |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.current_2``                       | PUB         | Current at winding 2 (A, ``i_2``)                      |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.current_3``                       | PUB         | Current at winding 3 (A, ``i_3``)                      |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.power_1``                         | PUB         | Active power at winding 1 (W). Not in short-circuit    |
|                                                |             | results                                                |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.power_2``                         | PUB         | Active power at winding 2 (W). Not in short-circuit    |
|                                                |             | results                                                |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.power_3``                         | PUB         | Active power at winding 3 (W). Not in short-circuit    |
|                                                |             | results                                                |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reactive_power_1``                | PUB         | Reactive power at winding 1 (VAr). Not in short-       |
|                                                |             | circuit results                                        |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reactive_power_2``                | PUB         | Reactive power at winding 2 (VAr). Not in short-       |
|                                                |             | circuit results                                        |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reactive_power_3``                | PUB         | Reactive power at winding 3 (VAr). Not in short-       |
|                                                |             | circuit results                                        |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.loading``                         | PUB         | Loading as a fraction of rated power. Not in short-    |
|                                                |             | circuit results                                        |
+------------------------------------------------+-------------+--------------------------------------------------------+

.. note:: Per-Pair Parameters

   The short-circuit voltage and copper loss are given for each winding **pair**
   (``_12``, ``_13``, ``_23``), because the short-circuit test for a three-winding
   transformer energises one winding, shorts a second and leaves the third open. From
   these three pairwise measurements the solver derives the three per-winding star
   impedances. The clock number is only given relative to winding 1 (``clock_12``,
   ``clock_13``); ``clock_23`` would be redundant since
   ``clock_23 = (clock_13 - clock_12) mod 12``.

Loads
^^^^^

``electrical_load_entities``

A load is a power consumer connected to a single node (PGM component ``sym_load``). Its
active and reactive power are subscribable, so they can be driven dynamically by another
model during the simulation.

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``connection.to_id``                           | INIT        | Id of the node the load is connected to                |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.status``                          | OPT         | Whether the load is on (1) or off (0). Default: 1      |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.load_type``                       | OPT         | Load behaviour (enum: 0=const power, 1=const           |
|                                                |             | impedance, 2=const current). Default: 0                |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.active_power_specified``          | SUB         | Specified active power consumption (W)                 |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reactive_power_specified``        | SUB         | Specified reactive power consumption (VAr)             |
+------------------------------------------------+-------------+--------------------------------------------------------+

Generators
^^^^^^^^^^

``electrical_generator_entities``

A generator is a power producer connected to a single node (PGM component ``sym_gen``).
It mirrors the load entity exactly, but injects rather than consumes power. Its values are
subscribable for dynamic updates.

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``connection.to_id``                           | INIT        | Id of the node the generator is connected to           |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.status``                          | OPT         | Whether the generator is on (1) or off (0). Default: 1 |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.load_type``                       | OPT         | Generation behaviour (enum, reuses the load-type       |
|                                                |             | enum). Default: 0                                      |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.active_power_specified``          | SUB         | Specified active power generation (W)                  |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reactive_power_specified``        | SUB         | Specified reactive power generation (VAr)              |
+------------------------------------------------+-------------+--------------------------------------------------------+

Sources
^^^^^^^

``electrical_source_entities``

A source is the connection to the external grid — the **slack bus** that fixes the voltage
reference for power flow. At least one source is required. For short-circuit analysis the
source also provides the equivalent external-grid impedance through its short-circuit power
and R/X ratio.

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``connection.to_id``                           | INIT        | Id of the node the source is connected to              |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reference_voltage``               | INIT        | Reference voltage magnitude (p.u., ``u_ref``)          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.status``                          | OPT         | Whether the source is on (1) or off (0). Default: 1    |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.reference_angle``                 | OPT         | Reference voltage angle (rad). Default: 0              |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.short_circuit_power``             | OPT         | Short-circuit apparent power of the external grid (VA, |
|                                                |             | ``sk``). Default: 1e10                                 |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.rx_ratio``                        | OPT         | R/X ratio of the external-grid impedance. Default: 0.1 |
+------------------------------------------------+-------------+--------------------------------------------------------+

Shunts
^^^^^^

``electrical_shunt_entities``

A shunt is a node-connected element used for reactive-power compensation (a capacitor or
reactor bank), described by its admittance.

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``connection.to_id``                           | INIT        | Id of the node the shunt is connected to               |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.conductance``                     | INIT        | Shunt conductance (S, ``g1``)                          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.susceptance``                     | INIT        | Shunt susceptance (S, ``b1``)                          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.status``                          | OPT         | Whether the shunt is on (1) or off (0). Default: 1     |
+------------------------------------------------+-------------+--------------------------------------------------------+

Sensors (State Estimation)
^^^^^^^^^^^^^^^^^^^^^^^^^^

Sensors supply measurements for ``state_estimation`` calculations. There are three types —
voltage, power and current sensors. Each measurement comes with a standard deviation
(``*_sigma``) describing its uncertainty. The measured values are subscribable.

**Voltage sensors** ``electrical_voltage_sensor_entities``

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``connection.to_id``                           | INIT        | Id of the node being measured                          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.voltage_sigma``                   | INIT        | Standard deviation of the voltage measurement (V)      |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.measured_voltage``                | SUB         | Measured voltage (V)                                   |
+------------------------------------------------+-------------+--------------------------------------------------------+

**Power sensors** ``electrical_power_sensor_entities``

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``connection.to_id``                           | INIT        | Id of the measured object (node, branch or appliance)  |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.measured_terminal_type``          | INIT        | What the sensor is attached to (enum, see              |
|                                                |             | Enumerations)                                          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.power_sigma``                     | INIT        | Standard deviation of the power measurement (VA)       |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.measured_active_power``           | SUB         | Measured active power (W)                              |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.measured_reactive_power``         | SUB         | Measured reactive power (VAr)                          |
+------------------------------------------------+-------------+--------------------------------------------------------+

**Current sensors** ``electrical_current_sensor_entities``

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``connection.to_id``                           | INIT        | Id of the measured object                              |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.measured_terminal_type``          | INIT        | What the sensor is attached to (enum)                  |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.current_sigma``                   | INIT        | Standard deviation of the current measurement (A)      |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.angle_measurement_type``          | INIT        | Angle reference (0=local, 1=global)                    |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.current_angle_sigma``             | INIT        | Standard deviation of the current angle (rad)          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.measured_current``                | SUB         | Measured current magnitude (A)                         |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.measured_current_angle``          | SUB         | Measured current angle (rad)                           |
+------------------------------------------------+-------------+--------------------------------------------------------+

Faults (Short Circuit)
^^^^^^^^^^^^^^^^^^^^^^

``electrical_fault_entities``

A fault defines a short circuit at a specific location for ``short_circuit`` analysis. The
faulted object is a node or a branch. The fault type and (optionally) the affected phase
determine whether the fault is balanced (three-phase) or unbalanced.

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``connection.to_id``                           | INIT        | Id of the faulted object (node or branch)              |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.fault_type``                      | INIT        | Fault type (enum, see Enumerations)                    |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.status``                          | OPT         | Whether the fault is active (1) or not (0). Default: 1 |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.fault_phase``                     | OPT         | Affected phase(s) (enum). Default: 0 (abc)             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.fault_resistance``                | OPT         | Fault resistance (:math:`\Omega`, ``r_f``). Default: 0 |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.fault_reactance``                 | OPT         | Fault reactance (:math:`\Omega`, ``x_f``). Default: 0  |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.fault_current``                   | PUB         | Resulting fault current magnitude (A, ``i_f``)         |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.fault_current_angle``             | PUB         | Resulting fault current angle (rad)                    |
+------------------------------------------------+-------------+--------------------------------------------------------+

Tap Regulators
^^^^^^^^^^^^^^

``electrical_tap_regulator_entities``

A tap regulator automatically adjusts a transformer's tap position to keep a controlled
voltage within a band (PGM component ``transformer_tap_regulator``). It regulates an
existing two- or three-winding transformer, referenced by id.

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``connection.to_id``                           | INIT        | Id of the regulated transformer                        |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.regulator_control_side``          | INIT        | Side whose voltage is controlled (0=from, 1=to)        |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.voltage_setpoint``                | INIT        | Target voltage (V, ``u_set``)                          |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.voltage_band``                    | INIT        | Allowed voltage band around the setpoint (V,           |
|                                                |             | ``u_band``)                                            |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.status``                          | OPT         | Whether the regulator is on (1) or off (0). Default: 1 |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.line_drop_compensation_r``        | OPT         | Line-drop compensation resistance (:math:`\Omega`).    |
|                                                |             | Default: 0                                             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.line_drop_compensation_x``        | OPT         | Line-drop compensation reactance (:math:`\Omega`).     |
|                                                |             | Default: 0                                             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tap_position``                    | PUB         | Resulting tap position chosen by the regulator         |
+------------------------------------------------+-------------+--------------------------------------------------------+

.. note:: Automatic Tap Changing

   When tap regulators are present and ``tap_changing`` is left unset in the model config,
   the model automatically enables the ``any_valid_tap`` strategy. To run a power flow with
   the tap changers held fixed even though regulators exist, set ``tap_changing`` to
   ``"disabled"`` explicitly.

.. _pgm-power-flow-vs-short-circuit:

Power Flow vs Short Circuit
---------------------------

Power flow and short circuit run on the same dataset and the same underlying model object,
but they answer fundamentally different questions.

**Power flow** (``calculation_type: power_flow``) determines the steady-state operating
point of a normally energised network. Given the loads, generation and a source that fixes
the reference voltage, it solves the non-linear power-balance equations for the voltage at
every bus and the power flow on every branch. The default ``newton_raphson`` and the
``iterative_current`` algorithms solve these non-linear equations iteratively; the
``linear`` and ``linear_current`` algorithms solve a linearised (constant-impedance /
constant-current) approximation in a single pass, trading accuracy for speed. Power-flow
results include voltages, branch active/reactive power, currents and ``loading``
(fraction of rated). By default the calculation is **symmetric** (balanced
positive-sequence); even asymmetric loads are collapsed to a balanced equivalent. It
answers: *"what does the network look like in normal operation?"*

**Short circuit** (``calculation_type: short_circuit``) determines the currents and
voltages produced when a fault occurs at a specific location. Instead of loads, the inputs
are one or more fault definitions (faulted object, fault type, fault impedance) together
with the source's short-circuit power and R/X ratio. The pre-fault load flow is discarded:
PGM uses the IEC 60909 equivalent-voltage-source method, applying a single equivalent
source at the fault location. Unbalanced fault types (single-phase-to-ground, two-phase,
two-phase-to-ground) couple the positive-, negative- and zero-sequence networks via
symmetrical components, while a balanced three-phase fault is driven by the
positive-sequence network alone. Short-circuit results are fault currents and per-phase
voltages — there is **no active power, reactive power or loading** in a short-circuit
result. It answers: *"how much current flows if it faults here?"* — the basis for
protection-relay settings, circuit-breaker sizing and equipment ratings.

.. list-table::
   :header-rows: 1
   :widths: 22 39 39

   * - Aspect
     - Power flow
     - Short circuit
   * - Network state
     - Normal, energised, with loads
     - A fault applied at one location
   * - Drives the solution
     - Loads, generation, slack voltage
     - Equivalent voltage source at the fault; source ``sk`` / ``rx_ratio``
   * - Mathematics
     - Non-linear power balance (Newton-Raphson) or a linear approximation
     - Linear solution of the sequence networks (symmetrical components)
   * - Symmetry
     - Symmetric by default; asymmetric optional
     - Always solved per phase; shape ``(n, 3)``
   * - Key outputs
     - Voltages, branch P/Q, currents, ``loading``
     - ``fault_current`` and angle (no P/Q/loading)
   * - Required entities
     - Source
     - Fault(s) and a source

.. warning:: Short-Circuit Results Keep Phase A Only

   The power-grid-model always computes short-circuit results per phase (shape
   ``(n, 3)``), even for a balanced three-phase fault. The Movici model writes back only
   **phase A** (the first phase) to the per-entity attributes. For a balanced three-phase
   fault this is exact; for unbalanced faults the published current/voltage is the phase-A
   value only.

.. note:: State Estimation

   The third calculation type, ``state_estimation``, is neither of the above: given (noisy)
   sensor measurements it computes the most likely network state. It requires at least one
   voltage, power or current sensor.

Configuration Options
---------------------

All calculation- and solver-related options are stored in the **model config** (not the
dataset).

+--------------------------+-----------+---------------------------------------------------------------------+
| Option                   | Type      | Description                                                         |
+==========================+===========+=====================================================================+
| ``dataset``              | string    | Name of the electrical network dataset |required|                   |
+--------------------------+-----------+---------------------------------------------------------------------+
| ``calculation_type``     | string    | ``power_flow`` (default), ``state_estimation`` or ``short_circuit`` |
+--------------------------+-----------+---------------------------------------------------------------------+
| ``algorithm``            | string    | Power-flow algorithm: ``newton_raphson`` (default),                 |
|                          |           | ``iterative_current``, ``linear`` or ``linear_current``             |
+--------------------------+-----------+---------------------------------------------------------------------+
| ``symmetric``            | boolean   | Use the symmetric (balanced) calculation. Default: ``true``         |
+--------------------------+-----------+---------------------------------------------------------------------+
| ``tap_changing``         | string    | Automatic tap-changing strategy: ``disabled``, ``any_valid_tap``,   |
|                          |           | ``min_voltage_tap``, ``max_voltage_tap`` or ``fast_any_tap``. When  |
|                          |           | unset, auto-detected from the presence of tap regulators            |
+--------------------------+-----------+---------------------------------------------------------------------+

Example model config for a power-flow calculation:

.. code-block:: json

    {
        "name": "grid_power_flow",
        "type": "power_grid_calculation",
        "dataset": "electrical_network",
        "calculation_type": "power_flow",
        "algorithm": "newton_raphson",
        "symmetric": true
    }

Example model config for a short-circuit calculation:

.. code-block:: json

    {
        "name": "grid_short_circuit",
        "type": "power_grid_calculation",
        "dataset": "electrical_network",
        "calculation_type": "short_circuit"
    }

Enumerations
------------

Several integer attributes encode enumerations matching the power-grid-model definitions.

**Winding connection** (``winding_*``)

+----------+------------------------------------------+
| Value    | Meaning                                  |
+==========+==========================================+
| 0        | ``wye``                                  |
+----------+------------------------------------------+
| 1        | ``wye_n`` (default)                      |
+----------+------------------------------------------+
| 2        | ``delta``                                |
+----------+------------------------------------------+
| 3        | ``zigzag``                               |
+----------+------------------------------------------+
| 4        | ``zigzag_n``                             |
+----------+------------------------------------------+

**Load / generation type** (``load_type``)

+----------+------------------------------------------+
| Value    | Meaning                                  |
+==========+==========================================+
| 0        | ``const_power`` (default)                |
+----------+------------------------------------------+
| 1        | ``const_impedance``                      |
+----------+------------------------------------------+
| 2        | ``const_current``                        |
+----------+------------------------------------------+

**Fault type** (``fault_type``)

+----------+------------------------------------------+
| Value    | Meaning                                  |
+==========+==========================================+
| 0        | ``three_phase`` (balanced)               |
+----------+------------------------------------------+
| 1        | ``single_phase_to_ground``               |
+----------+------------------------------------------+
| 2        | ``two_phase``                            |
+----------+------------------------------------------+
| 3        | ``two_phase_to_ground``                  |
+----------+------------------------------------------+

**Fault phase** (``fault_phase``)

+------------+------------------------------------------+
| Value      | Meaning                                  |
+============+==========================================+
| 0          | ``abc`` (default)                        |
+------------+------------------------------------------+
| 1 / 2 / 3  | ``a`` / ``b`` / ``c``                    |
+------------+------------------------------------------+
| 4 / 5 / 6  | ``ab`` / ``ac`` / ``bc``                 |
+------------+------------------------------------------+

**Measured terminal type** (``measured_terminal_type``)

+------------+--------------------------------------------------------------+
| Value      | Meaning                                                      |
+============+==============================================================+
| 0 / 1      | ``branch_from`` / ``branch_to``                              |
+------------+--------------------------------------------------------------+
| 2          | ``source``                                                   |
+------------+--------------------------------------------------------------+
| 3          | ``shunt``                                                    |
+------------+--------------------------------------------------------------+
| 4 / 5      | ``load`` / ``generator``                                     |
+------------+--------------------------------------------------------------+
| 6 / 7 / 8  | ``branch3_1`` / ``branch3_2`` / ``branch3_3`` (three-winding |
|            | transformer sides)                                           |
+------------+--------------------------------------------------------------+
| 9          | ``node``                                                     |
+------------+--------------------------------------------------------------+

Other Considerations
--------------------

Node and Object References
^^^^^^^^^^^^^^^^^^^^^^^^^^

Components reference the nodes (or objects) they attach to through different attributes,
depending on their entity type:

* Lines, cables, links and two-winding transformers use ``topology.from_node_id`` /
  ``topology.to_node_id`` (inherited from ``LinkEntity``)
* Three-winding transformers use ``electrical.node_1_id`` / ``node_2_id`` / ``node_3_id``
* Loads, generators, sources, shunts, sensors, faults and tap regulators use a single
  ``connection.to_id``

Entity IDs are used directly as power-grid-model component IDs. Because IDs are unique
within a dataset, no separate id mapping is needed.

Units
^^^^^

All quantities use SI units: V, A, W, VAr, VA, :math:`\Omega`, F, S and radians. Voltages
expressed in per-unit (``voltage_pu``, ``reference_voltage``, ``short_circuit_voltage``,
``no_load_current``) are relative to the relevant rated value. See
`power-grid-model: Components <https://power-grid-model.readthedocs.io/en/stable/user_manual/components.html>`_
for the full description of each component field.

Config Schema Reference
-----------------------

PowerGridConfig
^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``dataset``: ``string`` Name of the electrical network dataset |required|
  | ``calculation_type``: ``string`` One of ``power_flow``, ``state_estimation``, ``short_circuit`` (default: ``power_flow``)
  | ``algorithm``: ``string`` One of ``newton_raphson``, ``iterative_current``, ``linear``, ``linear_current`` (default: ``newton_raphson``)
  | ``symmetric``: ``boolean`` Use the symmetric (balanced) calculation (default: ``true``)
  | ``tap_changing``: ``string`` One of ``disabled``, ``any_valid_tap``, ``min_voltage_tap``, ``max_voltage_tap``, ``fast_any_tap``
