from app.state import AddState
from app.logger import setup_logger

logger=setup_logger().bind(name='ADD NODE')

def add_numbers(state: AddState) -> AddState:
    logger.info(f"Adding {state.a} and {state.b}")
    state.result = state.a + state.b
    logger.success(f"Result: {state.result}")
    return state