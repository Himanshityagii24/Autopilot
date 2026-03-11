import aiosqlite
from typing import Optional
from core.database import get_db




async def create_step(
    task_id: str,
    step_number: int,
    tool_name: str,
    input: str,
    prompt_used: Optional[str] = None  
):
    """Insert a new step as 'running' when agent starts executing it."""
    async with await get_db() as db:
        await db.execute(
            """
            INSERT INTO task_steps
                (task_id, step_number, tool_name, input, status, prompt_used)
            VALUES (?, ?, ?, ?, 'running', ?)
            """,
            (task_id, step_number, tool_name, input, prompt_used)
        )
        await db.commit()


async def update_step(
    task_id: str,
    step_number: int,
    status: str,
    output: Optional[str] = None,
    duration_ms: Optional[int] = None,
    attempt: Optional[int] = None      
):
    """Update step once it completes, fails, or is cancelled."""
    async with await get_db() as db:
        await db.execute(
            """
            UPDATE task_steps
            SET status = ?, output = ?, duration_ms = ?, attempt = ?
            WHERE task_id = ? AND step_number = ?
            """,
            (status, output, duration_ms, attempt, task_id, step_number)
        )
        await db.commit()


async def get_steps(task_id: str) -> list:
    """Fetch all steps for a task ordered by step number."""
    async with await get_db() as db:
        cursor = await db.execute(
            """
            SELECT * FROM task_steps
            WHERE task_id = ?
            ORDER BY step_number ASC
            """,
            (task_id,)
        )
        return await cursor.fetchall()




async def create_artifact(
    task_id: str,
    filename: str,
    file_path: str,
    created_at: str
):
    """Record a file artifact created by the write_file tool."""
    async with await get_db() as db:
        await db.execute(
            """
            INSERT INTO task_artifacts (task_id, filename, file_path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (task_id, filename, file_path, created_at)
        )
        await db.commit()


async def get_artifacts(task_id: str) -> list:
    """Fetch all artifacts produced by a task."""
    async with await get_db() as db:
        cursor = await db.execute(
            """
            SELECT * FROM task_artifacts
            WHERE task_id = ?
            ORDER BY created_at ASC
            """,
            (task_id,)
        )
        return await cursor.fetchall()