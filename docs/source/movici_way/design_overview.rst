.. include:: ../include/glossary.rst


Design Overview
=================

Movici has the ability to support many different kinds of modelling domains, and integrate these
in a single scenario. The way this works is primarily by separating calculation Models from Data.
Models do not communicate directly with each other, but always through Datasets. That way, Models
do not need to know about the inner workings of other models, but still "speak the same language"
through a common understanding of shared data. Movici enforces this behaviour by describing the
format data must adhere to. Models can then produce data in this data format in events, while 
other models can listen and react to those events, which may result in additional events.

Event based simulation
------------------------

A Movici simulation can be described as an event based simulation. All models run in their own
process. There is a separate, controlling process called the ``Orchestrator`` that sits in the 
middle and dispatches events to the models. At the start of a simulation, all models register 
themselves to the ``Orchestrator`` with their :ref:`Data Mask<in-depth-datamasks>`. The data
mask states in which data (datasets, entity groups and attributes) the model is interested in,
or `sub`\scribes to, and what data (datasets, entity groups and attributes) the model produces, or
``pub``\lishes. The ``Orchestrator`` uses this information to determine which models to send events
to when a model produces data. The models also indicate the next time (in the simulation timeline)
(if any) they want to be "woken up" to perform a calculation, and (possibly) produce data. After
every model has registered itself, the ``Orchestrator`` moves to the first timestamp one or more
models have indicated to be woken up, and sends an event to those models to perform their 
calculation. After a model finishes calculation, it sends a result back to the ``Orchestrator``
indicating if they have produced any new data (|Update|). If the model has produced an Update,
the ``Orchestrator`` looks up which models have subscribed to the producing model's data and sends
those models an event indicating there is new data available for them. If a model has not produced
any new data, no new events are send out. The notified models can now retrieve the new data and
perform their own calculation, which may lead to new Updates and new models being notified by 
the ``Orchestrator``. This series of cascading events all happens within the same timestamp of the
simulation and continues until no notified model produced any new data. At this point there is
considered consensus about the world state for this particular timestamp (every notified model has
had a chance to update their part of the world state), and the simulation moves to the next
timestamp. The ``Orchestrator`` wakes up the models that are next on the queue, and the series
of cascading events start anew.


Simulation Timeline
---------------------

The driving force of a Simulation is it's timeline. A simulation always starts at ``t=0`` and
moves forward in descrete/integer steps. These steps are called Timestamps. At the start of a
Simulation, models can register themselves on the timeline and indicate at which Timestamp they
want to be "woken up", called ``next_time``. After every time they are woken up (beit from a 
time-update or because a different model has produces data they are subscribed to) and return a 
result to the ``Orchestrator`` they are required to register themselves on the timeline by 
including their ``next_time``. They may send in ``None`` or ``null`` to indicate they do not wish
to be "woken up" at a particular Timestamp but only when there is new data availble for them. In
that case the model is considered to be in steady-state (their output doesn't change until their
input data has changed). At every update a model may switch from being time-dependent to being
steady state (although a steady state model can only become time-dependent after it has been 
notified that their input data has changed)

The timeline is therefore a queue containing only the models that want to be woken up at a specific
time, and only their first immediate ``next_time``. Every model can only appear once on the
timeline. This allows the ``Orchestrator`` to determine easily determine the relevant ``next_time``
after world state consensus has been reached on the current Timestamp. 

A Simulation ends whenever there are no more models registered on timeline, or when the ``end_time``
of the Scenario has been reached.

As mentioned, a Timestamp is only a discrete value indicating some amount of time that has elapsed
starting from ``t=0``. The Simulation needs to be configured with a
:class:`~movici_simulation_core.uitls.moment.TimelineInfo` object (using 
:meth:`Simulation.set_timeline_info<movici_simulation_core.Simulation.set_timeline_info>`) that
holds contextual information on how to translate a timestamp to a world time. A ``TimelineInfo``
contains the following fields:

``TimelineInfo``:
  | ``reference``: a unix timestamp (in seconds) indicating the world time at ``t=0``
  | ``time_scale``: the number of seconds each discrete time step signifies
  | ``start_time``: the initial timestamp for the simulation, typically ``0``. Simulations may 
    optionally start at ``t>0`` but this has limited functionality
  | ``duration``: The duration of the simulation in discrete time. If ``start_time=0`` then 
    ``duration`` is equivalent to the final timestamp

A model can use the :class:`~movici_simulation_core.uitls.moment.Moment` object it receives in 
its ``update`` method to request information about the simulation world time should this
information be required.

.. _movici-overview-kinds-of-models:

Kinds of Models
------------------------

Models can be categorized in a number of ways. For example by their specificity: some models are
tied to a certain (engineering) domain (Domain Models), while other may be more generic in 
nature and need to be configured at run-time to provide meaningful functionality (Utility Model)

Another way to categorize models is by their time/state-dependency. This way there are roughly
three categories of models:

* time dependent, state independent
* time independent, state dependent (steady-state)
* time dependent, state dependent

Time dependent, state independent Models
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These kinds of models are `produce-only` models. They are not dependent on any state, and therefore
do not subscribe to any data. They simply publish some data, based on their configuration, at
certain timestamps. Once they deregister themselves from the timeline, by sending a 
``next_time=None``, they will never be called again by the ``Orchestrator``. Example: 
:class:`Tape Player<movici_simulation_core.models.tape_player.model.Model>`

Time independent, state dependent (Steady State) Models
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Steady-state models calculate their output state once based on their initial input data, and then
will update this state only when their input data changes. These models do not appear on the
Timeline and will therefore only be called by the ``Orchestrator`` when another model updates their
subscribed data. Most Utility models fall under this category. Examples:
:class:`~movici_simulation_core.models.udf_model.udf_model.UDFModel`,
:class:`~movici_simulation_core.models.shortest_path.model.ShortestPathModel`

A subcategory of steady state models is the `consume-only` model. These kinds of models subscribe
to data but do not publish data themselves, for instance because they interact with resources or
services outside the Simulation. Example:
:class:`~movici_simulation_core.models.data_collector.data_collector.DataCollector`


Time dependent, state dependent Models
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These models can be considered the most complex kind of models. They respond to both changes in
time as well as changes in subscribed data. Most models in this category are Domain models since
they often need to capture the most complex behaviour of a domain. Example:
:class:`~movici_simulation_core.models.traffic_demand_calculation.model.TrafficDemandCalculation`


