.. |required| replace:: (**required**)

.. _power-grid-cascade:

Power Grid Cascade Model
========================

The power grid cascade model (``"power_grid_cascade"``) simulates the electrical
consequences of an external hazard — flooding, earthquake, subsidence — that causes short
circuits in a distribution grid. Where the
:ref:`power grid calculation model <power-grid-model>` runs *one* calculation per update,
the cascade model runs a **sequence**: a short circuit, the protection relays that respond
to it, and then a power flow on whatever grid survives.

It is normally paired with the :ref:`fault activation model <power-grid-fault-activation>`,
which turns hazard exposure into active faults. Together they answer: *"this area floods —
which customers lose power?"*

Use cases include:

* Estimating the outage footprint of a flood, and how it grows as water rises
* Testing whether protection settings isolate a fault or de-energise half the city
* Identifying grid locations where a single fault has a disproportionate impact

Goals
-----

* The model reuses the electrical data model of the :ref:`power grid calculation model
  <power-grid-model>` unchanged — the same entity groups and the same attributes
* Protection relays are described as ordinary Movici entities, so relay placement and
  settings are dataset properties rather than model configuration
* The model is hazard-agnostic: it reacts to fault status, not to what caused the fault

Limitations
-----------

* Protection is modelled as **definite-time overcurrent** only: a relay compares the
  short-circuit current at its side of a branch against a fixed pick-up current. Distance,
  differential and inverse-time characteristics are not modelled
* Relays are **latching**. A tripped relay stays tripped for the rest of the simulation;
  there is no auto-reclose and no repair
* Fault activation is likewise latching — a short circuit persists until repaired
* Only lines, cables, links and two-winding transformers can be protected. A relay on a
  three-winding transformer has no effect
* The whole cascade resolves inside a single timestamp; ``pick_up_time`` orders relays
  relative to one another but does not advance simulation time (see
  :ref:`below <pgm-cascade-timing>`)

Model Characteristics
---------------------

Like the power grid calculation model, each update is a **steady-state** solve. Unlike it,
the cascade model carries a small amount of **latching state** across timestamps: the set
of relays that have already tripped. Once a relay operates, its branch side stays open for
every subsequent update.

So the output is not a pure function of the current input. It depends on the input and on
the accumulated trip history:

.. math::

  Y_{t_{n}} = F(X_{t_{n}}, T_{t_{n}})

with:

| :math:`Y_{t_{n}}`: Model output at :math:`t_{n}` (voltages, currents, energised status)
| :math:`F`: The cascade (short circuit, trips, power flow)
| :math:`X_{t_{n}}`: Model input at :math:`t_{n}` (fault status, loads, generation)
| :math:`T_{t_{n}}`: The set of relays tripped at or before :math:`t_{n}`

This is what makes an outage *stick*: the grid does not recover when flood water recedes,
because the breakers stay open.

.. _pgm-cascade-timing:

.. note:: Why the Cascade Runs Inside One Timestamp

   Protection operates on sub-second timescales, well below the resolution of Movici's
   integer-second timeline. More importantly, *which relay trips first determines which
   relays trip at all*: a fast relay near the fault may clear it before a slower backup
   relay upstream ever sees sustained overcurrent. That ordering has to be resolved
   internally, so the entire short-circuit/trip sequence is completed within a single
   ``update()`` call.

   ``electrical.pick_up_time`` therefore expresses **relative priority** for selectivity,
   not a delay on the simulation timeline. No intermediate state is published: downstream
   models see the settled grid.

How It Works
------------

On every update:

1. Incoming changes — fault activations, load changes — are applied to the live
   power-grid-model network.
2. If no fault has ``electrical.status == 1``, the short-circuit stage is skipped
   entirely and the model proceeds straight to the power flow.
3. Otherwise a **short circuit** is calculated on the current topology.
4. Every untripped relay whose branch current exceeds its ``pick_up_current`` becomes a
   trip candidate. Among the candidates, only those with the **lowest** ``pick_up_time``
   actually operate — the selectivity rule.
5. Those relays open their protected branch side. The change is applied to the live
   network, published to the branch status attributes and recorded in the relay
   bookkeeping.
6. Steps 3-5 repeat until no further relay trips, or until ``max_cascade_iterations`` is
   reached (which logs a warning).
7. A **power flow** is run on the remaining, partially de-energised grid. Its results
   overwrite the node and branch values from the short circuit, and the per-node
   ``electrical.energized`` flag is published.

.. note:: Which Fault Currents Are Published

   ``electrical.fault_current`` comes from the **first** short-circuit round — the
   prospective fault current on the pre-trip topology, which is what the protection
   actually responded to. Later rounds are used only for trip decisions: once a fault is
   isolated its current drops to zero, and publishing that would be misleading.

   Node voltages and branch currents, by contrast, come from the final power flow, since
   those describe the settled operating state.

Data Model
----------

The cascade model registers the same entity groups as the
:ref:`power grid calculation model <power-grid-model>`, with the same attributes. See that
page for nodes, lines, cables, links, transformers, loads, generators, sources and faults.

Three differences apply.

Additional Entity Group: Branch Protection
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``electrical_branch_protection_entities``

A relay monitoring one side of one branch. Optional: without any relays the model still
runs, it simply never isolates anything.

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``electrical.protected_line``                  | INIT        | Id of the branch this relay protects (line, cable,     |
|                                                |             | link or two-winding transformer)                       |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.protected_side``                  | INIT        | Which side the relay measures and opens (enum          |
|                                                |             | ``branch_side``): 0 = from side, 1 = to side           |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.pick_up_current``                 | INIT        | Current above which the relay operates (A)             |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.pick_up_time``                    | OPT         | Relative operating time (s) used for selectivity: the  |
|                                                |             | lowest value among candidates trips first. Default: 0  |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.tripped``                         | PUB         | Whether this relay has operated (0/1). Latching        |
+------------------------------------------------+-------------+--------------------------------------------------------+

Additional Node Attribute
^^^^^^^^^^^^^^^^^^^^^^^^^

Both ``electrical_node_entities`` and ``electrical_virtual_node_entities`` gain one
published attribute:

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``electrical.energized``                       | PUB         | Whether the node is still connected to a source (0/1). |
|                                                |             | This is the outage indicator                           |
+------------------------------------------------+-------------+--------------------------------------------------------+

Changed Attribute Flags
^^^^^^^^^^^^^^^^^^^^^^^

Three attributes carry different flags than in the power grid calculation model, because
the cascade both reads and writes them:

+------------------------------------------------+---------------------+----------------------------------------------+
| Attribute                                      | Flags               | Why                                          |
+================================================+=====================+==============================================+
| ``electrical.from_status``                     | ``OPT`` → ``OPT``   | The model publishes breaker positions after  |
| ``electrical.to_status``                       | ``| PUB``           | a trip, on lines, cables, links and          |
| (on branches)                                  |                     | two-winding transformers                     |
+------------------------------------------------+---------------------+----------------------------------------------+
| ``electrical.status``                          | ``OPT`` → ``SUB``   | Fault status is driven by an external model  |
| (on faults)                                    |                     | and is required before the cascade can run   |
+------------------------------------------------+---------------------+----------------------------------------------+

Configuration Options
---------------------

+----------------------------+-----------+-------------------------------------------------------------------+
| Option                     | Type      | Description                                                       |
+============================+===========+===================================================================+
| ``dataset``                | string    | Name of the electrical network dataset |required|                 |
+----------------------------+-----------+-------------------------------------------------------------------+
| ``algorithm``              | string    | Power-flow algorithm: ``newton_raphson`` (default),               |
|                            |           | ``iterative_current``, ``linear`` or ``linear_current``           |
+----------------------------+-----------+-------------------------------------------------------------------+
| ``symmetric``              | boolean   | Use the symmetric (balanced) power flow. Default: ``true``.       |
|                            |           | ``false`` requires zero-sequence line/cable parameters            |
+----------------------------+-----------+-------------------------------------------------------------------+
| ``tap_changing``           | string    | Automatic tap-changing strategy for the power flow: ``disabled``, |
|                            |           | ``any_valid_tap``, ``min_voltage_tap``, ``max_voltage_tap`` or    |
|                            |           | ``fast_any_tap``. When unset, auto-detected                       |
+----------------------------+-----------+-------------------------------------------------------------------+
| ``max_cascade_iterations`` | integer   | Maximum short-circuit/trip rounds per update. Default: ``20``.    |
|                            |           | Exceeding it logs a warning and stops the loop                    |
+----------------------------+-----------+-------------------------------------------------------------------+
| ``per_phase_output``       | boolean   | Also publish the per-phase ``(3,)`` voltage and current           |
|                            |           | attributes alongside the scalar worst-phase ones.                 |
|                            |           | Default: ``false``                                                |
+----------------------------+-----------+-------------------------------------------------------------------+

Note that there is no ``calculation_type``: the cascade always runs a short circuit
followed by a power flow.

.. code-block:: json

    {
        "name": "grid_cascade",
        "type": "power_grid_cascade",
        "dataset": "power_grid_the_hague",
        "algorithm": "newton_raphson",
        "max_cascade_iterations": 20
    }

.. _power-grid-fault-activation:

Fault Activation Model
----------------------

The fault activation model (``"power_grid_fault_activation"``) is the bridge between a
hazard model and the cascade. It watches a per-node scalar attribute and activates the
fault attached to a node once that value crosses a threshold, by publishing
``electrical.status = 1`` on ``electrical_fault_entities``.

It is deliberately hazard-agnostic. The default monitored attribute is
``flooding.water_depth``, as published by the ``operational_status`` model, but any model
producing a per-node scalar — earthquake intensity, subsidence, temperature — can drive it
by pointing ``monitor_attribute`` at that attribute instead.

Activation is **latching**: a short circuit persists until repaired, so a fault stays
active even if the monitored value later drops back below the threshold.

Data Model
^^^^^^^^^^

The model reads one attribute from the monitored entity group and writes one attribute on
the faults. Each fault is linked to the node it monitors through ``connection.to_id``.

+------------------------------------------------+-------------+--------------------------------------------------------+
| Attribute                                      | Flags       | Description                                            |
+================================================+=============+========================================================+
| ``connection.to_id``                           | INIT        | On ``electrical_fault_entities``: the monitored node   |
+------------------------------------------------+-------------+--------------------------------------------------------+
| *the configured* ``monitor_attribute``         | SUB         | Per-node scalar driving activation. Default:           |
|                                                |             | ``flooding.water_depth``                               |
+------------------------------------------------+-------------+--------------------------------------------------------+
| ``electrical.status``                          | PUB         | Set to 1 when the threshold is exceeded. Latching      |
+------------------------------------------------+-------------+--------------------------------------------------------+

Configuration Options
^^^^^^^^^^^^^^^^^^^^^

+----------------------------+-----------+-------------------------------------------------------------------+
| Option                     | Type      | Description                                                       |
+============================+===========+===================================================================+
| ``dataset``                | string    | Name of the electrical network dataset |required|                 |
+----------------------------+-----------+-------------------------------------------------------------------+
| ``threshold``              | number    | The fault activates when the monitored value exceeds this         |
|                            |           | |required|                                                        |
+----------------------------+-----------+-------------------------------------------------------------------+
| ``monitor_entity_group``   | string    | Entity group holding the monitored attribute. Default:            |
|                            |           | ``electrical_node_entities``                                      |
+----------------------------+-----------+-------------------------------------------------------------------+
| ``monitor_attribute``      | string    | The per-node scalar to watch. Default:                            |
|                            |           | ``flooding.water_depth``                                          |
+----------------------------+-----------+-------------------------------------------------------------------+

.. code-block:: json

    {
        "name": "flood_faults",
        "type": "power_grid_fault_activation",
        "dataset": "power_grid_the_hague",
        "monitor_attribute": "flooding.water_depth",
        "threshold": 0.3
    }

Putting It Together
-------------------

A flood-outage scenario chains three models. The hazard model publishes water depth per
node; the fault activation model turns depth into active faults; the cascade model turns
faults into outages:

.. code-block:: json

    {
        "models": [
            {
                "name": "flood_faults",
                "type": "power_grid_fault_activation",
                "dataset": "power_grid_the_hague",
                "monitor_attribute": "flooding.water_depth",
                "threshold": 0.3
            },
            {
                "name": "grid_cascade",
                "type": "power_grid_cascade",
                "dataset": "power_grid_the_hague",
                "algorithm": "newton_raphson",
                "max_cascade_iterations": 50
            }
        ]
    }

The chain is driven entirely by attribute subscriptions: water depth changes activate
faults, activated faults trigger the cascade, and the cascade publishes
``electrical.energized`` per node, which downstream models can aggregate into an
affected-customer count.

Config Schema Reference
-----------------------

PowerGridCascadeConfig
^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``dataset``: ``string`` Name of the electrical network dataset |required|
  | ``algorithm``: ``string`` One of ``newton_raphson``, ``iterative_current``, ``linear``, ``linear_current`` (default: ``newton_raphson``)
  | ``symmetric``: ``boolean`` Use the symmetric (balanced) power flow (default: ``true``)
  | ``tap_changing``: ``string`` One of ``disabled``, ``any_valid_tap``, ``min_voltage_tap``, ``max_voltage_tap``, ``fast_any_tap``
  | ``max_cascade_iterations``: ``integer`` Maximum short-circuit/trip rounds per update, minimum 1 (default: ``20``)
  | ``per_phase_output``: ``boolean`` Publish per-phase ``(3,)`` results alongside the scalars (default: ``false``)

PowerGridFaultActivationConfig
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``dataset``: ``string`` Name of the electrical network dataset |required|
  | ``threshold``: ``number`` Fault activates when the monitored value exceeds this |required|
  | ``monitor_entity_group``: ``string`` Entity group holding the monitored attribute (default: ``electrical_node_entities``)
  | ``monitor_attribute``: ``string`` Per-node scalar attribute that triggers activation (default: ``flooding.water_depth``)
