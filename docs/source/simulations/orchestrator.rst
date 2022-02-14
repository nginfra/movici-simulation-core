Orchestrator
==============

The Orchestrator is responsible for receiving and distributing updates from the producing model to
the subscribed models, and to synchronize the timeline in the simulation. A simulation goes through
different phases, all governed by the Orchestator.

Initialization phase
---------------------

During initialization, every model registers itself to the orchestrator by setting up a connection
and sending their data mask. After all models have registered, the orchestrator
