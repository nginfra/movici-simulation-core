.. include:: ../include/code.rst
.. include:: ../include/glossary.rst

.. _models-trackedmodel:

Using TrackedModel
==================

.. hint:: 
    For a tutorial on how to create a custom model using |code_TrackedModel|, see 
    :ref:`custom-model`

When developing a custom model, it is recommended to subclass |code_TrackedModel| since it is 
provides a high level API on top of the Movici framework, especially concerning publishing and 
subscribing to data (see |Datamasks|). |code_TrackedModel| provides a |code_TrackedState| instance
which the developer can use to subscribe to data and publish results. |code_TrackedModel| works in
4 stages:

1) **Setup**: In this stage the model can read its config and determine which specific datasets,
   entity groups and attributes it wants to subscribe and publish to. For this the model is
   expected to implement the 
   :meth:`~movici_simulation_core.base_models.tracked_model.TrackedModel.setup` method and use the
   :meth:`~movici_simulation_core.core.state.TrackedState.register_attribute` and
   :meth:`~movici_simulation_core.core.state.TrackedState.register_entity_group` methods on the
   supplied |code_TrackedState| object to register its |Datamask|

2) **Initialize**: After *Setup*, once all the registered ``INIT`` attributes have received data,
   the model enters the *Initialize* stage. In this stage the model's
   :meth:`~movici_simulation_core.base_models.tracked_model.TrackedModel.initialize` is called once
   and only once. This allows the model to instantiate its own internal state based on the received
   data

3) **Running**: After *Initialize*, when the model's ``SUB`` attributes have been filled with data
   it enters the *Running* stage and its
   :meth:`~movici_simulation_core.base_models.tracked_model.TrackedModel.update` method is called
   at least once (at ``t=0``) so that the model can perform its first calcations, publish its
   initial results and provide (return) an optional ``next_time`` |code_Moment| object on when the
   model wants to be called next (for time dependent models, :ref:`models-moment` below).
   Regardless of whether the model has provided a ``next_time`` |code_Moment|, its
   :meth:`~movici_simulation_core.base_models.tracked_model.TrackedModel.update` will be called
   when its ``SUB`` data has changed, so that it can react to those changes.

4) **Finalize**: When the simulation has stopped, either because it has succeeded, or in case of
   a failure, the model's   
   :meth:`~movici_simulation_core.base_models.tracked_model.TrackedModel.shutdown` is called so
   that the model may clean up any internal resources

Setup
-----

In the setup stage, the model must register full attribute paths that the model wants to subscribe
and or publish to. Depending on the model, it can choose to register |code_EntityGroup| subclasses
or instances, or register attributes directly. When a model has a very flexible data model, that
is, if it can work on a wide range of different entity groups and attributes, it is most
straight-forward to register attributes directly using by calling
:meth:`~movici_simulation_core.core.state.TrackedState.register_attribute` on the provided
``state`` object. If a model requires a certain structure of entity groups containing one or more
predefined attributes, it is beneficial to first define this data model in terms of
|code_EntityGroup| subclasses and then register those using the
:meth:`~movici_simulation_core.core.state.TrackedState.register_entity_group` method on the
provided ``state`` object.


Registering Attributes
^^^^^^^^^^^^^^^^^^^^^^

When a model can be fully configured for a certain attribute or collection of attributes, it can
use the :meth:`~movici_simulation_core.core.state.TrackedState.register_attribute` method on the
provided ``state`` object.

.. testcode:: registering attributes
  from movici_simulation_core import TrackedModel, TrackedState, AttributeSpec, INIT

  class MyModel(TrackedModel):
      def setup(self, state: TrackedState, **_):

          # suppose the model config contains the following information:
          # {
          #   "dataset": "mydataset",
          #   "entity_group": "myentities",
          #   "input_attribute": "some.attribute",
          #   "output_attribute": "other.attribute",
          # }
          #
          # The attributes are assumed to be ``float`` attributes
          self.input_attribute = state.register_attribute(
            dataset_name=self.config["dataset"],
            entity_name=self.config["entity_group"],
            spec=AttributeSpec(self.config["input_attribute"], data_type=float, flags=INIT)
          )
          self.output_attribute = state.register_attribute(
            dataset_name=self.config["dataset"],
            entity_name=self.config["entity_group"],
            spec=AttributeSpec(self.config["output_attribute"], data_type=float),
            flags=INIT
          )


Registering Entity Groups
^^^^^^^^^^^^^^^^^^^^^^^^^

In order to define a |Datamask| based on a structure of entity groups, a model developer can
define subclassses of |code_EntityGroup|. For example, if a model wants to publish or subscribe to
an entity group called ``"my_entities"`` that has a point geometry (ie. the entity group has a
``geometry.x`` and ``geometry.y`` attribute). It can define the following ``EntityGroup``

.. testcode:: registering entity groups

  from movici_simulation_core import EntityGroup, field, INIT
  from movici_simulation_core.attributes import Geometry_X, Geometry_Y
  
  class PointEntityGroup(EntityGroup):
      __entity_name__ = "my_entities"
      x = field(Geometry_X, flags=INIT)
      y = field(Geometry_Y, flags=INIT)


This uses predefined |code_AttributeSpec|\s to register ``"geometry.x"`` and ``"geometry.y"``
as ``INIT`` attributes. :mod:`movici_simulation_core.attributes` and 
:mod:`movici_simulation_core.models.common.attributes` contain many |code_AttributeSpec|\s that 
can be used for defining and registering attributes. 

The |code_TrackedModel| can then look something like this:

.. testcode:: registering entity groups

  from movici_simulation_core import TrackedModel, TrackedState, AttributeSpec, INIT

  class MyModel(TrackedModel):
      def setup(self, state: TrackedState, **_):

          # suppose the model config contains the following information:
          # {
          #   "dataset": "mydataset",
          # }

          self.entity_group = state.register_entity_group(
              self.config['dataset'], PointEntityGroup
          )

          # alternatively, you may instantiate PointEntityGroup to override some defaults, such
          # as the entity group name

          self.alternative = state.register_entity_group(
              self.config['dataset'], PointEntityGroup(name="other_entities")
          )

.. _models-moment:

Simulation time defined by Moment
---------------------------------

<placeholder for documentation about Moment>


Caveats
-------

Attributes should have at most one PUBlising model
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Generally, every attribute should have at most one publisher. That model
is considered to be the owner of that attribute. If more than one model publishes
to an attribute (that is, it writes to an attribute array for a specific entity
group in a specific dataset in a simulation), there is the risk that the state of
this attribute array can diverge. By default, a model is not subscribed to changes
to its publishing attributes, so if there is another model that publishes on this 
attribute, the model is not aware of these changes and the state may become
non-deterministic. In order to prevent this, when designing a Scenario, you should
take care that every attribute (in a specific entity group in a specific dataset)
only has at most one model that publishes that attribute.


Attributes that are both PUB and SUB
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The corollary of requiring at most one publisher per attribute is that it is discouraged
to register an attribute as ``PUB|SUB``; that is: a model both subscribes to an attribute
and publishes to it. An subscribed attribute implies that there may be another model
that publishes on that attribute, which would in this case mean two publishers to that
attribute.

However, there are exceptions to this rule. For example, a model may progress the state
of an attribute based on some initial value. The attribute would in that case be registered
as ``INIT|PUB``. While ``INIT`` is a special case of ``SUB``, it does indicate that it is
expected to only be set once during initialize, and that after that other models don't
update it. Our model is then free to publish on this attribute after it's been set
initially. 

However, the default way that attribute changes are tracked by the |code_TrackedModel|
machinery, is incompatible with this kind of model and this behaviour must be (partially)
overridden. If an attribute is registered as ``INIT|PUB``, by default, the initial data
is considered a PUB change as well, so an update at ``t=0`` would produce update data
containing this attribute's initial data, regardless of whether the model has updated
the attribute.

Let's look at an example. Consider the following model that registers an attribute as 
``PUB|INIT``. Every 10 seconds, it increments the value of this attribute for every
entity in the entity group by 1

.. testcode:: python
  
  from movici_simulation_core import TrackedModel, AttributeSpec, PUB, INIT

  class MyModel(TrackedModel, name="mymodel"):
      def setup(self, state):
          self.attr = state.register_attribute(
                dataset_name="mydataset",
                entity_name="my_entity_group",
                spec=AttributeSpec("my.attribute", data_type=float),
                flags=PUB|INIT,
            )
          self.next_update = 10

      def update(self, moment):
          if moment.seconds < self.next_update:
              return None

          self.attr.array[:] = self.attr.array + 1
          self.next_update += 10
          return Moment.from_seconds(self.next_update)

If we leave the tracking behaviour of the |code_TrackedModel| to its defaults, we end
up with the following erroneous behaviour of the model: 

* Assuming the initial dataset for ``mydataset.my_entity_group.my.attribute`` is available, at 
  ``t=0``, the |code_TrackedState| is populated with a value. As far as the |code_TrackedState|
  is concerned there are pending changes. Normally this is not an issue since ``PUB`` attributes
  and ``SUB`` / ``INIT`` are separate. When we generate the update based on the changes to ``PUB``
  attributes after the :meth:`TrackedModel.update` has run, only the ``PUB`` attributes are
  considered
* After we have generated the update, the changes in the |code_TrackedState| are reset for both 
  ``INIT`` / ``SUB`` and ``PUB``, so that the next time that new ``SUB`` data comes in or new
  ``PUB`` data is produced, those changes are tracked appropriately.
* However, because in this case our attribute is considered both ``PUB`` and ``INIT``, when
  |code_TrackedModelAdapter| generates the update at ``t=0``, the attribute's ``INIT`` changes have 
  not been reset yet and when the update is generated, these changes are in corporated in the
  update, which leads at best to a redundant update, and at worst to undefined or non-deterministic
  behaviour. 

In order to fix this, the model must reset the attribute's changes just prior to it applying its
own changes, so that only its changes are picked up when |code_TrackedModelAdapter| generates
the update. Two small changes are required. First the model must indicate that it only wants the
|code_TrackedModelAdapter| to automatically reset the ``PUB`` changes and not the ``SUB`` changes
by setting the :attr:`TrackedModel.auto_reset` property. Secondly, the model must call
:meth:`~movici_simulation_core.base_models.core.state.TrackedState.reset_tracked_changes` in its
update method:

.. testcode:: python
  
  from movici_simulation_core import TrackedModel, AttributeSpec, PUB, INIT
  from movici_simulation_core.core.attribute import PUBLISH, SUBSCRIBE

  class MyModel(TrackedModel, name="mymodel"):
      auto_reset = PUBLISH

      def setup(self, state):
          self.attr = state.register_attribute(
                dataset_name="mydataset",
                entity_name="my_entity_group",
                spec=AttributeSpec("my.attribute", data_type=float),
                flags=PUB|INIT,
            )
          self.next_update = 10

      def update(self, state, moment):
          state.reset_tracked_changes(SUBSCRIBE)
          if moment.seconds < self.next_update:
              return None
          
          self.attr.array[:] = self.attr.array + 1
          self.next_update += 10
          return Moment.from_seconds(self.next_update)
