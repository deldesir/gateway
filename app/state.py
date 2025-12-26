from pydantic import BaseModel
from typing import Optional

class AgentState(BaseModel):
    """
    Shared LangGraph state for the agent.
    """

    user_input: str
    response: Optional[str] = None
    messages: list[str] = []
    step: int = 0
    max_steps: int = 3