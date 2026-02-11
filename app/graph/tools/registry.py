from typing import Dict, List, Any, Callable
from langchain_core.tools import BaseTool

from app.logger import setup_logger
from app.graph.tools.rapidpro import fetch_dossier, start_flow
from app.graph.tools.retrieval import retrieve_context
from app.graph.tools.mocks import check_stock, order_delivery, schedule_viewing

logger = setup_logger().bind(name="tool.registry")

class ToolRegistry:
    """
    Central registry for all available tools in the system.
    Maps string identifiers to actual Tool objects.
    """
    
    # Global map of all available tools
    # Key: String ID used in DB (e.g., "rapidpro_dossier")
    # Value: The LangChain tool function/object
    _TOOLS: Dict[str, BaseTool] = {
        "rapidpro_dossier": fetch_dossier,
        "rapidpro_flow": start_flow,
        "retrieval": retrieve_context,
        "check_stock": check_stock,
        "order_delivery": order_delivery,
        "schedule_viewing": schedule_viewing,
    }

    @classmethod
    def get_all_tool_names(cls) -> List[str]:
        """List all registered tool IDs."""
        return list(cls._TOOLS.keys())

    @classmethod
    def get_tools(cls, tool_ids: List[str]) -> List[BaseTool]:
        """
        Get a list of Tool objects based on a list of IDs.
        Silently ignores invalid IDs but logs warnings.
        """
        selected_tools = []
        for tid in tool_ids:
            tool = cls._TOOLS.get(tid)
            if tool:
                selected_tools.append(tool)
            else:
                logger.warning(f"Tool ID '{tid}' not found in registry.")
        return selected_tools
