import aiosqlite
from typing import Optional
from core.database import get_db


async def create_task(task_id: str, goal: str, created_at: str):
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "INSERT INTO tasks (id, goal, status, created_at) VALUES (?, ?, 'queued', ?)",
            (task_id, goal, created_at)
        )
        await db.commit()


async def get_task(task_id: str) -> Optional[aiosqlite.Row]:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        )
        return await cursor.fetchone()


async def get_all_tasks(status: Optional[str] = None) -> list:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
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
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE tasks SET status = ?, completed_at = ?, error = ? WHERE id = ?",
            (status, completed_at, error, task_id)
        )
        await db.commit()


async def delete_task(task_id: str):
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE tasks SET status = 'cancelled' WHERE id = ?",
            (task_id,)
        )
        await db.commit()