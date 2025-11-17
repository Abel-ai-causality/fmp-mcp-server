from pydantic import BaseModel, Field


class DisplayMeta(BaseModel):
    display_name: str = Field(..., description="A short and context related name for the purpose of displaying this tool call on ui, verb + noun (<= 30 characters and 3 words)")
    display_description: str = Field(..., description="A brief description of why this tool is being called")

