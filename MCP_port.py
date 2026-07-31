"""
MCP server for the Dependency Engine — Odysseus edition.

Architecture
------------
Flask  (app.py, port 5000)  owns workflow.json and serves the web GUI.
This server is a thin MCP proxy that calls the Flask API over HTTP.
Both processes can run simultaneously with no file contention.

Transport
---------
Default: stdio  — Odysseus spawns this process as a subprocess.
Optional: SSE   — set MCP_TRANSPORT=sse (and optionally MCP_PORT=5001)
                  then point Odysseus at http://localhost:5001/sse

Registering in Odysseus
-----------------------
Option A — through the Odysseus UI:
  Settings → MCP Servers → Add Server
    Type:    stdio
    Command: python
    Args:    ["/absolute/path/to/mcp_port.py"]
    Env:     { "WORKFLOW_API_URL": "http://localhost:5000/api" }   # optional

Option B — ask the Odysseus agent:
  "Add an MCP server called dependency-engine, stdio transport,
   command: python /absolute/path/to/mcp_port.py"

Option C — SSE (if you prefer a persistent network service):
  Run:  MCP_TRANSPORT=sse MCP_PORT=5001 python mcp_port.py
  Add in Odysseus: type=sse, url=http://localhost:5001/sse

Environment variables
---------------------
WORKFLOW_API_URL  Flask base URL  (default: http://localhost:5000/api)
MCP_TRANSPORT     stdio | sse     (default: stdio)
MCP_PORT          SSE port        (default: 5001)

Requirements
------------
    pip install "mcp[cli]"
    # Flask (app.py) must be running before any tool is called
"""

import json
import os
import urllib.request
import urllib.error
from mcp.server.fastmcp import FastMCP

# ── Config ────────────────────────────────────────────────────────────────────
FLASK_BASE = os.environ.get("WORKFLOW_API_URL", "http://localhost:5000/api").rstrip("/")

mcp = FastMCP(
    "dependency-engine",
    log_level="WARNING",
    host=os.environ.get("MCP_HOST", "0.0.0.0"),   # must be 0.0.0.0 in Docker; default was 127.0.0.1
    port=int(os.environ.get("MCP_PORT", "5001")),
)


# ── HTTP helpers ──────────────────────────────────────────────────────────────
def _get(path: str) -> dict | list:
    """GET from Flask and return parsed JSON."""
    try:
        with urllib.request.urlopen(f"{FLASK_BASE}{path}", timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.URLError as e:
        return {"error": f"Cannot reach Flask API at {FLASK_BASE}. Is app.py running? ({e})"}


def _post(path: str, body: dict | None = None) -> tuple[dict, int]:
    """POST to Flask, return (parsed JSON, http status)."""
    data = json.dumps(body or {}).encode()
    req  = urllib.request.Request(
        f"{FLASK_BASE}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code
    except urllib.error.URLError as e:
        return {"error": f"Cannot reach Flask API at {FLASK_BASE}. Is app.py running? ({e})"}, 503


def _put(path: str, body: dict) -> tuple[dict, int]:
    """PUT to Flask, return (parsed JSON, http status)."""
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"{FLASK_BASE}{path}",
        data=data,
        method="PUT",
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code
    except urllib.error.URLError as e:
        return {"error": f"Cannot reach Flask API at {FLASK_BASE}. Is app.py running? ({e})"}, 503


def _delete(path: str) -> tuple[dict, int]:
    """DELETE to Flask, return (parsed JSON, http status)."""
    req = urllib.request.Request(f"{FLASK_BASE}{path}", method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code
    except urllib.error.URLError as e:
        return {"error": f"Cannot reach Flask API at {FLASK_BASE}. Is app.py running? ({e})"}, 503


# ══════════════════════════════════════════════════════════════════════════════
# RESOURCES  — read-only snapshots
# ══════════════════════════════════════════════════════════════════════════════

@mcp.resource(
    "workflow://summary",
    name="Workflow Summary",
    description="Live count of total / complete / ready / blocked tasks.",
    mime_type="application/json"
)
def resource_summary() -> str:
    return json.dumps(_get("/summary"), indent=2)


@mcp.resource(
    "workflow://tasks",
    name="All Tasks",
    description=(
        "Full task list with computed dependency fields: "
        "producers, blocked_by, is_blocked."
    ),
    mime_type="application/json"
)
def resource_tasks() -> str:
    return json.dumps(_get("/tasks"), indent=2)


@mcp.resource(
    "workflow://tasks/{task_id}",
    name="Single Task",
    description="One task by ID, including producers, blocked_by, is_blocked.",
    mime_type="application/json"
)
def resource_task(task_id: str) -> str:
    return json.dumps(_get(f"/tasks/{task_id}"), indent=2)


@mcp.resource(
    "workflow://current",
    name="Current Task",
    description="The next task that is ready to execute (not blocked, not complete).",
    mime_type="application/json"
)
def resource_current() -> str:
    return json.dumps(_get("/current"), indent=2)


@mcp.resource(
    "workflow://execution-order",
    name="Execution Order",
    description="Tasks in topological (dependency-respecting) order.",
    mime_type="application/json"
)
def resource_execution_order() -> str:
    return json.dumps(_get("/toposort"), indent=2)


@mcp.resource(
    "workflow://validate",
    name="Validation Report",
    description="Check for dangling inputs (consumed but never produced).",
    mime_type="application/json"
)
def resource_validate() -> str:
    return json.dumps(_get("/validate"), indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# TOOLS  — read + write actions
# ══════════════════════════════════════════════════════════════════════════════

# ── Read ──────────────────────────────────────────────────────────────────────

@mcp.tool(description=(
    "Return a count of total, complete, ready, and blocked tasks. "
    "Good first call to orient yourself before taking action."
))
def get_summary() -> dict:
    return _get("/summary")


@mcp.tool(description=(
    "Return all tasks with computed status fields "
    "(producers, blocked_by, is_blocked, isComplete). "
    "Use this to understand the full workflow state."
))
def list_tasks() -> dict:
    return _get("/tasks")


@mcp.tool(description=(
    "Return one task by ID, including producers, blocked_by, is_blocked. "
    "Returns an error dict if the task does not exist."
))
def get_task(task_id: str) -> dict:
    return _get(f"/tasks/{task_id}")


@mcp.tool(description=(
    "Return the next task that is ready to execute: "
    "not complete, not blocked, earliest in topological order. "
    "Returns null task if all tasks are done or everything is blocked."
))
def get_current_task() -> dict:
    return _get("/current")


@mcp.tool(description=(
    "Return the list of task IDs that must complete before a given task can start, "
    "and whether all of them are currently satisfied."
))
def get_dependencies(task_id: str) -> dict:
    return _get(f"/tasks/{task_id}/dependencies")


@mcp.tool(description=(
    "Return tasks in topological order (dependency-respecting execution sequence). "
    "A partial result means the workflow contains a cycle."
))
def get_execution_order() -> dict:
    data  = _get("/toposort")
    total = _get("/summary").get("total", "?")
    order = data.get("order", [])
    return {
        "order":          order,
        "total_tasks":    total,
        "cycle_detected": isinstance(total, int) and len(order) < total
    }


@mcp.tool(description=(
    "Check the workflow for structural issues: "
    "inputs that are consumed but never produced by any task."
))
def validate_workflow() -> dict:
    return _get("/validate")


# ── Write ─────────────────────────────────────────────────────────────────────

@mcp.tool(description=(
    "Mark a task as complete. "
    "Enforces dependency order — returns status='blocked' (with blocked_by list) "
    "if any predecessor is still incomplete. "
    "Returns status='already_complete' if already done. "
    "Returns status='complete' on success, plus the next ready task and updated summary."
))
def complete_task(task_id: str) -> dict:
    result, _ = _post(f"/tasks/{task_id}/complete")
    if result.get("status") == "complete":
        # Fetch next task and summary so the agent doesn't need an extra round-trip
        current = _get("/current")
        summary = _get("/summary")
        result["next_task"] = current.get("task")
        result["summary"]   = summary
    return result


@mcp.tool(description=(
    "Mark a task as not complete (undo a completion). "
    "Does not cascade — downstream tasks are not automatically reset."
))
def uncomplete_task(task_id: str) -> dict:
    result, _ = _post(f"/tasks/{task_id}/uncomplete")
    return result


@mcp.tool(description=(
    "Reset every task in the workflow to incomplete. "
    "Equivalent to starting the workflow from scratch. "
    "Returns the updated summary."
))
def reset_workflow() -> dict:
    result, _ = _post("/reset")
    result["summary"] = _get("/summary")
    return result


@mcp.tool(description=(
    "Add a new task to the workflow. "
    "inputs and outputs are lists of artifact name strings — "
    "the engine resolves dependencies by matching output names to input names. "
    "Returns the created task, or an error if the ID already exists."
))
def add_task(
    task_id:     str,
    name:        str,
    description: str,
    inputs:      list,
    outputs:     list
) -> dict:
    result, code = _post("/tasks", {
        "id":          task_id,
        "name":        name,
        "description": description,
        "input":       inputs,
        "output":      outputs
    })
    return result


@mcp.tool(description=(
    "Update an existing task's name, description, inputs, or outputs. "
    "Dependency edges are recomputed automatically. "
    "isComplete state is preserved."
))
def update_task(
    task_id:     str,
    name:        str,
    description: str,
    inputs:      list,
    outputs:     list
) -> dict:
    result, _ = _put(f"/tasks/{task_id}", {
        "name":        name,
        "description": description,
        "input":       inputs,
        "output":      outputs
    })
    return result


@mcp.tool(description=(
    "Remove a task from the workflow by ID. "
    "Dependency edges involving this task are cleaned up automatically."
))
def remove_task(task_id: str) -> dict:
    result, _ = _delete(f"/tasks/{task_id}")
    return result


@mcp.tool(description=(
    "Return all tasks that are ready to work on: not yet complete and "
    "every upstream dependency is already satisfied. "
    "Use this to find parallelisable work at the current frontier."
))
def get_ready_tasks() -> dict:
    return _get("/tasks/ready")


@mcp.tool(description=(
    "Return all incomplete tasks that are currently blocked: "
    "at least one upstream dependency has not been completed yet. "
    "Useful for understanding what is holding up the workflow."
))
def get_blocked_tasks() -> dict:
    return _get("/tasks/blocked")


@mcp.tool(description=(
    "Return the list of task IDs that are directly blocking a given task "
    "(i.e. incomplete upstream dependencies). "
    "Returns an empty list if the task is ready or does not exist."
))
def get_blockers(task_id: str) -> dict:
    return _get(f"/tasks/{task_id}/blockers")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport == "streamable-http":
        port = int(os.environ.get("MCP_PORT", "5001"))
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        print(f"[dependency-engine MCP] Streamable HTTP on http://{host}:{port}/mcp", flush=True)
        mcp.run(transport="streamable-http", mount_path="/mcp")
    elif transport == "sse":
        port = int(os.environ.get("MCP_PORT", "5001"))
        print(f"[dependency-engine MCP] SSE transport on port {port}", flush=True)
        mcp.run(transport="sse", host="0.0.0.0", port=5001)
    else:
        mcp.run() 
