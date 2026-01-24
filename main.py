from dotenv import load_dotenv

load_dotenv()

from app.graph.graph import build_graph
from app.graph.state import AgentState
from app.memory.json_checkpointer import JsonCheckpointer
from app.logger import setup_logger
from IPython.display import Image, display

logger = setup_logger().bind(name="MAIN")


def main():
    logger.info("Starting Office Agents backend (terminal mode)")

    character = input("Choose character (michael / dwight / jim): ").strip().lower()
    user_input = input("Enter your message: ").strip()

    graph = build_graph(character)
    store = JsonCheckpointer("memory.json")

    thread_id = "user_1"  # later: real user/session id
    loaded = store.load(thread_id)
    state = AgentState(**loaded) if loaded else AgentState()
    state.user_input = user_input

    final_state = graph.invoke(state)
    store.save(thread_id, final_state)

    logger.success(f"{character} says: {final_state['response']}")


if __name__ == "__main__":
    main()
