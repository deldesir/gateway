from .registry import CommandRegistry, CommandContext

# Auto-discover commands by importing modules
from . import core
from . import crm
from . import automation
from . import content
from . import admin
from . import persona
from . import channel

from . import cost
from . import status
from . import reload
from . import skill_audit
from . import health
from . import noai
from . import broadcast

# Expose Registry and Context
__all__ = ["CommandRegistry", "CommandContext"]
