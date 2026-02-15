"""Dispatch engine strategies for hybrid microgrid simulation.

Available strategies:

* **load_following** -- RE first, then battery, generator, grid (simplest).
* **cycle_charging** -- Generator at full capacity when triggered by low SOC.
* **combined** -- Adaptive switching between load-following and cycle-charging.
* **optimal** -- LP-based cost minimisation using the HiGHS solver.
"""

from .load_following import dispatch_load_following
from .cycle_charging import dispatch_cycle_charging
from .combined import dispatch_combined
from .optimal import dispatch_optimal

__all__ = [
    "dispatch_load_following",
    "dispatch_cycle_charging",
    "dispatch_combined",
    "dispatch_optimal",
]
