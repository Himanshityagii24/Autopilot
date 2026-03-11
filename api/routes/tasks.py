from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timezone

from schemas.task import (
    CreateTaskRequest,
    TaskCreatedResponse,
    TaskDetailResponse,
    TaskListResponse,
    StepResponse,
    ArtifactResponse
)
from models.task import get_task, get_all_tasks, delete_task
from models.step import get_steps, get_artifacts
from services.task_runner import start_task, get_cancel_event

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()



@router.post("", response_model=TaskCreatedResponse, status_code=201)
async def create_task(request: CreateTaskRequest):
    """
    Submit a natural language goal.
    Returns task_id immediately — execution runs in background.
    """
    if not request.goal or not request.goal.strip():
        raise HTTPException(status_code=422, detail="Goal cannot be empty")

    task_id = await start_task(request.goal.strip())

    return TaskCreatedResponse(
        task_id=task_id,
        status="queued",
        created_at=_now()
    )



@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: queued | planning | running | completed | failed | cancelled"
    )
):
    """
    List all tasks with optional status filter.
    Uses DB index on status column — stays fast at 10,000+ records.
    """
    valid_statuses = {"queued", "planning", "running", "completed", "failed", "cancelled"}

    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )

    rows = await get_all_tasks(status)
    tasks = []

    for row in rows:
        steps_rows = await get_steps(row["id"])
        artifacts_rows = await get_artifacts(row["id"])

        tasks.append(TaskDetailResponse(
            task_id=row["id"],
            goal=row["goal"],
            status=row["status"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            error=row["error"],
            steps=[
                StepResponse(
                    step_number=s["step_number"],
                    tool_name=s["tool_name"],
                    input=s["input"],
                    output=s["output"],
                    status=s["status"],
                    duration_ms=s["duration_ms"],
                    attempt=s["attempt"]
                ) for s in steps_rows
            ],
            artifacts=[
                ArtifactResponse(
                    filename=a["filename"],
                    file_path=a["file_path"],
                    created_at=a["created_at"]
                ) for a in artifacts_rows
            ]
        ))

    return TaskListResponse(tasks=tasks, total=len(tasks))



@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task_detail(task_id: str):
    """
    Get full task result — status, all steps with inputs/outputs, artifacts.
    """
    row = await get_task(task_id)

    if not row:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    steps_rows = await get_steps(task_id)
    artifacts_rows = await get_artifacts(task_id)

    return TaskDetailResponse(
        task_id=row["id"],
        goal=row["goal"],
        status=row["status"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        error=row["error"],
        steps=[
            StepResponse(
                step_number=s["step_number"],
                tool_name=s["tool_name"],
                input=s["input"],
                output=s["output"],
                status=s["status"],
                duration_ms=s["duration_ms"],
                attempt=s["attempt"]
            ) for s in steps_rows
        ],
        artifacts=[
            ArtifactResponse(
                filename=a["filename"],
                file_path=a["file_path"],
                created_at=a["created_at"]
            ) for a in artifacts_rows
        ]
    )




@router.delete("/{task_id}", status_code=200)
async def cancel_task(task_id: str):
    """
    Cancel a running task.
    Gracefully interrupts execution — does not corrupt DB records.
    """
    row = await get_task(task_id)

    if not row:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if row["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Task is already {row['status']} — cannot cancel"
        )

    
    cancel_event = get_cancel_event(task_id)
    if cancel_event:
        cancel_event.set()

   
    await delete_task(task_id)

    return {"message": f"Task {task_id} cancellation requested", "task_id": task_id}