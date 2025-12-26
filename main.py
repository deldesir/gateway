from dotenv import load_dotenv

load_dotenv()

from app.graph.graph import build_graph
from app.state import AgentState
from app.logger import setup_logger


logger = setup_logger().bind(name="MAIN")


def main():
    logger.info("Starting the application...")

    graph = build_graph()

    final_state = graph.invoke({"user_input": "What do you think about paper sales this time? what should be the next steps?"})

    logger.info(f"Final State: {final_state}")
    logger.success("Application finished.")


if __name__ == "__main__":
    main()
