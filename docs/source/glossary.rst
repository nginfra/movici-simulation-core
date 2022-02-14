.. |Attribute| replace:: :term:`Attribute`
.. |Attributes| replace:: :term:`Attributes<Attribute>`
.. |Dataset| replace:: :term:`Dataset`
.. |Datasets| replace:: :term:`Datasets<Dataset>`
.. |Entity| replace:: :term:`Entity`
.. |Entities| replace:: :term:`Entities<Entity>`
.. |Entity group| replace:: :term:`Entity group`
.. |Entity groups| replace:: :term:`Entity groups<Entity group>`
.. |Model| replace:: :term:`Model`
.. |Models| replace:: :term:`Models<Model>`
.. |Orchestrator| replace:: :term:`Orchestrator`
.. |Pub/Sub| replace:: :term:`Pub/Sub<Datamask>`
.. |Scenario| replace:: :term:`Scenario`
.. |Services| replace:: :term:`Services<Service>`
.. |Simulation| replace:: :term:`Simulation`
.. |Update| replace:: :term:`Update`
.. |Updates| replace:: :term:`Updates<Update>`
.. |World state| replace:: :term:`World state`


Glossary
===================

.. glossary::

  Attribute
    |Entities| have *attributes*, values that associated with these entities. 
    Every entity must have at least one attribute: ``id`` which must be uniquely identifying a
    single entity within a |Dataset|. By convention, attributes are named by their domain,
    followed by their actual name, such as ``geometry.x`` or ``transport.max_speed``. Since 
    entities are grouped by type, the attribute data can be represented as an array inside the 
    entity group, where every position in the array represents a specific entity. 
  
  Datamask
  Pub/Sub filter
    When a |Model| initializes and registers itself to the |Orchestrator|, it sends information 
    about which parts of the |World state| it is interested in (Subscribes , and which parts of the
    World state it may change. This is 
  
  Dataset
  Init data
    A file that contains simulation input data. A dataset can be entity based data
    (see |Entity group|), in which case the file is a json file that follows the Movici data 
    format, or any other file that contains input data. Common formats are ``json`` and ``csv``. The
    dataset is identified by its file basename, which must be unique in a init data directory.
  
  Entity
    An object in a simulation world space representing a real-world object or phenomenon. These can
    be physical objects such as a pipe or a cable, or something more abstract like a link between
    two other object. Conceptually, an entity is equivalent to a Feature in GeoJSON.

  Entity group
  Entity type
    In a |Dataset|, |Entities| are grouped by their type, such as sewer pipes
    or road segments. By convention entity types are snake_cased and end with the suffix 
    ``_entities``, such as ``road_segment_entities``. All entities of the same *Entity type* in a single
    dataset are called an *Entity group*
  
  Model
    A calculation routine that manages and/or modifies certain parts of the simulation world state
    based on inputs. Models may govern a specific domain, such as *traffic assignment* or may 
    be more utalitarian in nature, such as a *tape player*. Also, some models are steady state,
    while others may be time dependent. A steady state model is a model that, given a certain input
    state, calculates its output only once. It then rests until its input changes, which triggers
    another calculation. Time dependent models update their output state based on time progression
    inside the simulation, independently of whether their input state changes. (Generally, time
    dependent models also update their output state when their input state changes, and sometimes
    even change their 'time-dependentness' when certain inputs change). There maybe be multiple
    instances of a Model during a |Simulation|, each configured to work on separate |Datasets| or
    |Entity groups|.
  
  Orchestrator
    The central-most component in a |Simulation|. The Orchestrator is responsible calling upon
    |Models| to update their state and to provide them with results from other Models. The 
    Orchestrator also keeps the timeline and makes sure to only progress the Simulation further in
    time once all models have processed all |Updates| that they've :term: `subscribed<Datamask>` to
    (which signifies that there is consensus about the current |World state|)

  Scenario
    A collection of |Datasets| and |Models| that can work together in a
    |Simulation|, together with timeline information such as the start date/time and duration
    (both in the simulated world). A scenario is generally described in a scenario config, a json 
    file containing all required information.
  
  Service
    An additional process within a |Simulation|. Different from |Models|, services do not change
    the common |World state|, but instead provide context for models so that they can do their job
    better. For example, the |Orchestrator| is implemented as a Service, as well as the |Update| 
    data service, that works under the hood to distribute updates to |Models| that are 
    :term: `interested<Datamask>`` in the Update's data. There is a maximum of one instance per 
    service in a simulation. Most services are automatically added to a Simulation but services
    can also be added on demand, prior to starting the simulation. In a future release, services
    may also be added to a |Scenario| config
    
  Simulation
    The process of letting |Models| and |Services| work together in calculating the results of a
    |Scenario|. A simulation is created by instantiating the ``Simulation`` class.
  
  Moment
  Timestamp
    ...

  Update
    Whenever a model calculates new output, ie. changes to the current |World state|, only these 
    changes are (/should be) propagated throughout |Simulation|, not the World state. This difference
    between the old world state and the new one is called an Update. An update has the same format
    as an |Entity| based |Dataset| in that all |Attribute| data is arranged in arrays. However, only
    those entities which have updated values, should be present in the arrays. The ``id`` attribute
    is always present in an Update to indicate which position in the arrays belongs to which entity
    Through the |Pub/Sub| system, updates are propated from publishing models, to the models that
    are interested in these parts of the World state
  
  World state
    The collection of all |Entities| in all |Datasets| with all their |Attributes| in a single 
    simulation. The world state is updated by |Models| as the simulation progresses; all changes
    are captured in |Updates|
