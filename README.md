# Task Autopilot — AI Agentic Task Runner

A FastAPI backend where users submit a natural language goal, an LLM agent decomposes it into steps, executes them using built-in tools, and streams progress back in real-time via SSE.

---


## Quick Start

### 1. Clone and set up environment

```bash
git clone https://github.com/Himanshityagii24/Autopilot.git
cd Autopilot
python -m venv venv

# Windows
.\venv\Scripts\activate 

# Mac/Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 4. Run the server

```bash
uvicorn main:app --reload
```

Server starts at `http://localhost:8000`

### 5. Open the UI

Open `index.html` directly in your browser — no extra setup needed.

> **Important:** The UI calls `localhost:8000` — server should  run first.

---

## Environment Variables

```env
GROQ_API_KEY=gsk_your_key_here        # Get free key at https://console.groq.com
LLM_MODEL=llama-3.1-8b-instant        # Groq model to use
LLM_TEMPERATURE=0.2                   # Lower = more deterministic
MAX_STEPS=10                          # Max steps per task (safety guardrail)
ARTIFACTS_DIR=artifacts               # Directory for write_file output
DATABASE_URL=./task_autopilot.db      # SQLite database path
MAX_RETRY_ATTEMPTS=3                  # Retry attempts for failed tools
RETRY_BASE_DELAY=1.0                  # Base delay in seconds (doubles each retry)
CACHE_ENABLED=true                    # Enable tool result caching
```

### Getting a Free Groq API Key

1. Go to [https://console.groq.com](https://console.groq.com)
2. Sign up for a free account (no credit card required)
3. Navigate to API Keys → Create API Key
4. Copy the key (starts with `gsk_`) into your `.env` file

---

## Project Structure

```
task_autopilot/
├── main.py                    # FastAPI app entry point
├── .env                       # Environment variables (not committed)
├── .env.example               # Template for environment variables
├── requirements.txt
├── README.md
├── index.html                 # UI — open directly in browser
├── core/
│   ├── config.py              # Pydantic settings
│   └── database.py            # aiosqlite connection + init_db()
├── models/
│   ├── task.py                # DB operations for tasks table
│   └── step.py                # DB operations for task_steps + artifacts
├── schemas/
│   └── task.py                # Pydantic request/response schemas
├── agent/
│   ├── planner.py             # LLM call to decompose goal into steps
│   ├── loop.py                # Core agent execution loop
│   └── tools/
│       ├── registry.py        # Tool name → function mapping
│       ├── web_search.py      # DuckDuckGo search via ddgs
│       ├── summarize.py       # LLM sub-call for summarization
│       ├── write_file.py      # Write to artifacts/ sandbox
│       ├── read_file.py       # Read from artifacts/ sandbox
│       └── http_get.py        # Fetch raw URL content via httpx
├── api/
│   └── routes/
│       ├── tasks.py           # POST, GET /tasks, GET /tasks/{id}, DELETE
│       ├── stream.py          # GET /tasks/{id}/stream (SSE)
│       └── dag.py             # GET /tasks/{id}/dag (Bonus)
├── services/
│   ├── stream_manager.py      # asyncio.Queue per task for SSE
│   └── task_runner.py         # Background task launcher
└── artifacts/                 # Files created by write_file tool
```

---

## API Endpoints

### POST /tasks — Submit a goal

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"goal": "Find top 3 Python frameworks and write a comparison report"}'
```

Response:
```json
{
  "task_id": "uuid",
  "status": "queued",
  "created_at": "2026-03-11T10:00:00Z"
}
```

---

### GET /tasks — List all tasks

```bash
curl http://localhost:8000/tasks
curl http://localhost:8000/tasks?status=running
curl http://localhost:8000/tasks?status=completed
curl http://localhost:8000/tasks?status=failed
```

---

### GET /tasks/{task_id} — Get task result

```bash
curl http://localhost:8000/tasks/your-task-id-here
```

Returns full task with all steps and their inputs/outputs.

---

### GET /tasks/{task_id}/stream — Live SSE stream

```bash
curl -N http://localhost:8000/tasks/your-task-id/stream
```

Streams events as each step executes:
```
data: {"step": 1, "tool": "web_search", "input": "top Python frameworks", "status": "running"}
data: {"step": 1, "tool": "web_search", "output": "...", "status": "done", "duration_ms": 1200}
data: {"step": 2, "tool": "summarize", "status": "running"}
data: {"type": "completed", "message": "All steps completed successfully"}
```

---

### DELETE /tasks/{task_id} — Cancel a running task

```bash
curl -X DELETE http://localhost:8000/tasks/your-task-id-here


### GET /tasks/{task_id}/dag — Task DAG 

```bash
curl http://localhost:8000/tasks/your-task-id/dag
```

Returns the planned step graph as JSON with nodes and edges.

---

### GET /health — Health check

```bash
curl http://localhost:8000/health
```

---

## Available Tools

| Tool | Input Format | Description |
|---|---|---|
| `web_search` | Short query string | Searches the web using DuckDuckGo  |
| `summarize` | Text or `output_of_step_N` | Summarizes long text using LLM sub-call |
| `write_file` | `"filename.md, content"` | Writes content to `artifacts/` sandbox directory |
| `read_file` | `filename.md` | Reads a file from `artifacts/` sandbox |
| `http_get` | Full `https://` URL | Fetches raw content of a URL (no JS rendering) |

---

## Demo Prompts

### Simple — 1-2 tools
```
Search for what is FastAPI
```
```
Search for Python list comprehension examples and save to python_tips.md
```

### Medium — 3 tools (search + summarize + save)
```
Find what is machine learning and write a beginner guide to ml_guide.md
```
```
Search for differences between SQL and NoSQL databases and write a comparison to databases.md
```
```
Find what is Docker and write a summary to docker_summary.md
```

### Uses http_get tool — fetch real URLs
```
Fetch content from https://httpbin.org/json and save the result to httpbin.md
```
```
Fetch content from https://api.github.com/repos/tiangolo/fastapi, summarize the repository details like stars and description, and save to fastapi_repo.md
```
```
Fetch content from https://jsonplaceholder.typicode.com/posts/1, summarize what the post is about, and save to post_summary.md
```

#

### Tests caching (run TWICE — second run is instant)
```
Search for what is REST API and save to rest_api.md
```


```

### Tests retry logic (will retry 3 times before failing gracefully)
```
Fetch content from https://thissitedoesnotexist12345.com and save results
```


---




## Database Schema

```sql
CREATE TABLE tasks (
    id           TEXT PRIMARY KEY,
    goal         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'queued',
    created_at   TEXT NOT NULL,
    completed_at TEXT,
    error        TEXT
);

CREATE TABLE task_steps (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      TEXT NOT NULL REFERENCES tasks(id),
    step_number  INTEGER NOT NULL,
    tool_name    TEXT NOT NULL,
    input        TEXT,
    output       TEXT,
    status       TEXT NOT NULL DEFAULT 'running',
    duration_ms  INTEGER,
    prompt_used  TEXT,
    attempt      INTEGER DEFAULT 1
);

CREATE TABLE task_artifacts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    TEXT NOT NULL REFERENCES tasks(id),
    filename   TEXT NOT NULL,
    file_path  TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Indexes for efficient filtering
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
CREATE INDEX idx_task_steps_task_id ON task_steps(task_id);
CREATE INDEX idx_task_artifacts_task_id ON task_artifacts(task_id);
```

Structured step data is stored in `task_steps` 

---

## Bonus Features

### Retry with exponential backoff
Failed tool calls are retried up to 3 times with delays of 1s → 2s → 4s. Implemented in `run_tool_with_retry()` in `agent/loop.py`.

### Tool result caching
Same tool + same input within a session returns cached output instantly. Cache key is `"tool_name:input"`. Cached results show ` cached` in the UI stream. Controlled by `CACHE_ENABLED` env variable.

### Prompt versioning
The exact LLM prompt used for planning is stored in the `prompt_used` column of every `task_steps` row — enabling full reproducibility and audit of what the agent was told to do.

### Task DAG endpoint
`GET /tasks/{id}/dag` returns the planned step graph as JSON with nodes and edges. Sequential edges connect every step; data dependency edges are added when a step references `output_of_step_N`.

---



## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| Language | Python 3.11+ |
| LLM | Groq API (llama-3.1-8b-instant) |
| LLM Client | openai SDK (Groq-compatible) |
| Database | SQLite via aiosqlite |
| Streaming | SSE via sse-starlette |
| Web Search | DuckDuckGo via ddgs |
| HTTP Client | httpx |
| Validation | Pydantic v2 |
| UI | Vanilla HTML/CSS/JS |

---

## Swagger Docs

FastAPI auto-generates interactive API docs:

```
http://localhost:8000/docs       ← Swagger UI
http://localhost:8000/redoc      ← ReDoc
```