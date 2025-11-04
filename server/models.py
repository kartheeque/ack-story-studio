from typing import List, Optional
from pydantic import BaseModel

# ---------- Shared schemas ----------

class Panel(BaseModel):
    n: int
    title: str
    prompt: str

class PromptsResponse(BaseModel):
    background: str
    panels: List[Panel]
    model: str

class StyleOpts(BaseModel):
    size: Optional[str] = "1024x1536"

# ---------- Request payloads ----------

class PromptsRequest(BaseModel):
    story: str
    # could include style later if desired

class GenerateFromBlockRequest(BaseModel):
    block: str
    image: Optional[StyleOpts] = None
    useImageReferences: bool = False
