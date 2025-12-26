from typing import Any
from pydantic import BaseModel


def to_json_safe(obj: Any):
    """
    Recursively converts Pydantic models into JSON-serializable objects.
    """
    if isinstance(obj, BaseModel):
        return obj.model_dump()

    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [to_json_safe(v) for v in obj]

    return obj
