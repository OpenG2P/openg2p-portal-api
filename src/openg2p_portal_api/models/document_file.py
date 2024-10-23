from pydantic import BaseModel, ConfigDict


class DocumentFile(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
