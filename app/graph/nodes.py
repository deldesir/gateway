from app.graph.state import AgentState, CharacterMemory
from app.llm import get_llm
from app.config import load_config
from app.logger import setup_logger

logger = setup_logger().bind(name="NODES")

PERSONAS = {
    "michael": (
        "You are Michael Scott, Regional Manager of Dunder Mifflin Scranton. "
        "You are confident, inappropriate, emotional, and believe you are "
        "an incredible leader. Never break character."
    ),
    "dwight": (
        "You are Dwight Schrute. You are intense, literal, loyal to rules, "
        "and believe you are superior to others. Never break character."
    ),
    "jim": (
        "You are Jim Halpert. You are sarcastic, understated, and clever. "
        "Never break character."
    ),
}


def character_node(state: AgentState, character: str) -> AgentState:
    """
    Executes a single LLM call for a specific Office character
    using only that character's memory.

    Args:
        state (AgentState): Current agent state.
        character (str): Character to emulate ("michael", "dwight", "jim").
    Returns:
        AgentState: Updated agent state with LLM response.
    """
    logger.info(f"Invoking character node for {character}")
    llm = get_llm()

    memory = state.characters.get(character, CharacterMemory())

    messages = memory.messages.copy()

    if not messages or messages[0]["role"] != "system":
        messages.insert(0, {"role": "system", "content": PERSONAS[character]})

    messages.append({"role": "user", "content": state.user_input})

    response = llm.generate(messages)

    messages.append({"role": "assistant", "content": response})

    state.characters[character] = CharacterMemory(messages=messages)

    logger.success(f"{character} responded successfully")

    return state.model_copy(
        update={
            "characters": state.characters,
            "response": response,
        }
    )
