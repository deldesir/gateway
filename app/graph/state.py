from pydantic import BaseModel
from typing_extensions import Dict, List, Optional, TypedDict


class Message(TypedDict):
    role: str
    content: str


class CharacterMemory(BaseModel):
    messages: List[Message] = []


class AgentState(BaseModel):
    """
    State scoped to a single user session (thread).
    Character memories are namespaced inside this state.
    """

    user_input: Optional[str] = None
    personas: Dict[str, CharacterMemory] = {}
    response: Optional[str] = None
