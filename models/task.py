import aiosqlite
from typing import Optional
from core.database import get_db


async def create_task(task_id: str, goal: str, created_at: str):
    """Insert a new task record with status 'queued'."""
    async with await get_db() as db:
        await db.execute(
            """
            INSERT INTO tasks (id, goal, status, created_at)
            VALUES (?, ?, 'queued', ?)
            """,
            (task_id, goal, created_at)
        )
        await db.commit()


async def get_task(task_id: str) -> Optional[aiosqlite.Row]:
    """Fetch a single task by ID. Returns None if not found."""
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,)
        )
        return await cursor.fetchone()


async def get_all_tasks(status: Optional[str] = None) -> list:
    """
    Fetch all tasks, optionally filtered by status.
    Uses index on status column for performance at 10k+ rows.
    """
    async with await get_db() as db:
        if status:
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
                (status,)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC"
            )
        return await cursor.fetchall()


async def update_task_status(
    task_id: str,
    status: str,
    completed_at: Optional[str] = None,
    error: Optional[str] = None
):
    """Update task status — called by agent loop as task progresses."""
    async with await get_db() as db:
        await db.execute(
            """
            UPDATE tasks
            SET status = ?, completed_at = ?, error = ?
            WHERE id = ?
            """,
            (status, completed_at, error, task_id)
        )
        await db.commit()


async def delete_task(task_id: str):
    """
    Cancel a task — sets status to 'cancelled'.
    Does NOT delete the record — preserves history.
    """
    async with await get_db() as db:
        await db.execute(
            "UPDATE tasks SET status = 'cancelled' WHERE id = ?",
            (task_id,)
        )
        await db.commit()