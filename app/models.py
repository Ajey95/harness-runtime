from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class TaskRequest(BaseModel):
    task_id: Optional[str] = None
    repo_path: Optional[str] = None
    description: str


class TraceEntry(BaseModel):
    timestamp: datetime
    step: str
    detail: Optional[str] = None


class TaskResult(BaseModel):
    task_id: str
    status: str
    traces: List[TraceEntry] = []
