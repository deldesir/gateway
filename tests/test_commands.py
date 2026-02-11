import asyncio
from unittest.mock import AsyncMock
from app.commands.registry import CommandRegistry, CommandContext
# Ensure all commands are loaded
import app.commands

async def test_command_execution():
    # Mock Context
    mock_checkpointer = AsyncMock()
    ctx = CommandContext(
        user_id="test_user",
        thread_id="test_thread",
        persona="test_persona",
        args=[],
        checkpointer=mock_checkpointer,
        raw_message=""
    )

    # Test Built-in: Debug
    response = await CommandRegistry.execute("#debug", ctx)
    assert "**System Diagnostics**" in response, f"Debug failed: {response}"
    assert "test_user" in response

    # Test Built-in: Reset (Mocked Checkpointer)
    response = await CommandRegistry.execute("/reset", ctx)
    assert "Memory wiped" in response, f"Reset failed: {response}"
    mock_checkpointer.adelete_thread.assert_called_with("test_thread")

    # Test Built-in: Persona
    response = await CommandRegistry.execute("/persona pirate", ctx)
    assert "Persona Switch Requested" in response, f"Persona failed: {response}"
    assert "pirate" in response

    # Test Unknown Command
    response = await CommandRegistry.execute("/unknown", ctx)
    assert response is None, f"Unknown command failed: {response}"

async def test_custom_command_registration():
    # Register a new command dynamically
    @CommandRegistry.register("ping")
    async def cmd_ping(ctx: CommandContext) -> str:
        return "pong"
    
    ctx = CommandContext("u", "t", "p", [], None, "")
    response = await CommandRegistry.execute("/ping", ctx)
    assert response == "pong", f"Ping failed: {response}"

if __name__ == "__main__":
    asyncio.run(test_command_execution())
    asyncio.run(test_custom_command_registration())
    print("ALL COMMAND TESTS PASSED")
