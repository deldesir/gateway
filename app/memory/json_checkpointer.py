import json
import os
from typing import Optional
from app.graph.state import AgentState
from app.memory.serializer import to_json_safe


class JsonCheckpointer:
    """
    Simple JSON-based checkpointer keyed by thread_id.
    """

    def __init__(self, path: str = "memory.json"):
        self.path = path
        if not os.path.exists(self.path):
            with open(self.path, "w") as f:
                json.dump({}, f)

    def load(self, thread_id: str) -> Optional[dict]:
        with open(self.path, "r") as f:
            data = json.load(f)

        return data.get(thread_id)

    def save(self, thread_id: str, state: dict):
        with open(self.path, "r") as f:
            data = json.load(f)

        data[thread_id] = to_json_safe(state)

        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)
