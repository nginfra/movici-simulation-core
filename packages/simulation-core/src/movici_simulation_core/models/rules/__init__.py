"""Rules Model for conditional attribute updates.

This model updates entity attributes based on conditions involving:
- Simulation time (<simtime>)
- Clock time (<clocktime>)
- Attribute values from source entities
- Logical combinations (AND/OR) of conditions
"""

from .model import Model

__all__ = ["Model"]
