Installation
==============


.. _installation_linux:

Linux
---------------

``movici-simulation-core`` can be installed using pip:

.. code-block::

  pip install movici-simulation-core

This installs ``movici-simulation-core`` and its core requirements with which you can get started to
create your own models and setup simulations. Some models that that are included with 
``movici-simulation-core`` require extra requirements that can be installed separately:

First install ``mod_spatialite``, an extension to Sqlite for geospatial queries. This shared 
library is required by one of ``movici-simulation-core``\s dependencies. Install using your 
favorite packages manager. For example, under Debian/Ubuntu:

.. code-block::
  
  sudo apt-get install libsqlite3-mod-spatialite

Then you can install the extra python requirements throug pip:

.. code-block::
  
  pip install movici-simulation-core[models]

The models that require these extra requirements are

* ``area_aggregation``
* ``overlap_status``
* ``traffic_demand_calculation``
* ``traffic_assignment_calculation``

.. _installation_windows:

Windows
-------

.. note::
  August 2022: One the dependencies is ``Fiona``. This package only recently started providing
  binary wheels for Windows as per version ``1.9a2``. This is an alpha release version. While it
  appears to be stable enough, if you run into any problems regarding Fiona, try running in an
  alternative environment, such as :ref:`installation_alternative_anaconda`

On Windows, installation is still done using ``pip install movici-simulation-core``. For the extra
model requirements install ``mod_spatialite`` as following:

* Get latest Windows binaries from `Gaia-SINS <https://www.gaia-gis.it/gaia-sins/>`_
* Extract using `7-Zip <https://www.7-zip.org/>`_
* Copy contents to well-known directory such as ``C:\bin\spatialite`` or 
  ``C:\Program Files\Spatialite``
* Add the contents to the ``PATH`` environment variable. For instructions, see 
  `here <https://www.computerhope.com/issues/ch000549.htm>`_
* Log out from your Windows account and log back in to update your environment
* Test if the installation was succesful by opening a command prompt and running: 
  ``sqlite3 :memory: ".load mod_spatialite"``. This commands returns without any output, otherwise
  an error message is shown


Then you can install the extra python requirements throug pip:

.. code-block::
  
  pip install movici-simulation-core[models]


.. _installation_macos:

MacOS
------

Due to some dependencies, the installation on MacOS is a bit more involved. Please follow the instructions below.

**Pre-requisites:**

- Python 3.11 or higher (Lower versions produce conflicts with OpenMP at runtime.)
- `Homebrew <https://brew.sh/>`_ package manager 

1. On a terminal. Install spatialite as follows:

.. code-block:: bash

    brew update
    brew install spatialite-tools
    brew install libspatialite


2. Install the ``llvm`` compiler suite:

.. code-block:: bash

  brew install llvm

3. Set the following environment variables to use the ``llvm`` C and C++ compilers:

.. code-block:: bash

  export CC=/opt/homebrew/opt/llvm/bin/clang
  export CXX=/opt/homebrew/opt/llvm/bin/clang++

4. Update the ``DYLD_LIBRARY_PATH`` to include ``libspatialite``.

.. code-block:: bash

  export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH

5. Clone ``aequilibrae`` repository and install it from source.

.. code-block:: bash

  git clone https://github.com/AequilibraE/aequilibrae.git
  cd aequilibrae
  pip install .

6. Finally, install ``movici-simulation-core`` from source.

.. code-block:: bash

  git clone https://github.com/nginfra/movici-simulation-core.git
  pip install .


Alternative environments
-------------------------

.. _installation_alternative_anaconda:

Anaconda
^^^^^^^^

While the Movici libraries cannot be installed using conda, many dependencies (such as ``Fiona`` 
and ``spatialite``) can:

.. code-block::

  conda install libspatialite fiona
  pip install movici-simulation-core[models]

Windows Substystem for Linux (WSL)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

While Windows is a supported platform, you may have a better experience when running Movici in
a linux environment. The easiest method for running Linux in Windows is by using 
:abbr:`WSL (Windows Subsystem for Linux)`. Only WSL 2 is supported, this is default WSL version
for Windows 10 and higher. When using WSL, it is recommended to use VSCode as your development
environment. See `Developing in WSL <https://code.visualstudio.com/docs/remote/wsl>`_ for 
installation instructions. After installation of WSL, follow the installation instructuctions for
:ref:`Linux<installation_linux>` for how to install Movici. 

