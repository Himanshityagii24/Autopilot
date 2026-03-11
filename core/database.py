import aiosqlite
from core.config import settings

DATABASE_URL = settings.database_url


def get_db():
    """
    Returns a context manager for DB connection.
    Usage:
        async with get_db() as db:
            ...
    """
    db = aiosqlite.connect(DATABASE_URL)
    return db


async def init_db():
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript("""

            CREATE TABLE IF NOT EXISTS tasks (
                id              TEXT PRIMARY KEY,
                goal            TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'queued',
                created_at      TEXT NOT NULL,
                completed_at    TEXT,
                error           TEXT
            );

            CREATE TABLE IF NOT EXISTS task_steps (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id         TEXT NOT NULL,
                step_number     INTEGER NOT NULL,
                tool_name       TEXT NOT NULL,
                input           TEXT,
                output          TEXT,
                status          TEXT NOT NULL DEFAULT 'pending',
                duration_ms     INTEGER,
                prompt_used     TEXT,
                attempt         INTEGER DEFAULT 1,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            );

            CREATE TABLE IF NOT EXISTS task_artifacts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id         TEXT NOT NULL,
                filename        TEXT NOT NULL,
                file_path       TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status
                ON tasks(status);

            CREATE INDEX IF NOT EXISTS idx_tasks_created_at
                ON tasks(created_at);

            CREATE INDEX IF NOT EXISTS idx_task_steps_task_id
                ON task_steps(task_id);

            CREATE INDEX IF NOT EXISTS idx_task_artifacts_task_id
                ON task_artifacts(task_id);

        """)
        await db.commit()
        print("Database initialized successfully")