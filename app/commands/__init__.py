from .registry import CommandRegistry, CommandContext

# Auto-discover commands by importing modules
from . import core
from . import crm
from . import automation
from . import content
from . import admin
from . import persona
from . import channel

# Expose Registry and Context
__all__ = ["CommandRegistry", "CommandContext"]
