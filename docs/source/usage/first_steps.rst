Creating your first Simulation
==============================

Let's create our first simulation. This is a basic example on how to setup and run a 
simulation in Movici, but it will cover most of the important details that have to do with
running simulations. 

In order to run a simulation, we create a file `squares.py` and start editing it. We first need to 
instantiate a ``Simulation`` object:

.. code-block:: python

  from movici_simulation_core import Simulation
  
  sim = Simulation()

Now, we need to add some models and some (initial) data. We start with the data. Movici datasets,
or more specifically, entity based data (see also: :ref:`movici-data-format`), have a specific 
format. Let's create a dataset with two entities of a certain type, and give them some attribute
values

.. code-block:: python

  dataset = {
      "figures": {
          "square_entities": {
              "id": [1, 2],
              "shape.edge_length": [10.0, 20.0]
          }
      }
  }

.. sidebar:: Attribute namespaces

  The ``shape.`` prefix acts as a namespace to our ``edge_length`` attribute. Perhaps in the future we
  also want to do simulations containing medieval weaponry, and we want to distinguish the meaning 
  the meaning of ``swords.edge_length`` from that of ``shape.edge_length``. By convention, namespaces 
  are the way to do that.

We now have defined two entities of type ``square_entities`` in our ``figures`` dataset. The first 
entity has ``id=1`` and a single attribute ``shape.edge_length=10.0``. Our second entity has an ``id=2`` and
``shape.edge_length=20.0``.  Since our Movici data format is array-oriented, we concatenate the attribute
values of every entity of the same type into a single array per attribute. Every index in these 
array refers to a specific entity. In our case, position 0 is allocated for our entity with ``id=1``
and position 1 for entity ``id=2``.

In order to make use of this dataset in a simulation, we must store it to disk:

.. code-block:: python

  import json
  from pathlib import Path
  from tempfile import mkdtemp

  input_dir = mkdtemp(prefix='movici-input-')
  output_dir = mkdtemp(prefix='movici-output-')

  Path(input_dir).joinpath('figures.json').write_text(json.dumps(dataset))

We've created two temporary directories, one for input data and one for simulation results. We
then stored our dataset in a json file with the name of the dataset.

.. note::
  In Movici, datasets are identified by their filename. Dataset files must have a base name equal
  to their dataset name, and this basename must be unique within a input data dir

  Also, in general you'd want to fill your data_dir with your datasets running your simulation, 
  so that you don't recreate the datasets every time you run a simulation

We can now tell our ``Simulation`` to look for its input data in the given directory. It is also
recommended to tell our ``Simulation`` that there exists an attribute called ``shape.edge_length`` and
that it has values of type ``float``. This is done by registring an ``AttributeSpec``

.. note::
  It is not required to specify every attribute using an ``AttributeSpec``. If an attribute is 
  encountered that does not have an associated specification, the simulation core will do it's best
  to infer the data type from the data. This does however, create an performance overhead, and is
  not foolproof. It works for simple data types, but can make mistakes for more complex types. It
  is therefore recommended to always register your attributes  

Our ``squares.py`` now looks as following:

.. code-block:: python

  import json
  from pathlib import Path
  from tempfile import mkdtemp
  from movici_simulation_core import Simulation
  from movici_simulation_core.core import AttributeSpec

  input_dir = mkdtemp(prefix='movici-input-')
  output_dir = mkdtemp(prefix='movici-output-')
  
  dataset = {
      "figures": {
          "square_entities": {
              "id": [1, 2],
              "shape.edge_length": [10.0, 20.0]
          }
      }
  }
  
  Path(input_dir).joinpath('figures.json').write_text(json.dumps(dataset))

  sim = Simulation(data_dir=input_dir, storage_dir=output_dir)
  sim.register_attributes([AttributeSpec("shape.edge_length", data_type=float)])

Now that we have data, we can add and configure our models. In our dataset, we have 
``square_entities`` that have an ``shape.edge_length`` but no ``shape.area`` yet. We are going to let 
a model calculate these. For this, we'll make use of the included ``UDFModel``. ``UDF`` stands for 
*User Defined Function* and thi model can do basic arithmetic operations on attributes. We add the 
``UDFModel`` as following

.. code-block:: python

  from movici_simulation_core.models.udf_model import UDFModel

  sim.add_model("square_maker", UDFModel( {
            "entity_group": [["figures", "square_entities"]],
            "inputs": {"length": [None, "shape.edge_length"]},
            "functions": [
                {
                    "expression": "length * length",
                    "output": [None, "shape.area"],
                },
            ],
        }))
  sim.register_attributes([AttributeSpec("shape.area", data_type=float)])

.. sidebar:: A note on model config pecularities

  You may wonder why there is a ``None`` in front of our attribute names, or why the entity group
  is given as a nested list. This is for compatibility with an older version of the Movici
  data format and to be able to support running in the Movici Cloud Platform. In future releases
  these pecularities will be removed.

We've created an instance of ``UDFModel`` and given it a unique name in the ``Simulation``: 
``"square_maker"``. We've configured the model with its required parameters. We point it to a 
specific entity group inside our dataset and refer to certain input attributes (which we can give
a working name). In this case we have one input attribute ``shape.edge_length``, which we temporarily
call ``"length"``, we can then create an expression with the temporary name as a variable name, 
and store the expression result under an output attribute in the same entity group. For 
completeness, we also register the output attribute to the simulation.

Now, we have a single model that does a calculation. However, the results of this calculation are 
not going anywhere, currently, they stay in the simulation, and disappear as soon as the simulation
is completed. In order to save the results, we need to add a second, special model called
``DataCollector``. This model takes all updates that other models produce, and stores them in the
output directory ``storage_dir``. 

.. code-block:: python

  from movici_simulation_core.models.data_collector import DataCollector

  sim.add_model("data_collector", DataCollector({}))

There, we are now ready to run our first simulation. The final ``squares.py`` looks like this:

.. code-block:: python

  import json
  from pathlib import Path
  from tempfile import mkdtemp
  from movici_simulation_core import Simulation
  from movici_simulation_core.core import AttributeSpec
  from movici_simulation_core.models.udf_model import UDFModel
  from movici_simulation_core.models.data_collector import DataCollector

  input_dir = mkdtemp(prefix='movici-input-')
  output_dir = mkdtemp(prefix='movici-output-')
  
  dataset = {
      "figures": {
          "square_entities": {
              "id": [1, 2],
              "shape.edge_length": [10.0, 20.0]
          }
      }
  }
  
  Path(input_dir).joinpath('figures.json').write_text(json.dumps(dataset))

  sim = Simulation(data_dir=input_dir, storage_dir=output_dir)
  sim.register_attributes(
    [
      AttributeSpec("shape.edge_length", data_type=float),
      AttributeSpec("shape.area", data_type=float)
    ]
  )
  sim.add_model("square_maker", UDFModel({
        "entity_group": [["figures", "square_entities"]],
        "inputs": {"length": [None, "shape.edge_length"]},
        "functions": [
            {
              "expression": "length * length",
              "output": [None, "shape.area"],
          },
        ],
      }
    )
  )
  sim.add_model("data_collector", DataCollector({}))

  sim.run()
  print(f"results stored in {output_dir}")

After we've succesfully run our simulation, the output directory contains one file:
``t0_0_figures.json``. Its filename is made up of the following components:

* ``t0`` means timestamp 0 in the simulation. Every simulation starts at ``t=0``
* ``0`` The second ``0`` marks the iteration number. At every timestamp, there may be multiple
  updates calculated. Every update in a single timestamp must have a unique increasing, 
  iteration number
* ``figures`` This is to indicate to which dataset the update file belongs to.

When we open this file, we see that it contains the following data:

.. code-block:: python

  {
    "figures":{
      "square_entities":{
        "id": [1, 2],
        "shape.area": [100.0, 400.0]
      }
    }
  }

The model has succesfully calculated the area for all of our squares, yay! You are now ready to
read further about the various aspects of programming with Movici, or take a deep dive and start
creating your own Models.
