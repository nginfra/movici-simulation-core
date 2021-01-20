# Movici Simulation Core
Copyright 2020ff NGinfra

Movici simulation core is a set of tools and models for running a simulations on infrastructure 
according to the Movici standard.

## Models
### Movici Tape Player
The tape player reads and produces updates from a `tapefile` dataset. The `tapefile` may be 
available as a dataset from the start, or it may be produced as as t0-update by another model.

### Overlap Status

This model does one-to-many spatial mapping on configured entities. 
It then publishes overlap status for these entities.

#### Configuration:

* from_dataset: from part in the one-to-many relationship
* from_dataset_geometry: one of points/lines
* to_points_datasets: to part where entities are points in the one-to-many relationship
* to_lines_datasets: to part where entities are lines in the one-to-many relationship
* check_overlapping_from: optional property to check in the from_dataset. Otherwise assumes status is always active
* check_overlapping_to: optional property to check in the "to datasets". Otherwise assumes status is always active
* distance_threshold: threshold for which entities overlap by distance
* display_name_template: a string that configures the display name for the overlapping entities.
  Valid variables in display_name_template: {from_dataset_name} {to_dataset_name} {from_reference} {to_reference} {from_id} {to_id}
