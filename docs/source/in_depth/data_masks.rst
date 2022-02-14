.. highlight:: json
.. include:: ../include/code.rst

.. _in-depth-datamasks:

Data masks
===========

.. note::
  When using the |code_TrackedState| and/or |code_TrackedModel| classes, data masks are created
  for you, so you don't have to deal with these yourself and it will just work.

A data mask is a model's description of what data it produces (``pub``), and what data it is 
interested in (``sub``). The mask specifies datasets, entity groups and attributes in the following
way:

.. code-block::

  {
    "pub": {
      "some_dataset": {
        "foo_entities": ["attribute.a", "attribute.b"]
      }
    },
    "sub": {
      "some_other_dataset": {
        "bar_entities": ["attributes.c"]
      }
    }
  }

The above data mask indicates that a model publishes data on ``foo_entities`` inside 
``some_dataset`` and that it only ever publishes ``attribute.a`` and ``attribute.b``. It subscribes
to ``bar_entities`` in ``some_other_dataset``, and is only interested in ``attribute.c``

.. note::
  A model does not need to publish every attribute that is in their ``pub`` mask at every update
  the ``pub`` mask only indicates that it could publish these attributes. However, if it publishes
  attributes that are not announced in its ``pub`` mask, these data may not be sent to all models
  that are interested in these data.


A data mask can contain multiple datasets and entity groups. There may be ``null`` values inside
a data mask. A ``null`` value means "match everything at this level". The following example shows
valid locations for ``null``:

.. code-block::

  {
    "pub": {
      "some_dataset": {
        "foo_entities": null
      },
      "some_other_dataset": null
    },
    "sub": null
  }

The ``pub`` mask means the model could publish anything in ``some_dataset.foo_entities`` and 
anything in ``some_other_dataset``. It is not obliged to do so. Meanwhile it subscribes to 
everything in the world state.

Empty containers (``{}`` or ``[]``) are not allowed in a data mask, except directly after ``pub``
or ``sub``. The following data masks shows some invalid occurences of empty containers. In these
cases the entry should just be omitted from the data mask.

.. code-block::

  {
    "pub": {
      "some_dataset": {
        "foo_entities": []
      },
      
    },
    "sub": {
      "some_other_dataset": {}
    }
  }

The exception is that the ``pub`` and ``sub`` key may contain an empty dictionary:

.. code-block::

  {
    "pub": {},
    "sub": {}
  }

This means that nothing is matched, so this datamask means that the model would publish nothing,
and would subscribe to nothing. (Which makes it a pretty useless model; normally a maximum of one
of ``pub`` and ``sub`` would be an empty dictionary.)