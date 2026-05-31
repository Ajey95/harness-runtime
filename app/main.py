from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import asyncio
import uuid

from .runtime import ExecutionRuntime
from .models import IncidentRequest, TaskRequest
from . import db
from .incidents import build_demo_incident
from .verifier import run_verification
try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
except Exception:
    generate_latest = None
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"

app = FastAPI(title="Harness Runtime MVP")
runtime = ExecutionRuntime()

# Allow CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/tasks")
async def create_task(req: TaskRequest):
    # generate task id and launch task in background
    task_id = req.task_id or str(uuid.uuid4())
    asyncio.create_task(
        runtime.start_task(
            req.description,
            req.repo_path,
            task_id=task_id,
            incident_id=req.incident_id,
            health_url=req.health_url,
            container_name=req.container_name,
        )
    )

    return {
        "status": "started",
        "task_id": task_id,
        "description": req.description,
    }


@app.get("/traces")
async def list_traces(task_id: Optional[str] = None):
    if task_id:
        traces = db.get_traces(task_id)
        if traces is None:
            raise HTTPException(status_code=404, detail="task not found")
        return {"task_id": task_id, "traces": traces}
    return db.get_traces()


@app.post("/approvals/{task_id}")
async def post_approval(
    task_id: str,
    approved: bool = True,
    approver: Optional[str] = None,
    note: Optional[str] = None,
) -> dict:
    db.save_approval(task_id, approved, approver, note)
    report = db.get_report(task_id)
    should_resume = bool(
        approved
        and report
        and report.get("status") == "pending_approval"
    )
    if should_resume:
        asyncio.create_task(runtime.resume_task(task_id))
    return {
        "task_id": task_id,
        "approved": approved,
        "resume_started": should_resume,
    }


@app.get("/approvals/{task_id}")
async def get_approval(task_id: str):
    approval = db.get_approval(task_id)
    if not approval:
        raise HTTPException(status_code=404, detail="approval not found")
    return approval


@app.get("/approvals")
async def list_approvals():
    return db.get_all_approvals()


@app.post("/incidents/demo-docker")
async def trigger_demo_incident(req: IncidentRequest):
    incident_id = str(uuid.uuid4())
    incident = build_demo_incident(
        repo_path=req.repo_path,
        description=req.description,
        health_url=req.health_url,
        container_name=req.container_name,
    )
    db.save_incident(incident_id, incident, status="detected")
    task_id = None
    if req.auto_start:
        task_id = str(uuid.uuid4())
        db.update_incident(
            incident_id,
            status="runtime_started",
            task_id=task_id,
            payload_updates={"task_id": task_id},
        )
        asyncio.create_task(
            runtime.start_task(
                incident["description"],
                incident["repo_path"],
                task_id=task_id,
                incident_id=incident_id,
                health_url=incident["health_url"],
                container_name=incident["container_name"],
            )
        )
    return {
        "incident_id": incident_id,
        "task_id": task_id,
        "status": "runtime_started" if task_id else "detected",
        "incident": incident,
    }


@app.get("/incidents")
async def list_incidents():
    return db.get_incidents()


@app.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    incident = db.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@app.post("/verify/{task_id}")
async def post_verify(
    task_id: str,
    repo_path: Optional[str] = None,
    health_url: Optional[str] = None,
    container_name: Optional[str] = None,
):
    # Start verification in background
    asyncio.create_task(
        run_verification(
            task_id,
            repo_path,
            health_url=health_url,
            container_name=container_name,
        )
    )
    return {"task_id": task_id, "status": "verification_started"}


@app.get("/verify/{task_id}")
async def get_verify(task_id: str):
    ver = db.get_verification(task_id)
    if not ver:
        raise HTTPException(status_code=404, detail="verification not found")
    return ver


@app.get("/reports")
async def list_reports():
    return db.get_reports()


@app.get("/reports/{task_id}")
async def get_report(task_id: str):
    report = db.get_report(task_id)
    if not report:
        raise HTTPException(status_code=404, detail="report not found")
    return report


@app.get("/metrics")
async def list_metrics():
    return db.get_metrics()


@app.get("/prometheus")
async def prometheus_metrics():
    """Expose Prometheus-formatted metrics for scraping."""
    if not generate_latest:
        return Response(
            content=b"# prometheus_client not available\n",
            media_type="text/plain",
        )
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@app.get("/metrics/{task_id}")
async def get_metrics(task_id: str):
    metrics = db.get_metrics(task_id=task_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="metrics not found")
    return metrics
