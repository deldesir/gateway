from typing import Optional, List, Dict, Any
from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """
    Core agent state used across the LangGraph workflow.

    This state mirrors the design principles used in PhiloAgents:
    - Messages are append-only and managed by LangGraph.
    - State holds semantic artifacts, not decisions.
    - No flags, counters, or tool-usage markers are present.

    Attributes:
        persona:
            Identifier for the active persona (e.g., "jim", "michael", "dwight").

        user_input:
            The raw user query that initiated the current graph execution.

        retrieved_chunks:
            Canonical factual text chunks retrieved from the FAISS vector store.

        retrieved_context:
            A consolidated or post-processed representation of retrieved_chunks
            intended for prompt injection.

        conversation_summary:
            A rolling semantic summary of prior interactions for long-term
            continuity and memory compression.

        persona_memory:
            Persona-scoped long-term memory persisted via a JSON checkpointer.

        final_response:
            The final response sent out to the user.
    """

    persona: str
    user_input: str
    retrieved_chunks: Optional[List[str]] = None
    context_summary: Optional[str] = None
    conversation_summary: Optional[str] = None
    persona_memory: Optional[Dict[str, Any]] = None
    final_response: Optional[str] = None
    
    # Konex Persona Engine
    dossier: Dict[str, Any]
    trust_score: int
    mood: str # Literal["Happy", "Neutral", "Annoyed"] - kept simple for TypedDict compatibility
