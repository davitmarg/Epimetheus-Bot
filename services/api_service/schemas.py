from typing import List, Optional

from pydantic import BaseModel


class ManualTriggerRequest(BaseModel):
    doc_id: Optional[str] = None


class CreateDocumentRequest(BaseModel):
    name: str
    folder_id: Optional[str] = None
    initial_content: Optional[str] = ""
    tags: Optional[List[str]] = None
    description: Optional[str] = None


class UpdateMetadataRequest(BaseModel):
    name: Optional[str] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
