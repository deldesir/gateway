from loguru import logger
import sys

def setup_logger():
    """
    Configures and returns a loguru logger with colored,
    structured, production-grade output.
    """
    logger.remove()

    logger.add(
        sys.stdout,
        level="INFO",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level}</level> | "
            "<cyan>{extra[name]}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    return logger
