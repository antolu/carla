"""CARLA - Coffee Aficionado, RL Agent.

An interactive reinforcement learning agent to optimize espresso brewing parameters.
"""

try:
    from ._version import version as __version__  # noqa
except ImportError:
    msg = "carla must be installed as a package. Run 'pip install -e .' from the project root."
    raise ImportError(msg) from None

from .agent import BrewingAgent
from .env import BrewingEnvironment
from .export import DataExporter
from .models import BrewAction, BrewEvaluation, BrewState

__all__ = [
    "BrewAction",
    "BrewEvaluation",
    "BrewState",
    "BrewingAgent",
    "BrewingEnvironment",
    "DataExporter",
]
