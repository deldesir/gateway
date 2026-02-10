import logging
from typing import Dict, Any, Callable, Awaitable, Optional, List
from dataclasses import dataclass

# Set up logging for commands
logger = logging.getLogger("konex_commands")

@dataclass
class CommandContext:
    user_id: str
    thread_id: str
    persona: str
    args: List[str]
    checkpointer: Any
    
    # Message content that triggered the command
    raw_message: str 

# Command Handler Type: Takes context, returns response string
CommandHandler = Callable[[CommandContext], Awaitable[str]]

class CommandRegistry:
    """
    A simple registry to map command strings to handler functions.
    Example: 
        @CommandRegistry.register("reset")
        async def reset(ctx): ...
    """
    _commands: Dict[str, CommandHandler] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a function as a command handler."""
        def decorator(func: CommandHandler):
            cls._commands[name.lower()] = func
            return func
        return decorator

    @classmethod
    def has_command(cls, name: str) -> bool:
        """Checks if a command is registered."""
        return name.lower().lstrip("/#") in cls._commands

    @classmethod
    async def execute(cls, command_string: str, context: CommandContext) -> Optional[str]:
        """
        Parses command string and executes handler.
        Returns response string if handled, None otherwise.
        """
        parts = command_string.strip().split()
        if not parts:
            return None
            
        command_name = parts[0].lstrip("/#").lower()
        context.args = parts[1:]
        
        handler = cls._commands.get(command_name)
        if not handler:
            return None # Not a known command
        
        try:
            logger.info(f"Executing command '{command_name}' for user {context.user_id}")
            return await handler(context)
        except Exception as e:
            logger.error(f"Error executing command {command_name}: {e}", exc_info=True)
            return f"❌ System Error while executing command `{command_name}`: {str(e)}"
