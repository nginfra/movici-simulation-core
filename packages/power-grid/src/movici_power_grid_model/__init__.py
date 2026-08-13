"""Power grid models for Movici.

* :class:`Model` performs electrical network analysis using the
  power-grid-model library: power flow, state estimation, and short circuit
  calculations.
* :class:`CascadeModel` runs the short circuit -> protection trips -> power
  flow cascade for hazard scenarios.
* :class:`FaultActivationModel` activates faults when a monitored node
  attribute (e.g. flood depth) crosses a threshold.
"""

from .cascade import Model as CascadeModel
from .fault_activation import Model as FaultActivationModel
from .model import Model

__all__ = ["Model", "CascadeModel", "FaultActivationModel"]
