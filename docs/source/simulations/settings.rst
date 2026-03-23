.. include:: ../include/glossary.rst
.. include:: ../include/code.rst

Settings
===================

distributed
-----------
By default, a |Simulation| runs distributed. That is, every |Model| and every |Service| runs in
its own process. This has the benefit for certain simulations, some models may calculate parallel
which speeds up the simulation. It is also a requirement for (future) support of running a
Simulation on multiple nodes, where certain models may run on different sites. However, it also
has drawbacks. It leads to communication overhead and some models may not function properly in
a multiprocessing environment on certain operating systems (most notably the
``traffic_assignment`` model on MacOS). To provide an alternative calculation environment, a
|code_Simulation| can be instantiated with the ``distributed=False`` setting. Running in a
non-distributed/in-process environment has the following benefits:

- Reduce overhead. Data is not serialized/deserialized between models. Also, in a distributed the
  number of processes that are created can sometimes reach 50+ for certain scenarios. This is
  significant, especially when you then also want to run multiple Simulations in parallel.
- Provide determinism. When running models in parallel, there is no guarantee that a reproducible
  result is reached. While in general a simulation will always converge to a single state, this
  is by no means a given, and certain race conditions could occur that lead to non-deterministic
  effects. By ensuring that only a single model runs at a time and the models are invoked in a
  prescribed order, the simulation can be carried out deterministically, provided that the models
  themselves are deterministic
- Provide a fallback for certain models that may have incompatibilities when run in a
  distributed, multiprocessing environment
