"""whorl.agents — deployed agents.

Re-exports the public agent surface so `from whorl.agents import Yvette`
works instead of requiring the deeper `whorl.agents.yvette` path.
"""

from .yvette import Yvette, interactive_session

__all__ = ["Yvette", "interactive_session"]
