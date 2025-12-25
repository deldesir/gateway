from app.graph import build_graph
from app.state import AddState
from app.logger import setup_logger

logger = setup_logger().bind(name='MAIN')

def main():
    logger.info("Starting the application...")

    graph = build_graph()

    final_state = graph.invoke({'a': 5, 'b': 7})

    logger.info(f"Final State: {final_state}")
    logger.success("Application finished.")

if __name__ == "__main__":
    main()
