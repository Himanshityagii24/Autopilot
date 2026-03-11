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
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
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
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
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
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM task_steps WHERE task_id = ? ORDER BY step_number ASC",
            (task_id,)
        )
        return await cursor.fetchall()


async def create_artifact(
    task_id: str,
    filename: str,
    file_path: str,
    created_at: str
):
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "INSERT INTO task_artifacts (task_id, filename, file_path, created_at) VALUES (?, ?, ?, ?)",
            (task_id, filename, file_path, created_at)
        )
        await db.commit()


async def get_artifacts(task_id: str) -> list:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM task_artifacts WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,)
        )
        return await cursor.fetchall()