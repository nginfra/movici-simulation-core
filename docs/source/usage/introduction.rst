.. _introduction:

Introduction
======================

What is Movici?
----------------------

Movici is a software suite for running various kinds of (event based) simulations. It focuses on
time-based geospatial simulations. This means anything that has a physical location in the world 
and/or can change over time can be simulated using Movici. This is for example useful for 
simulations of different kinds of infrastructure domains such as roads and utilities but also for 
other types of assets in the world, such as buildings. Movici emphasises on the interdependencies
between different domains so that the effects that one has on the other can be identified and
quantified. 

An example
---------------------------------

Judy is responsible for investment planning for a road infrastructure maintainer. She wants to know
how the upcoming planned housing investments affects her road network. She loads a digital 
representation of her road network (called a dataset) into Movici as well as the forecasted 
population density. Movici's integrated Traffic Demand Model and Traffic Assignment model 
calculate the effect that the increased population has on her road network. She is able to 
pin-point a bottleneck in her network where road usage exceeds its capacity, leading to unacceptable 
congestion. She is able to plan her investments accordingly, determining that the affected roads 
need to be widened, and after loading her planned investments into Movici, validates that these 
indeed solve the congestion problems. 

Meanwhile, Jason is head of logistics of a major sea port. He is in good contact with Judy and
when she shares her road investment planning, he immediately runs his own simulation in Movici 
using this data. It turns out that one of his core transport routes will be unavailable for some
time due to the planned road works. By connecting his own supply chain model, he is able to 
re-allocate demand to cargo trains to ensure that his customers receive their goods in time.

Why is it called Movici?
---------------------------------

Movici is an acronym of Modeling and Visualization of Critical Infrastructures. Next to its 
Simulation Core, Movici provides a powerful data visualization tool for showing simulation results
and using these visualizations to communicate the core findings to interested parties and stake 
holders.

How does it work?
---------------------------------

Being able to simulate anything in the world is a daunting task. Instead of providing calculation
models for every domain, Movici provides tools for connecting the different domain models that the
user already has. By defining a common interface, different domains can interact with each other
and interdependencies between these domains can be exposed.

Movici does this by defining two things:
 
* A data model: A common way that data is organised, so that domain calculation models know what
  to expect. To prevent confusion about what is called a "model", this is called the "data 
  format". A collection of data concerning a specific domain is called a "Dataset"
* A calculation model interface: The way that calculation models (or just "Models") are triggered
  and notified about changes in their domain and are expected to update their calculations

Models and Datasets can now be brought together in a Scenario. A Scenario is a description of 
which Models connect to which Datasets and  Within a scenario, models and data
are "brought to life" by introducing a timeline. On the timeline, some Models can initiate events
(changes to the common world state), while others only react to these events/changes. 
