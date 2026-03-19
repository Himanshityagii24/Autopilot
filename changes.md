TaskAutopilot — Follow-Up Improvements
Fix 1: Planning Shouldn’t Block Other API Requests

In services/task_runner.py, the plan_task(goal) function was being called directly inside an async flow. The problem is that the Groq LLM call inside plan_task() is synchronous, so it ended up blocking the entire event loop for 2–3 seconds.

That meant while planning was happening, nothing else could run — no API requests, no SSE updates, no status checks. Everything just paused.

The fix was simple: wrap plan_task() with run_in_executor. This pushes the blocking LLM call to a background thread, letting the event loop stay responsive and handle other requests at the same time.

This is also already how tools are handled in agent/loop.py, so it keeps things consistent across the codebase. We intentionally didn’t switch to AsyncOpenAI since mixing async patterns at this stage would add unnecessary complexity.


Validation
# Terminal 1 — submit a task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"goal": "find top python frameworks and write a report"}'

# Terminal 2 — hit this immediately during planning
curl http://localhost:8000/tasks

# Before fix → Terminal 2 hangs for 2–3 seconds
# After fix  → responds instantly 


Fix 2: Task Status Should Reflect What Actually Happened

Previously, tasks were always marked as "completed" once the loop finished — even if some steps failed along the way. That made the final status misleading.

Now, a failed_steps counter is initialized before the loop in agent/loop.py and incremented whenever something goes wrong:

Unknown tool

Invalid input (ValueError)

Tool execution error

After the loop:

If failed_steps == 0 → status = "completed"

Otherwise → status = "failed" with a message showing how many steps failed

This makes the final task state accurate and trustworthy.


Validation
# Submit a task that will fail
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"goal": "search the web for python and then use http_get on the search results to fetch each page"}'

# Check status
curl http://localhost:8000/tasks/{task_id}

# Before fix → always "completed" 
# After fix  → "failed" with correct step count 
Fix 3: Cancellation Should Be Final

There was a subtle issue with cancellation.

The system only checked for cancellation at the start of each step. So if a user cancelled while the last step was still running, that step would finish, the loop would end, and the system would overwrite "cancelled" with "completed".

So the task looked successful — even though the user cancelled it.

The fix introduces a was_cancelled flag:

Starts as False

Set to True when cancellation is detected

Final status update only runs if was_cancelled == False

This guarantees that once a task is cancelled, that state is permanent and cannot be overwritten.



Validation
# Submit a long-running task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"goal": "search top 10 python frameworks summarize and write detailed report"}'

# Cancel immediately
curl -X DELETE http://localhost:8000/tasks/{task_id}

# Check status
curl http://localhost:8000/tasks/{task_id}

# Before fix → sometimes shows "completed" 
# After fix  → always "cancelled" 
Fix 4: Streaming Now Works Properly Across Reconnects

The original streaming setup used a single queue per task. That caused two big issues:

If a client disconnected, the queue was deleted → reconnecting gave a 404

Multiple clients ended up splitting events randomly between them

The new approach uses a fan-out model:

Each client gets its own queue via subscribe()

All past events are stored in a history list

On reconnect, history is replayed instantly so the client catches up

New events are broadcast to all active clients at the same time

unsubscribe() only removes that specific client’s queue

Cleanup happens only after the task fully completes

This makes streaming reliable, consistent, and multi-client friendly.



Validation
# Terminal 1 — submit task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"goal": "search for top 5 machine learning libraries and write a report"}'

# Terminal 2 — connect to stream
curl -N http://localhost:8000/tasks/{task_id}/stream

# Disconnect after first step (Ctrl+C)

# Terminal 3 — reconnect
curl -N http://localhost:8000/tasks/{task_id}/stream

# Before fix → 404 on reconnect 
# After fix  → instantly replays and continues 

# Multiple clients test
# Before fix → events split 
# After fix  → all clients receive identical streams 