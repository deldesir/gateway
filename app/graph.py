from langgraph.graph import StateGraph, END
from app.state import AddState
from app.nodes import add_numbers
from app.logger import setup_logger

logger = setup_logger().bind(name='GRAPH')

def build_graph() -> StateGraph:
    logger.info("Building the graph...")

    graph = StateGraph(AddState)
    graph.add_node("add_numbers",add_numbers)
    graph.set_entry_point("add_numbers")
    graph.add_edge("add_numbers", END)

    logger.success("Graph built successfully")

    return graph.compile()
