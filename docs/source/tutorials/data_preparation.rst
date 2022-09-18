.. highlight:: json
.. include:: ../include/code.rst
.. include:: ../include/glossary.rst

.. |required| replace:: (**required**)
.. |create_dataset| replace:: :func:`~movici_simulation_core.preprocessing.dataset_creator.create_dataset`
.. _tutorial-data-preparation:

Data Preparation
===================================================================================================
Movici |Datasets|, or init data, need to be provided in the :ref:`movici-data-format`. The easiest
way to create these dataset files is to use a |code_DatasetCreator|, or more specifically, the
shorthand function |create_dataset|.

This function can create a Dataset from a ``dataset creator config``, a json object following a 
specific :ref:`schema<tutorial-dataset-creator-config-schema>`. A simple example of a dataset
creator config is as following:

Dataset Creator Config
---------------------------------------------------------------------------------------------------

.. code-block:: json

  {
    "__meta__": {
      "crs": "EPSG:28992"
    },
    "__sources__": {
      "my_source": {
        "source_type": "file",
        "path": "/path/to/my_source.geojson"
      }
    },
    "name": "my_dataset",
    "display_name": "My Dataset",
    "version": 4,
    "general": {},
    "data": {
      "my_entities": {
        "__meta__": {
          "source": "my_source",
          "geometry": "points"
        },
        "my_attribute": {
          "property": "prop",
          "loaders": ["int"]
        }
      }
    }
  }


Let's look at the config piece by piece to show what everything means. 

Global meta data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We start with the global metadata:

.. code-block::

  {
    "name": "my_dataset",
    "display_name": "My Dataset",
    "version": 4,
    "general": {},
  }

These fields will be copied into the resulting dataset as is. The `general` section is currently
empty, and may be omitted. However, it may also be filled with a `special` and `enum` fields, more
on that later. The currently only supported version is `4`, and is an optional field.


__meta__ section
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block::

  {
    "__meta__": {
      "crs": "EPSG:28992"
    }
  }

The ``__meta__`` field contains addtional metadata about the dataset creator needs to know about. In
this case it contains a ``crs`` field, indicating the desired coordinate reference system of the
dataset. This may be different from the crs of the sources (and the sources may each have their own
crs), but the geospatial coordinates of the source entities will be transformed into the value 
of ``crs``. If omitted, the default value is ``EPSG:28992``, which corresponds with `Amersfoort / RD New`

Data Sources
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. code-block::

  {
    "__sources__": {
      "my_source": {
        "source_type": "file",
        "path": "/path/to/my_source.geojson"
      }
    }
  }

The ``__sources__`` field contains definitions of data sources. Keys are identifiers that may be
used later on to reference a specific source. The values give information about the source.
``source_type`` gives the type of the source. Currently, only files are allowed. ``path`` gives
the location to the source file. Since only files are supported, the above snippet may be 
simplified as following:

.. code-block::

  {
    "__sources__": {
      "my_source": "/path/to/my_source.geojson"
    }
  }

Data source files are read by ``geopandas`` (which uses ``Fiona`` under the hood) and can be of
any format that ``geopandas`` supports, typically GeoJSON and Shapefile.

Data section
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block::

  {
    "data": {
      "my_entities": {
        "__meta__": {
          "source": "my_source",
          "geometry": "points"
        },
        "my_attribute": {
          "property": "prop"
          "loaders": ["int"]
        }
      }
    }
  }

.. sidebar:: Attributes vs Properties

  Throughout this documentation, there is a semantic difference between Attributes and Properties.
  Attributes are values, usually in array form, belonging to an |Entity Group| in a Movici Dataset.
  Properties indicate the same data, but from source data, such as in a geojson or shapefile

The ``data`` section of the dataset creator config loosely follows the same structure as the 
``data`` section of the resulting dataset. Top-level keys inside the ``data`` section represent
entity groups, and inside entity groups, most keys represent attributes. In this case there is 
a single entity group ``my_entities`` which will have an attribute ``my_attribute``. An entity
group also requires a ``__meta__`` key with additional information on how to construct the entity
group. Here, it has a ``source`` field, which identifies one of the source in the ``__sources__``
field (see above). It also specifies a geometry, in this case ``points``. Other supported 
geometries are ``lines`` and ``polygons``. For more information about the supported geometries and
how they map to common (geojson) feature types see :ref:`movici-geometries`. An entity group does
not need to have a geometry, but most do.

The ``my_attribute`` field will result in an attribute ``my_attribute`` for the ``my_entities``
entity group. The data for this attribute (array) is taken from the source specified in the 
``__meta__`` field and the ``property`` field in ``my_attribute``.

An attribute config may also specify a ``loaders`` key. See :ref:`dataset-creator-attribute-loaders`
for more information about loaders and an overview of the supported loaders. In this case, the 
``int`` loader ensures that the resulting attribute data has an `integer` data type.


ID generation
###################################################################################################

You may have noticed that the above example does not specify an ``id`` for the ``my_entities``
entity group. In fact, specifying an ``id`` attribute is not allowed. ``id``\s are always generated
for you by the dataset creator. This way, it can be always be ensured that ``id``\s are unique 
within a dataset. In case you need to keep track of which entity belongs to which source asset, you
may use the ``reference`` attribute and fill it with a (unique) string belonging to the source
asset.

.. _dataset-creator-attribute-loaders:

Loaders
###################################################################################################

An attribute config may specify one or more ``loaders``. Loaders are processing operations done on
source property values before they are written to the dataset. A loader acts on each value for
each source asset separately. The table below shows the supported currently supported loaders:

+-----------+------------------------------------------------------------------------------------+
| Loader    | Description                                                                        |
+===========+====================================================================================+
| ``bool``  | Convert the value into a boolean. Follows the Python rules for truthyness, ie.     |
|           | everything is ``true`` except ``false`` , ``0`` ,``0.0`` and ``""``.               |
+-----------+------------------------------------------------------------------------------------+
| ``int``   | Convert the value into an integer, input may be a numeric type or a string with a  |
|           | literal integer. Floating point numbers are converted to int by rounding down.     |
+-----------+------------------------------------------------------------------------------------+
| ``float`` | Convert a value into a floating point.                                             |
+-----------+------------------------------------------------------------------------------------+
| ``str``   | Convert a value into a string.                                                     |
+-----------+------------------------------------------------------------------------------------+
| ``json``  | Parse a string value as json. Supports only primitive types and (multidimensional) |
|           | lists. Lists with more than one dimension, must have a uniform length in all but   |
|           | first dimension. See also :ref:`dataset-creator-recipes-array-like`                |
+-----------+------------------------------------------------------------------------------------+
| ``csv``   | Parse a string as an array of comma  (``,``) separated values. The resulting       |
|           | values are still of type ``str`` but may be converted using other loaders. See     |
|           | also :ref:`dataset-creator-recipes-array-like`                                     |
+-----------+------------------------------------------------------------------------------------+

Dataset Creator
---------------------------------------------------------------------------------------------------

Now that we have established the contents of the dataset creator config, let's have a look on how
to use this to actually create datasets. As mentioned earlier, the most straight-forward method is
to use the |create_dataset| function:

.. testsetup:: create-dataset

  from pathlib import Path
  config = {"name": "foo", "data": {}}
  Path("source_a.csv").write_text("a,b\n0,0")

.. testcleanup:: create-dataset

  Path('dataset.json').unlink(missing_ok=True)
  Path('source_a.csv').unlink(missing_ok=True)
  
.. testcode:: create-dataset

  import json
  from movici_simulation_core.preprocessing.dataset_creator import create_dataset

  dataset = create_dataset(config)
  with open("dataset.json", 'w') as file:
      json.dump(dataset, file)


This will use the config to create a dataset. It is also possible to supply additional 
``DataSources`` as using the ``sources`` arguments. These are then merged with any sources defined
in the config's ``__sources__`` key:

.. testcode:: create-dataset
  
  import pandas as pd
  from movici_simulation_core.preprocessing.dataset_creator import create_dataset, PandasDataSource 

  additional_sources = {
    "source_a": PandasDataSource(pd.read_csv('source_a.csv')),
  }

  dataset = create_dataset(config, sources=additional_sources)

Recipes
---------------------------------------------------------------------------------------------------

Below are a number of recipes showcasing the various functionalities of the Dataset Creator

Enumerations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Enumerated attributes can be specified as following (not all required fields are given, such as
``source``):

.. code-block::

  {
    "general": {
      "enum": {
        "label": ["first", "second", "third"]
      }
    },
    "data" {
      "my_entities": {
        "attr": {
          "property": "enum_prop"
          "enum": "label"
        }
      }
    }
  }

The above config specifies an enum with name ``label`` and three values: ``first``, ``second`` and
``third``. The resulting dataset will make use of this enum in the ``my_entities.attr`` attribute.
The attribute will have integer values in the range ``[0-2]``, matching up with the position in the
enum list.

The source property can contain either strings or integers, integers must be a valid number in the
enum range. When providing string values, the ``general.enum`` section is optional. Any values not
present as a valid enum are simply appended to the list of enum values.

Enums are matched after all loaders are applied. This means that it is possble for example to have
enum values in array-like attributes by supplying the source data as json or csv, and using their
respective attribute loader.


.. _dataset-creator-recipes-array-like:

Attributes with array-like data types
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Movici datasets support array-like values for a single entity's attribute. However, supplying such
data in source properties can be tricky. While geojson supports arrays as a feature property, the
underlying machinery of the |code_DatasetCreator| (``geopandas`` and ``Fiona``) does not. Instead, 
array-like data may be supplied as a string, either as comma-separated-values or a json string.
These can then be converted into their array-like data using respectively the ``csv`` or the 
``json`` loader. For example, consider a geosjon feature with the following property:

.. code-block::

  {
    "properties": {
      "layout": "0,1,1,0"
    }
  }

An entity group config that reads this property may look like this: 

.. code-block::

  {
    "__meta__": "{...}",
    "transport.layout": {
      "property": "layout",
      "loaders": ["csv", "int"]
    }
  }

These loaders parse the csv string into their components. The output from ``csv`` loader still has
a type ``str`` so it must be further converted into integers. The resulting entity group in the
dataset will look like this:

.. code-block::

  { 
    "id": [0]
    "transport.layout": [[0,1,1,0]]
  }
  
Similarly, if the source property would be json-encoded (eg. ``"[0,1,1,0]"``), you would use the
``json`` loader. As a bonus, when loading json data, all values are converted to their respective
data type automatically.

Read attributes from a different source
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes an entity group combines data from multiple data sources. For this case it is possible
to override the entity group's primary source in an attribute config:

.. code-block::

  {
    "__meta__": {
      "source": "source_a"
    },
    "some_attribute_using_the_default_source": {
      "property": "prop"
    }
    "some_attribute_using_source_b": {
      "source": "source_b",
      "property": "prop"
    }
  }

The second source (``source_b``) must contain the same number of features as the primary source
(``source_a``) and the order of features must also be equal.


Linking entities by id
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes it is necessary to link entities together within a dataset, for example when specifying
a network dataset, in which edges are connected to nodes (See also :ref:`movici-common-attributes`
). These connections are done on an `id`\-basis, which means there is an attribute in an entity 
group with integer values that reference `id`\s of other entities (in the same dataset). Since it
is not allowed to specify the `id` for entities created using a dataset creator, the fact that a
certain attribute references `id`\s in other entity groups, must be specified separately. Let's look
at an example dataset creator config:

.. code-block::

  {
    "__sources__": {
      "nodes": "nodes.geojson",
      "edges": "edges.geojson",
    },
    "data": {
      "node_entities": {
        "__meta__": {
          "source": "nodes"
        }
      },
      "edge_entities": {
        "__meta__": {
          "source": "edges"
        }
        "topology.from_node_id": {
          "property": "from_node_ref"
          "id_link": {
            "entity_group": "node_entities",
            "property": "ref"
          }
        },
        "topology.to_node_id": {
          "property": "to_node_ref"
          "id_link": {
            "entity_group": "node_entities",
            "property": "ref"
          }
        }
      }
    }
  }

This config will interpret the source data in the following way: 

* the ``nodes`` source is expected to have features with a ``ref`` property. Every feature must 
  have unique ``ref`` property
* the ``edges`` source is expected to have features with a ``from_node_ref`` and a ``to_node_ref``
  property. Values for these properties are expected to match a ``ref`` field of a feature in
  the ``nodes`` source. This information links a single edge to two nodes; in the attribute config
  for ``topology.from_node_id`` and ``topology.to_node_id`` this link is specified using the 
  ``id_link`` field
* After generating the ``id``\s for every entity, the dataset creator revisits attributes with an
  ``id_link``. It looks up the ``source`` for a linked entity group (in this case "node_entities")
  and maps it to a unique ``id``, which it places in the linking attribute (in this case 
  ``topology.from_node_id`` and ``topology.to_node_id``). Note that it is not required to have
  the linking source property (ie: ``ref``) be available as an attribute in the linked entity
  group. (ie. ``node_entities``), it will read the data directly from the source.

As an example, consider the following input data. it represents two points that are connected by 
a linestring. Processing this data using the above dataset creator config will result in the 
below output data:

.. code-block::
  :caption: nodes.geojson
  
  {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {
          "type": "Point"
          "coordinates": [0, 0]
        },
        "properties": {
          "ref": "1"
        }
      },
      {
        "type": "Feature",
        "geometry": {
          "type": "Point"
          "coordinates": [1, 1]
        },
        "properties": {
          "ref": "2"
        }
      },
    ],
  }

.. code-block::
  :caption: edges.geojson
  
  {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {
          "type": "LineString"
          "coordinates": [[0, 0], [1 ,1]]
        },
        "properties": {
          "from_node_ref": "1",
          "to_node_ref": "2",
        }
      },
    ],
  }

.. code-block::
  :caption: dataset.json

  {
    "data": {
      "node_entities": {
        "id": [0, 1]
      },
      "edge_entities": {
        "id": [2],
        "topology.from_node_id": [0],
        "topology.to_node_id": [1]
      }
    }
  }

Sometimes the linked entity may exist in one of multiple entity groups, for example if there are
more than one groups of nodes inside the network. In that case the ``id_link`` field may contain an
array of entries:

.. code-block::

  {
    "topology.from_node_id": {
      "property": "from_node_ref",
      "id_link": [
          {
            "entity_group": "node_entities",
            "property": "ref"
          },
          {
            "entity_group": "other_node_entities",
            "property": "other_ref"
          }
      ]
    }
  }

The values of "ref" and "other_ref" must be unique within their respective source, but 
there may be duplicates between the sources


Entities without attributes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is possible to create entities in an entity group that do not have any attributes (except for
``id``). There are two ways to do this, depending on whether there is an associated source:

.. code-block::
  :caption: With source

  {
    "__meta__": {
      "source": "my_source"
    }
  }

In case there is a source, the dataset creator simply looks at the number of features of the source
and creates the same amount of entities. If there is no source available, you can set a fixed 
number of entities using the ``count`` field:


.. code-block::
  :caption: Without source

  {
    "__meta__": {
      "count": 10
    }
  }



Undefined attribute values and dealing with NaN
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A property does not have to be defined for every feature within a source. In case a property is not
defined, this results in a ``null`` / ``None`` in the dataset for that entity. For ``bool`` and 
``str`` data types this works as expected. However, for ``int`` and ``float`` there are a few 
caveats

The default data source uses ``pandas`` under the hood. Any ``None`` in a ``float`` property array
is converted into ``NaN`` by ``pandas``. As a consequence, any ``NaN`` encountered by the Dataset
Creator is converted into ``None``, which means the value is undefined for that entity. In case
you have data for which ``NaN`` has a specific meaning, you will first need to convert any ``NaN``
values to a non-``NaN`` |Special| value.

When ``None`` exists within a property of type ``int``, ``pandas`` converts the property array to
``float`` and inserts these ``None`` values to ``NaN``. This means that in case you have ``None``
values for an ``int`` property, it is recommended to add the ``int`` loader to your attribute 
config to ensure the correct data type.


.. _dataset-creator-recipes-custom-data-source:

Preprocess data and custom data sources
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes, it is necessary to perform additional preprocessing to the geospatial data before 
converting it to a Movici dataset. The preferred, and most flexible, way to do this is to first
read the data in a ``geopandas.GeoDataFrame`` and perform any operations you want directly on the
dataframe. You can then hand over the dataframe to a |code_DatasetCreator| and use it to create the
Movici dataset. Consider the following example:

.. literalinclude:: ../../../examples/custom_datasource.py
  :language: python


.. _tutorial-dataset-creator-config-schema:

Dataset Creator Config Schema Reference
---------------------------------------------------------------------------------------------------

DatasetCreatorConfig
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
| ``type``: ``object``

``properties``:
  | ``__meta__``: :ref:`DatasetCreatorMetaData`
  | ``__sources__``: :ref:`DatasetCreatorDatasetSources`
  | ``name``: ``string``, a `snake_case` dataset name |required|
  | ``display_name``: ``string``, a human readable name suitable for displaying
  | ``version``: literal ``4``, only dataset version v4 is supported
  | ``general``: :ref:`DatasetCreatorGeneralSection`
  | ``data``: :ref:`DatasetCreatorDataSection` |required|


.. _DatasetCreatorMetaData:

DatasetCreatorMetaData
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
| ``type``: ``object``

``properties``: 
  | ``crs``: ``string`` or ``integer`` indicating the Coordinate Reference System. Can be anything
      that is supported by ``geopandas`` as a valid CRS identifier. Default: ``EPSG:28992`` 
      (Amersfoort/RD new)

.. _DatasetCreatorDatasetSources:

DatasetCreatorDatasetSources
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
| ``type``: ``object``

``additionalProperties``: 
  | `keys`: Source name
  | `values`: :ref:`DatasetCreatorSource`


.. _DatasetCreatorSource:

DatasetCreatorSource
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
`One of:`

| ``type``: ``string`` location on disk to a source file

----

| ``type``: ``object``

``properties``:
  | ``source_type``: literal ``file``. Only file-based sources are supported
  | ``path``: ``string`` location on disk to a source file

Source files are read using ``geopandas`` which uses  ``Fiona`` under the hood and may be any file
that ``Fiona`` supports as geospatial data, such as ``geojson`` or ``shapefile``


.. _DatasetCreatorGeneralSection:

DatasetCreatorGeneralSection
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``special``: :ref:`DatasetCreatorSpecialValues`
  | ``enum``: :ref:`DatasetCreatorEnums`


.. _DatasetCreatorSpecialValues:

DatasetCreatorSpecialValues
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``additionalProperties``:
  | `keys`: Path to an attribute such as ``<entity_group>.<attribute>``
  | `values`: ``number`` \| ``integer`` \| ``string`` Primitive type of the attribute


.. _DatasetCreatorEnums:

DatasetCreatorEnums
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``additionalProperties``:
  | `keys`: Enum name
  | `values`: :ref:`DatasetCreatorEnumItems`

.. _DatasetCreatorEnumItems:

DatasetCreatorEnumItems
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``
| ``items``: ``string``
| ``minItems``: 1


.. _DatasetCreatorDataSection:

DatasetCreatorDataSection
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``additionalProperties``:
  | `keys`: Entity types that will reflect entity groups in the dataset
  | `values`: :ref:`DatasetCreatorEntityGroup`


.. _DatasetCreatorEntityGroup:

DatasetCreatorEntityGroup
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``type``: ``object``

``properties``:
  | ``__meta__``: :ref:`DatasetCreatorEntityGroupMeta`

``additionalProperties``: 
  | `keys`: attribute names that will reflect attributes in the dataset
  | `values`: :ref:`DatasetCreatorAttribute`


.. _DatasetCreatorEntityGroupMeta:

DatasetCreatorEntityGroupMeta
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`One of:`

| ``type``: ``object``

``properties``:
  | ``source``: ``string`` name of a data source |required|
  | ``geometry``: ``string`` one of ``points``, ``lines`` or ``polygons``

--------

| ``type``: ``object``

``properties``:
  | ``count``: ``integer`` number of required entities (in case there are no additional attributes) |required|


.. _DatasetCreatorAttribute:

DatasetCreatorAttribute
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``type``: ``object``

``properties``:
  | ``source``: ``string`` Source name. Can be used to override the entity group's default source
  | ``property``: ``string`` Name of the property in the data source
  | ``const``: ``boolean`` \| ``number`` \| ``string`` Constant attribute value when no source is given
  | ``id_link``: :ref:`DatasetCreatorIDLink`
  | ``special``: ``number`` \| ``integer`` \| ``string`` The attribute's special value
  | ``enum``: ``string`` Enum name
  | ``loaders``: :ref:`DatasetCreatorAttributeLoaders`


.. _DatasetCreatorIDLink:

DatasetCreatorIDLink
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`One of`

| ``type``: :ref:`DatasetCreatorIDLinkItem`

----

| ``type``: ``array``
| ``items``: :ref:`DatasetCreatorIDLinkItem`
| ``minItems``: 1


.. _DatasetCreatorIDLinkItem:

DatasetCreatorIDLinkItem
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
| ``type``: ``object``

``properties``:
  | ``entity_group``: ``string`` The entity type to link to (target) |required|
  | ``property``:  ``string`` the property (in the target's source data) to match |required|



.. _DatasetCreatorAttributeLoaders:

DatasetCreatorAttributeLoaders
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``
| ``items``: ``string``
| ``values``: ``json``, ``csv``, ``bool``, ``int``, ``float``, ``str``

