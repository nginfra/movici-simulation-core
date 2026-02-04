.. |required| replace:: (**required**)

Opportunities Model
===================

The opportunities model (``"opportunity"``) tracks coordination opportunities
between infrastructure activities by monitoring spatial overlaps.

Use cases include:

* Identifying missed opportunities for combined infrastructure works
* Calculating potential savings from coordinated maintenance
* Analyzing infrastructure work scheduling efficiency

How It Works
------------

1. Monitors the overlap status dataset for active overlaps
2. When an overlap becomes active, checks if the opportunity was "taken"
   (indicated by a status attribute being true)
3. Calculates opportunity value based on line length and cost per meter
4. Tracks both taken and missed opportunities

An **opportunity is taken** when:
  * An overlap is active (two infrastructure elements are in proximity)
  * AND the "opportunity taken" attribute is true

An **opportunity is missed** when:
  * An overlap is active
  * BUT the "opportunity taken" attribute is false or undefined

Configuration Options
---------------------

+---------------------------+---------+-------------------------------------------+
| Option                    | Type    | Description                               |
+===========================+=========+===========================================+
| overlap_dataset           | array   | ``[dataset_name]`` with overlap records   |
+---------------------------+---------+-------------------------------------------+
| opportunity_entity        | array   | ``[dataset_name, entity_group_name]``     |
+---------------------------+---------+-------------------------------------------+
| opportunity_taken_property| array   | ``[attribute_name]`` boolean status       |
+---------------------------+---------+-------------------------------------------+
| total_length_property     | array   | ``[attribute_name]`` for total length     |
+---------------------------+---------+-------------------------------------------+
| cost_per_meter            | number  | Cost factor for opportunity calculation   |
+---------------------------+---------+-------------------------------------------+

Example Configuration
---------------------

.. code-block:: json

    {
        "name": "road_cable_opportunities",
        "type": "opportunity",
        "overlap_dataset": ["road_cable_overlaps"],
        "opportunity_entity": ["road_network", "road_segment_entities"],
        "opportunity_taken_property": ["maintenance.excavation_active"],
        "total_length_property": ["coordination.opportunity_length"],
        "cost_per_meter": 150.0
    }

Output Attributes
-----------------

The model publishes to the opportunity entity:

+----------------------------------+---------------------------------------------+
| Attribute                        | Description                                 |
+==================================+=============================================+
| ``coordination.opportunity``     | Value of taken opportunity (length * cost)  |
+----------------------------------+---------------------------------------------+
| ``coordination.missed_opportunity``| Value of missed opportunity (length * cost)|
+----------------------------------+---------------------------------------------+
| (total_length_property)          | Length of entities with taken opportunities |
+----------------------------------+---------------------------------------------+

Prerequisites
-------------

This model requires an overlap status dataset, which is typically produced by
the :doc:`overlap_status` model. The overlap dataset contains records of
spatial proximity between infrastructure entities.

Config Schema Reference
-----------------------

OpportunityConfig
^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``overlap_dataset``: ``array`` Single-element array with overlap dataset name |required|
  | ``opportunity_entity``: :ref:`OpportunityEntityGroup` |required|
  | ``opportunity_taken_property``: ``array`` Single-element array with boolean attribute name |required|
  | ``total_length_property``: ``array`` Single-element array with length attribute name |required|
  | ``cost_per_meter``: ``number`` Cost factor for opportunity calculation |required|

.. _OpportunityEntityGroup:

OpportunityEntityGroup
^^^^^^^^^^^^^^^^^^^^^^

| ``type``: ``array``

A tuple of two strings: ``[dataset_name, entity_group_name]``
