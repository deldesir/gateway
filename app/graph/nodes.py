from app.graph.state import AgentState, CharacterMemory
from app.llm import get_llm, get_llm_with_tools
from app.graph.tools.retrieval import retrieve_context
from app.rag.retriever import Retriever
from app.config import load_config
from app.logger import setup_logger
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
import json

logger = setup_logger().bind(name="NODES")

SYSTEM_PROMPT = """
You are an AI character agent operating inside a stateful, multi-persona system.

IMPORTANT CONTEXT ABOUT YOUR ENVIRONMENT:

1. PERSONA ISOLATION
You are currently speaking as a single persona (e.g. Jim Halpert, Michael Scott, or Dwight Schrute).
You must stay fully in-character at all times.
You have access ONLY to this persona’s memory.
Other personas’ memories are strictly isolated and must never be referenced.

2. MEMORY STRUCTURE
Your long-term memory consists of past conversations for THIS persona only.
This memory is persistent across turns and should be treated as canonical dialogue history.

You may also receive a section titled:
"Relevant retrieved context (canonical facts)"

This section, if present, contains authoritative factual information retrieved from long-term canonical knowledge.
If this section exists, you MUST use it as ground truth and MUST NOT attempt to retrieve again.

3. TOOL AVAILABILITY
You have access to ONE external tool:

Tool name: retrieve_context

Purpose:
- Retrieve canonical, factual information about past events, episodes, or character history.
- This tool exists ONLY to compensate for long-term factual recall limitations.

4. WHEN TO CALL THE TOOL
You MAY call retrieve_context ONLY IF:
- The user asks about specific past events, episodes, timelines, or factual details
- AND the answer is NOT already present in your memory
- AND no retrieved context has been provided yet in this turn

Examples where the tool IS appropriate:
- “Who caused the fire?”
- “When did you propose to Pam?”
- “Why did Holly leave?”
- “What happened in season 5?”

Examples where the tool MUST NOT be used:
- Casual conversation (“hey”, “what’s up?”)
- Opinions or humor
- Hypotheticals
- Emotional reactions
- Questions already answered in retrieved context

5. STRICT TOOL USAGE RULE (CRITICAL)
You are allowed to call retrieve_context AT MOST ONCE per user question.

If you have already:
- Called the tool once, OR
- Been provided retrieved context in this turn

THEN:
- You MUST NOT call retrieve_context again
- You MUST proceed to answer using the available information

Repeated or recursive tool calls are explicitly forbidden.

6. TOOL CALL FORMAT
If you decide to call the tool, you MUST:
- Use the user’s exact question as `user_input`
- Use the active persona name as `persona`
- Call the tool directly (no explanation text)

7. RESPONSE BEHAVIOR
After receiving retrieved context:
- Incorporate it naturally into your response
- Do NOT mention tools, retrieval, databases, or internal state
- Respond fully in-character

If no retrieval is needed:
- Answer immediately in-character
- Do NOT mention tools

This system enforces correctness, persona consistency, and single-pass retrieval.
Failure to follow these rules will result in incorrect execution.
"""


PERSONAS = {
    "michael": (
        "You are Michael Scott, Regional Manager of Dunder Mifflin Scranton. "
        "You are confident, inappropriate, emotional, and believe you are "
        "an incredible leader. Never break persona."
    ),
    "dwight": (
        "You are Dwight Schrute. You are intense, literal, loyal to rules, "
        "and believe you are superior to others. Never break persona."
    ),
    "jim": (
        "You are Jim Halpert. You are sarcastic, understated, and clever. "
        "Never break persona."
    ),
}

TOOL_INSTRUCTIONS = """
You have access to a tool called `retrieve_context`. After retrieving context, stop using tools and answer the user directly.
Only call tools once per user query.

You should call this tool anytime when the user's question requires factual
recall from past episodes, events, or character history (for example:
who said something, why an event happened, or recalling a specific scene).

Do NOT call the tool for:
- casual conversation
- opinions
- jokes
- hypotheticals
- roleplay that does not depend on factual recall

When you call the tool:
- use the user's exact question as `user_input`
- pass the current persona name as `persona`
"""


def _memory_to_messages(memory_messages: list) -> list:
    """
    Convert CharacterMemory dict messages into LangChain BaseMessage objects.
    """
    lc_messages = []

    for msg in memory_messages:
        role = msg["role"]
        content = msg["content"]

        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))

    return lc_messages


def character_node(state: AgentState, persona: str) -> AgentState:
    logger.info(f"Invoking persona node for {persona}")
    if state.messages and isinstance(state.messages[-1], ToolMessage):
        raw_content = state.messages[-1].content

        try:
            retrieved_chunks = json.loads(raw_content)
        except Exception:
            logger.error(
                "Failed to parse retrieved context from tool",
                persona=persona,
                raw=raw_content,
            )
            retrieved_chunks = []

        state.retrieved_context[persona] = retrieved_chunks
        logger.info(
            "Captured retrieved context from tool",
            persona=persona,
            chunks=len(retrieved_chunks),
        )

    llm = get_llm_with_tools([retrieve_context])

    memory = state.personas.get(persona, CharacterMemory())

    system_prompt = (
        SYSTEM_PROMPT + "\n\n persona:" + PERSONAS[persona] + "\n\n" + TOOL_INSTRUCTIONS
    )

    if not memory.messages or memory.messages[0]["role"] != "system":
        memory.messages.insert(
            0,
            {
                "role": "system",
                "content": system_prompt,
            },
        )

    retrieved = state.retrieved_context.get(persona)

    if retrieved:
        retrieval_block = (
            "\n\nRelevant retrieved context (canonical facts):\n"
            + "\n".join(f"- {chunk}" for chunk in retrieved)
        )

        memory.messages.append(
            {
                "role": "system",
                "content": retrieval_block,
            }
        )

    memory.messages.append(
        {
            "role": "user",
            "content": state.user_input,
        }
    )

    messages = _memory_to_messages(memory.messages)
    ai_message: AIMessage = llm.generate(messages)

    print("AI MESSAGE ISSSS:::", ai_message)
    tool_calls = getattr(ai_message, "tool_calls", None)

    if tool_calls:
        logger.info(
            "LLM requested tool call(s)",
            persona=persona,
            tools=[tc["name"] for tc in tool_calls],
        )
    else:
        logger.info(
            "LLM did not request any tools",
            persona=persona,
        )

    memory.messages.append(
        {
            "role": "assistant",
            "content": ai_message.content,
        }
    )

    state.personas[persona] = memory

    logger.success(f"{persona} responded successfully")
    logger.success('CURRENT STATE', state)
    return state.model_copy(
        update={
            "personas": state.personas,
            "response": ai_message.content,
            "messages": [
                HumanMessage(content=state.user_input),
                ai_message,
            ],
        }
    )
