.. include:: ../include/unicode_checkmark.rst

Movici Communication Protocol
==============================

Within a simulation, every model and services runs in it's own process. Communication between these
processes is done using `ZeroMQ <https://zeromq.org/>`_ (zMQ) over TCP sockets. This article describes 
how zMQ is implemented for Movici. It does not give a complete description on the inner workings
of zMQ and expects basic knowledge about different zMQ terms.

.. note:: 
  In the context of this article, a Model refers to the system process of the model, not to
  instances of (subclasses of) the ``Model`` class that contain the model's business logic


All services, including the ``Orchestrator`` bind to a ``ROUTER`` socket. All models connect to
the ``Orchestrator`` using a ``DEALER`` socket. Most communication with the ``Orchestrator`` is 
synchronous (ie. request -> reply) but in case of an unhandled exception, models need to be able
at all times to send a message to the ``Orchestrator``. A standard ``REQ`` socket is therefore
insufficient. To services other than the ``Orchestrator``, models connect through a ``REQ`` socket. 

All messages are multipart messages where the first frame indicates the message type, and 
subsequent frames contain the message payload. Every payload frame contains a serialized json
object.

Communication with Orchestrator
----------------------------------

Models register to the orchestrator by sending a ``READY`` message. Payload is their Pub/Sub 
Data Mask. The orchestrator responds by sending the first ``NEW_TIME`` message for timestamp ``0``
as soon as all models have registered, indicating the start of the simulation.

Upon every new timestamp, the orchestrator sends ``NEW_TIME`` to every model. After every 
``NEW_TIME`` message, models must respond with ``ACK`` after performing any task that
need be done before transitioning to the new timestamp. The orchestrator may send zero or more
``UPDATE`` messages to zero or more models. The orchestrator may combine multiple ``UPDATE``\s
to the same model at the same timestamp into a single ``UPDATE_SERIES``. Every model must respond 
to ``UPDATE`` or ``UPDATE_SERIES`` with ``RESULT``. At any time, the orchestrator may send an
``END`` message, indicating the end of a simulation, either because it is finished, or because
a simulation failed due to an unhandled exception or other reason. A model must respond to ``END``
by sending ``ACK`` before closing the connection.

At any time when a model detects a failed state, for example due to an unhandled exception. It must
send an ``ERROR`` before closing the connection. The orchestrator must send ``END`` to all non-failed
models to indicate the simulation has failed. Also, when a model sends an unexpected message, the
orchestrator must send ``END`` to all non-failed models (including the model that sent the 
unexpected message)


Communication with Update Data Service
---------------------------------------

``UPDATE`` messages contain only metadata about the update, not the actual data. Models should 
retrieve update data from the the Update Data Service by sending a ``GET``. The Update Data Service
responds with ``DATA`` with the update's data or ``ERROR`` in case the request could not be
adequately processed (such as when the requested ``key`` is unavailable)

After performing a calculation produced an update, Models must send a ``PUT`` message with the 
update's data. The Update Data Service must respond with either ``ACK`` or ``ERROR`` (in case an
error occured)

Upon every ``NEW_TIME`` from the Orchestrator, models should send ``CLEAR`` to the Update Data 
Service to remove any result data they've stored using ``PUT``. The Update Data Service must 
respond with either ``ACK`` or ``ERROR`` (in case an error occured) 

Communciation with Init Data Service
---------------------------------------

Init datasets may be requested from the Init Data Service by sending a ``GET``. The Init Data 
Service responds by either ``PATH`` or ``ERROR`` (in case an error occured). The ``PATH`` contains
a file location to the dataset on disk. In case the dataset is not available, ``PATH`` contains a
``null`` payload.


Message reference
-----------------

====================  =================================================  ================================
Message               Payload                                            Associated Service
====================  =================================================  ================================
``READY``             ``pub``, ``sub``                                   Orchestrator
``ACK``               \-                                                 Orchestrator, Update
``CLEAR``             ``prefix``                                         Update
``DATA``              ``data``, ``size``                                 Update
``END``               ``due_to_failure``                                 Orchestrator
``ERROR``             ``error``                                          Orchestrator, Update, InitData
``GET``               ``key``, ``mask``                                  Update, InitData
``NEW_TIME``          ``timestamp``                                      Orchestrator
``PATH``              ``path``                                           InitData
``PUT``               ``key``, ``data``, ``size``                        Update
``RESULT``            ``key``, ``address``, ``next_time``, ``origin``    Orchestrator
``UPDATE``            ``timestamp``, ``key``, ``address``, ``origin``    Orchestrator
``UPDATE_SERIES``     [*]_                                               Orchestrator
====================  =================================================  ================================

.. [*] ``UPDATE_SERIES`` payload consists of multiple frames, each containing one ``UPDATE`` 
  payload


