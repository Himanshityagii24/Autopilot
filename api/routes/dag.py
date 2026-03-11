from fastapi import APIRouter, HTTPException

from models.task import get_task
from models.step import get_steps

router = APIRouter(prefix="/tasks", tags=["DAG"])


@router.get("/{task_id}/dag")
async def get_task_dag(task_id: str):
    """
    Bonus: Returns the planned step graph as JSON.

    Nodes = each step with tool + status
    Edges = sequential dependencies between steps

    Since steps are linear (1→2→3), edges connect each step to the next.
    If a step references output_of_step_N, that dependency is also captured.
    """
    row = await get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    steps = await get_steps(task_id)

    if not steps:
        return {
            "task_id": task_id,
            "goal": row["goal"],
            "status": row["status"],
            "nodes": [],
            "edges": []
        }

    # Build nodes
    nodes = [
        {
            "step": s["step_number"],
            "tool": s["tool_name"],
            "input": s["input"],
            "output": s["output"],
            "status": s["status"],
            "duration_ms": s["duration_ms"],
            "attempt": s["attempt"]
        }
        for s in steps
    ]

    # Build edges — sequential + detect output_of_step_N references
    edges = []
    for s in steps:
        step_num = s["step_number"]
        tool_input = s["input"] or ""

        # Sequential edge — every step connects to next
        next_step = step_num + 1
        if next_step <= len(steps):
            edges.append({
                "from": step_num,
                "to": next_step,
                "type": "sequential"
            })

        # Dependency edge — if input references a previous step output
        for other in steps:
            ref = f"output_of_step_{other['step_number']}"
            if ref in tool_input and other["step_number"] != step_num:
                edges.append({
                    "from": other["step_number"],
                    "to": step_num,
                    "type": "data_dependency"
                })

    return {
        "task_id": task_id,
        "goal": row["goal"],
        "status": row["status"],
        "total_steps": len(nodes),
        "nodes": nodes,
        "edges": edges
    }