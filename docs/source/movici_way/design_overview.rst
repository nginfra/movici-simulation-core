Design Overview
=================

Movici has the ability to support many different kinds of modelling domains, and integrate these
in a single scenario. The way this works is primarily by separating calculation Models from Data.
Models do not communicate directly with each other, but always through Datasets. That way, Models
do not need to know about the inner workings of other models, but still "speak the same language"
through a common understanding of shared data. Movici enforces this behaviour by describing the
format data must adhere to. Models can then produce data in this data format in events, while 
other models can listen and react to those events, which may result in additional events.

Event based simulation
------------------------

A Movici simulation can be described as an event based simulation


Orchestration
------------------------

The main component in every Simulation is the ``Orchestrator``

Kinds of Models
------------------------

There are roughly four kinds of models