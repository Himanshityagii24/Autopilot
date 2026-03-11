from pydantic import BaseModel, Field
from typing import Optional, List




class CreateTaskRequest(BaseModel):
    goal: str = Field(
        ...,
        min_length=1,
        description="Natural language goal for the agent to execute",
        example="Find top 3 Python frameworks and write a comparison report"
    )




class TaskCreatedResponse(BaseModel):
    task_id: str
    status: str
    created_at: str


class StepResponse(BaseModel):
    step_number: int
    tool_name: str
    input: Optional[str]
    output: Optional[str]
    status: str
    duration_ms: Optional[int]
    attempt: Optional[int]       


class ArtifactResponse(BaseModel):
    filename: str
    file_path: str
    created_at: str


class TaskDetailResponse(BaseModel):
    task_id: str
    goal: str
    status: str
    created_at: str
    completed_at: Optional[str]
    error: Optional[str]
    steps: List[StepResponse] = []
    artifacts: List[ArtifactResponse] = []


class TaskListResponse(BaseModel):
    tasks: List[TaskDetailResponse]
    total: int