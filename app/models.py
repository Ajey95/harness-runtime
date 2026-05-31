from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class TaskRequest(BaseModel):
    task_id: Optional[str] = None
    repo_path: Optional[str] = None
    incident_id: Optional[str] = None
    health_url: Optional[str] = None
    container_name: Optional[str] = None
    description: str


class IncidentRequest(BaseModel):
    repo_path: Optional[str] = None
    description: Optional[str] = None
    health_url: Optional[str] = None
    container_name: Optional[str] = None
    auto_start: bool = True


class TraceEntry(BaseModel):
    timestamp: datetime
    step: str
    detail: Optional[str] = None


class TaskResult(BaseModel):
    task_id: str
    status: str
    traces: List[TraceEntry] = []
