from pydantic import BaseModel

class AddState(BaseModel):
    a: int
    b: int
    result: int | None = None