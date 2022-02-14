.. include:: ../include/code.rst
.. highlight:: json

.. _movici-data-format:

Movici Data Format
============================

At the heart of Movici is a clear definition of what simulation data should look like and how to
extend the data format to accommodate many different calculation domains. The Movici Data Format
is described below.

.. _movici-data-format-datasets:

Datasets, Entities and Attributes
----------------------------------------

All simulation data is divided into datasets. While there is not restriction of what could be input
data to a specific model (any file could be considered a dataset), there is a restriction when it
comes to sharing data and results between models. These are called Entity Based Datasets. Every
aspect of a simulation world can be captured in an Entity. Entities may be representations of
physical objects, such as a pipe, road segment or building, or may be a more abstract concept such
as a (virtual) link between two other entities, or a grid cell for numerical computations. Entities
belong to the same (business/engineering) domain should be grouped in a single dataset, so that
all entities belonging to a road network are in the same dataset, and all entities belonging to
a drinking water network are in a different dataset. 

Inside a dataset, every entity of a certain Entity Type is placed into a single group, such that
all drinking water pipes are grouped together, and all pumps are placed in a different group.
By convention, an entity type is a `snake_case` name and ends with the suffix `_entities`. So there
may be an group of ``water_pipe_entities`` in a dataset as well as a group of ``water_pump_entities``. 

Every entity has one or more attributes, specific values related to this entity, such as a 
geospatial location or geometry, a maximum speed (in case of roads) or a pipe thickness (in case of
a drinking water pipe). Within the Movici data format there is no requirement on which entities 
must have which attributes, except for one: `id`. Every entity must have a numeric (integer) id 
that is unique within its dataset. 

All entity data is stored in ``json`` files. A minimal dataset is shown as following:

.. code-block:: json

  {
    "my_road_network": {
      "road_segment_entities": {
        "id": [0, 1, 2, 3],
        "transport.max_speed": [27.7, 27.7, 16.7, 16.7]
      }
    }
  }

  

The json-object contains the dataset name as a single top level key, in this case ``my_road_network``.
Within this dataset there is a single entity group ``road_segment_entities``. Inside this group,
the attributes are given as arrays. Every entity is represented by a position in these array. The
first entity has ``id=0`` and a ``transport.max_speed=27.7`` while the last entity in this group
has ``id=3`` and ``transport.max_speed=16.7``. Representing entities in this way is both beneficial
for storage size and computational performance, as most (if not all) models do their calculations
on arrays of data, which means less overhead in converting the data to arrays.

.. note::
  In the above example, the dataset name was indicated by the top level key in the json-documented.
  A second way to describe an entity base dataset is to provide a ``name`` key and a ``data`` key,
  such as indicated below. The entity groups are then placed directly under the ``data`` key. While
  both formats are supported by ``movici-simulation-core``, only the second format is supported by 
  the Movici Cloud Platform.

  .. code-block::

    {
      "name": "my_road_network",
      "data": {
        "road_segment_entities": {}
    }

Attribute arrays may contain ``null`` values. This means that the attribute is not set for a 
particular entity, while it may be set for others in the same entity group. When an attribute has 
a ``null`` value, it called to be Undefined for that particular entity. An additional attribute to
the ``road_segment_entities`` in the above example may be:

.. code-block::

  {
    "transport.max_speed_rushhour": [null, 22.0, null, null]
  }

In this case road segment  ``1`` has an additional maximum speed defined that is only valid during certain
hours. Depending on the time of day (inside a simulation), a model may decide to work with the
alternative maximum speed for this road segment, while using the base maximum speed for the other 
road segments

Aside from ``id``, attributes can have any name. However, to encourage sharing attributes between
different models, there are conventions. Attributes are all ``snake_case`` with a ``.`` separating
a namespace from the actual attribute name. The namespace relates to the relevant domain of the
attribute and is there to disambiguate attributes that may share a name. An attribute named `p` may
exist in both the electrical domain (representing Power) as well as the fluid domain (representing
Pressure). To distinguish these different attributes, they should be given a namespace, ie 
``electrical.p`` and ``fluid.p``. The namespace also helps to give a visual indication of 
attribute's domain.



.. _movici-data-format-updates:

World state vs Updates
-------------------------
All entity based datasets together form the World State for a scenario or simulation. They 
represent every relevant object that exists for the scenario. Due to the nature of the simulations,
the world state is not static and attribute values change over time as models do their calculations
and produce new results for different timestamps. Changes to the world state during a simulation
are called Updates. Whenever a model finishes a calculation, it produces an Update. An update 
has a format very similar to a full datasets, but contains only those entities and attributes that
have actually changed from the current world state. An example update to the ``my_road_network`` 
from above may look like the following:

.. code-block::

  {
    "my_road_network": {
      "road_segment_entities": {
        "id": [0, 3],
        "transport.max_speed": [10.0, 12.0]
      }
    }
  }

This updates the max speed for entities ``0`` and ``3`` while leaving ``1`` and ``2`` intact.

Any ``null`` value in an update represent a "hole" in that update, meaning that the current value
in the world state is not affected by the update. This is useful for updating only some values in
one attribute array, and others in a different array:

.. code-block::

  {
    "my_road_network": {
      "road_segment_entities": {
        "id": [0, 1, 2, 3],
        "transport.max_speed": [null, null, 12.0, 12.0 ],
        "transport.max_speed_rushhour": [25.0, 25.0, null, null]
      }
    }
  }

This updates the value for ``transport.max_speed`` for entities ``2`` and ``3``, and 
``transport.max_speed_rushhour`` for entities ``0`` and ``1``

.. note::
  Most of the time, updates are created and read automatically, especially when using the 
  |code_TrackedState| and/or |code_TrackedModel| classes, so you don't have to worry about the 
  details of the update that your model needs to produce.
  

.. _movici-data-format-data-types:

Data Types
------------------------

In order to support high performant numercial calculations, Movici relies heavily on ``numpy``. 
Inside ``movici-simulation-core``, every attribute array is converted into a ``numpy.ndarray``. 
Since numpy arrays are statically typed, every attribute must also be statically typed. In order to
be consistent, the attribute's data type should be predefined. This can be done by registering an
|code_AttributeSpec| to a |code_Simulation|. In case an attribute is encountered that does not have
a registered ``AttributeSpec``, it's data type will be inferred from the data. This is however, not
error-proof, especially when it concerns `Complex data types`_. It is therefore always recommended
to register attributes that are relevant to a ``Simulation``. See also :ref:`Plugins<tutorial-plugins>`
on how to always register a common set of ``AttributeSpec``\s.

There are four primitive datatypes, these map to the following ``numpy.dtype``:

=========  ===============
Python     Numpy   
=========  ===============
``bool``   ``np.int8``
``int``    ``np.int32``
``float``  ``np.float64``
``str``    ``np.str_`` [*]_
=========  ===============

.. [*] ``str`` data types are UTF-32 encoded. the numpy ``dtype`` grows with the maximum size in the 
  attribute array. It has a minimum size of 8 characters (32 byte per attribute) and a maximum of 256
  characters (1024 bytes per attribute)

..sidebar:: A note on units

(Engineering) units are currently not part of an ``AttributeSpec``, so you are responsible for 
making sure units align with each other. A future release of ``movici_simulation_core`` will 
support supplying units so that you can verify the correct units more easily.

Complex data types
^^^^^^^^^^^^^^^^^^^^^^

Aside from the above primitive types, it is also possible to define more complex, types. Complex in
this sense does not refer to numbers having an imaginary part, but to the fact that they consist
of multiple values for a single entity, ie. if the value for a single entity needs to be an
array. Complex attributes may be fixed size arrays (for example always 2 values per entity), 
variable-sized arrays when the array length may differ per single attribute, or a combination 
of these two. 

Complex data types can be created using the |code_DataType| class. This class takes in three 
arguments:

* ``py_type`` The python primitive type for this data type. All complex data types must have a 
  homogeneous primitive
* ``unit_shape`` This determines the fixed size shape of the attribute for each entity. The default
  unit shape of ``()`` means 0-dimensional (ie. scalar) and represents a single primitive per 
  entity. The meaning of ``unit_shape`` is equivalent to the meaning of ``numpy.ndarray.shape``
* ``is_csr`` This toggles support for variable width arrays per entity. ``csr`` is an abbreviation
  of Compressed Sparse Row, which is the technique used to store these types of attribute arrays.
  See also :ref:`Working with Attributes<tutorial-attributes>` on how to interact with csr arrays

Fixed width arrays are created by supplying the ``unit_shape`` argument to a ``DataType``. For 
example an array of pairs are supported by ``DataType(int, unit_shape=(2,))``:

.. code-block::
  
  {
    "foo.pairs": [[1, 2], [3, 4], [5, 6]]
  }

Variable length csr data types require the ``is_csr`` boolean to be set, such as in 
``DataType(int, is_csr=True)``. For these attributes, every entity has an array/list of zero or more
values assigned to it, which can grow or shrink individually during a simulation:

.. code-block::

  {
    "foo.list": [[1, 2], [], [4], [3, 4, 5]]
  }

It is also possible to combined fixed length with variable length attributes. In that case the
resulting attribute becomes a variable length array of fixed size tuples. For example, 
the builtin ``geometry.polygon`` attribute has a data type of 
``DataType(float, unit_shape=(2,), is_csr=True)``:

.. code-block::

  {
    "geometry.polygon": [
      [[0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0], [0.0, 1.0]],
      [[2.0, 2.0], [2.0, 1.0], [0.0, 0.0], [2.0, 2.0]]
    ]
  }

For complex data types, an Undefined is represented by a single ``null`` in the attribute array:

.. code-block::
  
  {
    "foo.pairs": [[1, 2], null, [5, 6]],
    "geometry.polygon": [
      [[0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0], [0.0, 1.0]],
      [[2.0, 2.0], [2.0, 1.0], [0.0, 0.0], [2.0, 2.0]],
      null
    ]
  }

.. _movici-data-format-general:

General Section
-----------------
At the root of the dataset document, there may be a ``general`` which can contain some additional
metadata about the dataset and attribute values. Most importantly are the ``special`` and the 
``enums`` key. These will be explained below.

.. note::
  While there may be many different keys in the root of the dataset document that can provide 
  metadata, ``general`` is the only key that may contain an object/dictionary itself. Any other
  key that contains a dictionary is considered to be dataset data and will be parsed as such


.. _movici-data-format-data-special-values:

Special Values
^^^^^^^^^^^^^^
Sometimes, having just a numerical value for an attribute is not enough. Sometimes you want to 
convey that an attribute's value is not a normal value. It may be that there is no ``route`` found
between two points on the map, or that a ``flooding.water_height`` indicates that the location is 
dry and you want to represent that in a value. In some application this is achieved by setting a
``NaN`` value. However, ``NaN`` is not supported in json, and only works for floating point values.
Other data types do not have ``NaN``. Movici instead knows the concept of a ``special`` value, a 
value that lies outside the range of "normal" values. What constitutes a "normal" value depends 
on the context of the attribute, and therefore these must be given for a specific 
dataset+entity+attribute. Inside the ``general`` section there may be a ``special`` key. This 
section contains keys in the format ``<entity_type>.<attribute>`` that point to that attribute's
special value:

.. code-block::

  {
    "general": {
      "special": {
        "my_entities.foo": -9999
      }
    },
    "my_dataset": {
      "my_entities": {
        "id": [1, 2],
        "foo": [12, -9999]
      }
    }
  }

It is up to the creator of the dataset to determine a reasonable special value. Special values are
completely optional. If an attribute does not need a special value, it is not necessary to define
one. 

.. _movici-data-format-enums:

Enumerations
^^^^^^^^^^^^^

A specialization of an ``int`` attribute, is an ``int`` attribute with an enumeration. Enumerations
are useful when you want an attribute to categorize an entity group with a limited number of 
categories. While it is possible to create a ``str`` attribute and provide the full category name
for every entity, this creates a lot of overhead. Instead, it is much more performant to associate
an integer with every category and map every category name to that integer, called an enumeration,
or enum for short. Enums have names and values. The enum name is part of the |code_AttributeSpec|,
while the enum values (the categories themselves) are part of the dataset. The enum values are
then placed under the ``enum`` key in the ``general`` section. For an attribute with a spec
``AttributeSpec("foo", data_type=int, enum_name="bar")``, a dataset may look like the following:

.. code-block::

  {
    "general": {
      "enum": {
        "bar": ["some", "enumerated", "categories"]
      }
    },
    "my_dataset": {
      "my_entities": {
        "id": [1, 2, 3, 4],
        "foo": [2, 1, 2, 0]
      }
    }
  }

The attribute values ``[2, 1, 2, 0]`` now map to the ``bar`` enumeration as 
``["categories", "enumerated", "categories", "some"]`` but which a much reduced data footprint. See
also :ref:`Custom Models<custom-models>` on how to work with enumerations


.. _movici-data-format-storing-data:

Storing your Datasets
----------------------

When preparing datasets. It is important to note the following:

* Init dataset files must be placed in a single directory for a simulation. Different simulation 
  may use the same datasets. This directory is refered to as the ``data_dir``.
* Since any changes to the world state are captured in updates, the dataset files themselves are
  not modified during a simulation.
* Dataset files must be named after their dataset name, eg. ``my_dataset.json`` for a dataset called
  ``my_dataset``.
* In a simulation, datasets are always refered to by their name.