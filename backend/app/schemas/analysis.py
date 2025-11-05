from pydantic import BaseModel

class BufferRequest(BaseModel):
    layer_name: str
    distance: float  # meter