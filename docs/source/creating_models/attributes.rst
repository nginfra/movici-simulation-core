.. include:: ../include/code.rst

.. _manual-attributes:

Working with Attributes
=======================


Attributes should have at most one PUBlising model
---------------------------------------------------

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
------------------------------------
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
