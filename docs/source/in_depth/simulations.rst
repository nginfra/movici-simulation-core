.. include:: ../include/glossary.rst
.. include:: ../include/code.rst

Simulations
==============================

A |Simulation| consists of |Models| and |Services|. Models are processes that run the business
logic that performs the calculations for a specific domain and generate simulation results. Models
act on data. Services on the other hand are (most of the time) single instance processes that
perform a specific auxillary role in a Simulation. If necessary, some services can be scaled
horizontally to improve performance. There are three common services that run in a simulation most
of the time. They are:

- |Orchestrator|. The ``Orchestrator`` is responsible for coordination between models and to keep track
  of the simulation time line
- Init Data Service. The Init Data Service handles requests for |Datasets|. By default it reads
  data from disk but it can be customized depending on the data storage environment (database,
  external api). It presents models with a file pointer that they can use to read their data to
  minimize the data sent between it and the models.
- Update Data Service. The Update Data Service acts as a temporary store for Model |Updates|.
  It is implemented as an in memory key/value store.

Another component that is usually added to a ``Simulation`` is a ``Data Collector``. By
default, none of the data that is produced during a simulation is persisted. To ensure persistence,
a small model is added that collects every model's ``Updates`` and stores it to disk (by default).
This model is extensible so that it can also be configured to save updates to an api endpoint or
perform various steps of aggregations.

A simple figure of the different processes in a ``Simulation`` can be found below:

.. uml::

  node Simulation {

    package Models {
      [Model A]
      [Model B]
      [Data Collector]

    }

    package Services {
      [Orchestrator]
      [Update data service]
      [Init data service]
    }

    [Model A] --> [Orchestrator]
    [Model B] --> [Orchestrator]
    [Data Collector] --> [Orchestrator]

    [Model A] --> [Update data service]
    [Model B] --> [Update data service]
    [Model A] -[hidden] [Model B]
    [Data Collector] --> [Update data service]

    [Model A] --> [Init data service]
    [Model B] --> [Init data service]
  }

  database Storage {
    [External data storage]
  }

  [Data Collector] --> [External data storage]
  [External data storage] --> [Init data service]

Startup & Initialization phase
---------------------------------

After invoking a ``Simulation``\s :meth:`~movici_simulation_core.simulation.Simulation.run` method,
it is determined which Models and Services are required (either because they have been set up
manually or are auto-selected). Every Model and every Service runs in its own process. Upon
startup, models are given a service discovery object so that they may connect to the relevant
services. A Simulation starts in the Initialization phase. In this phase, every Model reads their
configuration and requests their relevant initial data. It only reads data that it needs to perform
its calculations, not the full |World State|. Every model keeps their own part of the World State
in memory, which will be synchronized during the simulation. Every model also determines their pub
and sub :ref:`in-depth-datamasks`. These Data masks describe the parts of the |World State| a model
reacts on and the parts of the World State the model may change. Every model then finalizes its
initialization by connecting to the  ``Orchestrator`` and sending a ``READY``  message including
its Pub/Sub data mask. After every model as registered itself to the ``Orchestrator``, the
``Orchestrator`` calculates the pub/sub matrix (which models are subscribed to which model) and
sends a first ``UPDATE`` message to every model to signal the beginning of the simulation.

.. uml::

  participant Simulation as S
  participant Orchestrator as O
  participant "Model A" as A
  participant "Model B" as B
  participant "Init Data Service" as I


  == Start up ==
    create O
    S -> O: spawn
    create I
    S -> I: spawn

    create A
    S -> A: spawn
    create B
    S -> B: spawn

  == Initialization ==
    A -> I: GET
    note right
    the Init Data service may download
    datasets from external sources
    end note
    I -> A: PATH

    B -> I: GET
    I -> B: PATH
    A -> O: READY pubA subA
    B -> O: READY pubB subB

    O -> O: calculate pub/sub matrix

  == Running ==
    O -> A: UPDATE 0
    O -> B: UPDATE 0

Running phase
--------------
In the running phase, models perform their calculations and results are generated. The overall
simulation is a discrete event simulation where models reacts to other models' data updates until
a common agreed-upon |World State| is reached. There are two (implicitly defined) kinds of events:
Time updates and Data updates which are always sent by the ``Orchestrator``. Time updates are sent
to wake up a time-dependent model. Data updates are the result of model's producing results (data)\
that matches the subscribe-Datamask of other models. These models need to be woken up so that they
may react to these World State changes. Every model receives a Time update at the beginning of the
simulation (t=0) so that it knows the simulation has started and it can perform its initial
calcuation. When a model has performed its calculation, it sends its results to the Init Data
Service using a ``PUT`` message. These results should only contain the changes in common World
State. Any values that have not changed (significantly) should be omitted. In general, the
framework provided by Movici ensures this is the case. The model then sends a ``RESULT`` message
back to the ``Orchestrator`` containing the location (address and key) of it's update data (if any)
and the next |Timestamp| (``next_time``) it wishes to be woken up to perform a new calculation. Its
``next_time`` field may be ``null`` indicating there is no specific Timestamp the model wishes to
be woken up (eg. steady state models). If a model has no ``next_time`` announced to the
``Orchestrator`` it can only be woken up by Data updates coming from other models.

After a model has sent a ``RESULT`` message, the ``Orchestrator`` determines to which models to
forward the result to by evaluating the pub/sub matrix. It then sends a Data ``UPDATE`` to these
models containing the address and key of the update data. By only sending this meta-information,
the messages can be kept small to improve performance. The receiving model can then contact the
Update Data Service at the given address to request the update data by sending a ``GET`` message.
It can optionally send it's own Sub-datamask along with this message. The pub/sub-matrix generated
by the ``Orchestrator`` contains all possible overlaps between all models' pub-mask and all models'
sub-mask. This does not mean that every ``RESULT`` message is relevant for every subscribed model,
since a specific ``RESULT`` message may contain (a reference to) data that is not relevant for a
particular model. However, the ``Orchestrator`` is not aware of this and sends a data ``UPDATE`` to
every subscribed model. When a model sends it's Sub-datamask as part of the ``GET`` message, the
Update Data Service can use this to filter out and respond with only the model's relevant data,
reducing the message size. The receiving model then updates it's World State and performs its
calulations (if any). It can upload any results to the Update Data Service and finally sends a
``RESULT`` message back to the ``Orchestrator``. This process continues until there are no pending
data updates for the current timestamp, and every model has had their (multiple) chance(s) to
update the common World State. At this point, there is consensus between the models about the World
State at this Timestamp. The ``Orchestrator`` determines the next Timestamp by looking up the
closest ``next_time`` that was sent by the models and wakes up these (one or more) models at that
timestamp. This triggers the next chain of data updates. This continues until either the max
timestamp for this Simulation has been reached or until no model has a pending ``next_time``, which
signifies that a steady state has been achieved.

The following diagram summarizes a simplified  Running phase of the Simulation. This hypothetical
Simulation consists of two models: ``A`` and ``B``. Model ``A`` publishes on dataset ``a``, to
which ``B`` is subscribed. (in reality ``B`` would not subscribe to the entirety of dataset ``a``
but only to a subset). ``B`` does not publish any data. The ``Orchestrator`` detects ``B`` as being
dependent on ``A`` so it will only wake up ``B`` after ``A`` has returned to prevent duplicate
calulations.

.. uml::

  participant Orchestrator as O
  participant "Model A" as A
  participant "Model B" as B
  participant "Update Data Service" as U

  == Running  (t=0) ==

  O -> A: UPDATE 0
  activate A
  A -> A: update()
  A -> U: PUT a0 <data>
  U -> A: ACK
  return RESULT a0 next_time=5

  O -> B: UPDATE 0 a0
  activate B
  B -> U: GET a0
  U -> B: DATA <data>
  B -> B: update()
  return RESULT null next_time=null

  == t=5 ==

  O -> A: UPDATE 5
  activate A
  A -> A: update()
  note right: 'A' calculates no change in data
  return RESULT null next_time=null

  == Finalization ==
  O -> A: END
  O -> B: END


Dependent Models
^^^^^^^^^^^^^^^^^
When generating the pub/sub matrix during Simulation Initialization, the ``Orchestrator`` records
which models are dependent on other models. During the Running phase, a dependent model is not
woken up as long as any of its direct dependencies are still running. All data
updates for the dependent model are queued and, once all its dependencies have returned, are sent
as a single Data Update using an ``UPDATE_SERIES`` message. The model is expected to return a
single ``RESULT`` based all Data Updates.

.. note::
  An ``UPDATE_SERIES`` message may include both Time Updates and Data Updates. Most of the time it
  contains one ore more Data Updates and zero or one Time Updates

In this example, Model C depends on Model A and B:

.. uml::

  participant Orchestrator as O
  participant "Model A" as A
  participant "Model B" as B
  participant "Model C" as C
  participant "Update Data Service" as U
  == Running ==

  O -> A: UPDATE 0
  activate A
  O -> B: UPDATE 0
  activate B
  A -> A: update()
  A -> U: PUT a0 <data>
  U -> A: ACK
  A -> O: RESULT a0 next_time=5
  deactivate A

  B -> B: update()
  B -> U: PUT b0 <data>
  U -> B: ACK
  B -> O: RESULT b0 next_time=null
  deactivate B

  O -> C: UPDATE_SERIES 0, 0 a0, 0 b0
  note right
  this UPDATE_SERIES contains
  one Time Update and two
  Data Updates
  end note

  activate C
  C -> U: GET a0
  U -> C: DATA <data>
  C -> U: GET b0
  U -> C: DATA b0
  C -> C: update()
  return RESULT null next_time=null



House keeping and Finalization
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
During and after the Running phase, there are a number of messages that are being sent that Models
may hook into to perform housekeeping tasks. At the beginning of every new timestamp a ``NEW_TIME``
message is sent to every Model. Models use this hook to clean up the Update Data Service (every
model is responsible for the data management of their own keys, and these must be deleted after
every timestamp using a ``DELETE`` message), to verify their data integrity (there are situations
in which a model may postpone their own calculation at a timestamp, but must act before a new
timestamp has reached) and to clean up other (external) resources. Similarly, Models may hook into
``END`` messages, which signify the end of a Simulation upon which they may perform final tasks and
clean up resources.
