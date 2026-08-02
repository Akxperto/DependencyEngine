"""
MCP server for the Dependency Engine — Odysseus edition.
mcp SDK v1.x (FastMCP).

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
Optional: streamable-http — set MCP_TRANSPORT=streamable-http

Registering in Odysseus
-----------------------
Option A — through the Odysseus UI:
  Settings → MCP Servers → Add Server
    Type:    stdio
    Command: python
    Args:    ["/absolute/path/to/mcp_port.py"]
    Env:     { "WORKFLOW_API_URL": "http://flesk:5000/api" }

Option B — SSE / streamable-http (persistent network service):
  Run:  MCP_TRANSPORT=streamable-http MCP_PORT=5001 python mcp_port.py
  Add:  type=streamable-http, url=http://flesk:5001/mcp

Environment variables
---------------------
WORKFLOW_API_URL  Flask base URL  (default: http://localhost:5000/api)
MCP_TRANSPORT     stdio | sse | streamable-http (default: stdio)
MCP_PORT          SSE / streamable-http port    (default: 5001)
MCP_HOST          Bind host for HTTP transports (default: 0.0.0.0)
"""

import json
import os
import urllib.request
import urllib.error
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# ── Config ────────────────────────────────────────────────────────────────────
FLASK_BASE = os.environ.get("WORKFLOW_API_URL", "http://localhost:5000/api").rstrip("/")
MCP_HOST   = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT   = int(os.environ.get("MCP_PORT", "5001"))

# Disable DNS rebinding protection — the server is behind Caddy which
# rewrites the Host header to the container's internal address. Without
# this, every request gets HTTP 421 Misdirected Request.
mcp = FastMCP(
    "dependency-engine",
    host=MCP_HOST,
    port=MCP_PORT,
    log_level="WARNING",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


# ── HTTP helpers ──────────────────────────────────────────────────────────────
def _get(path: str):
    """GET from Flask and return parsed JSON."""
    try:
        with urllib.request.urlopen(f"{FLASK_BASE}{path}", timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.URLError as e:
        return {"error": f"Cannot reach Flask API at {FLASK_BASE}. Is app.py running? ({e})"}


def _post(path: str, body=None):
    """POST to Flask, return (parsed JSON, http status)."""
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        f"{FLASK_BASE}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code
    except urllib.error.URLError as e:
        return {"error": f"Cannot reach Flask API at {FLASK_BASE}. Is app.py running? ({e})"}, 503


def _put(path: str, body: dict):
    """PUT to JSON, return (status, body)."""
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{FLASK_BASE}{path}",
        data=data,
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code
    except urllib.error.URLError as e:
        return {"error": f"Cannot reach Flask API at {FLASK_BASE}. Is app.py running? ({e})"}, 503


def _delete(path: str):
    """DELETE to JSON, return (status, body)."""
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
    mime_type="application/json",
)
def resource_summary() -> str:
    return json.dumps(_get("/summary"), indent=2)


@mcp.resource(
    "workflow://tasks",
    name="All Tasks",
    description="Full task list with computed dependency fields.",
    mime_type="application/json",
)
def resource_tasks() -> str:
    return json.dumps(_get("/tasks"), indent=2)


@mcp.resource(
    "workflow://tasks/{task_id}",
    name="Single Task",
    description="One task by ID, including producers, blocked_by, is_blocked.",
    mime_type="application/json",
)
def resource_task(task_id: str) -> str:
    return json.dumps(_get(f"/tasks/{task_id}"), indent=2)


@mcp.resource(
    "workflow://current",
    name="Current Task",
    description="The next task that is ready to execute.",
    mime_type="application/json",
)
def resource_current() -> str:
    return json.dumps(_get("/current"), indent=2)


@mcp.resource(
    "workflow://execution-order",
    name="Execution Order",
    description="Tasks in topological order.",
    mime_type="application/json",
)
def resource_execution_order() -> str:
    return json.dumps(_get("/toposort"), indent=2)


@mcp.resource(
    "workflow://validate",
    name="Validation Report",
    description="Check for dangling inputs.",
    mime_type="application/json",
)
def resource_validate() -> str:
    return json.dumps(_get("/validate"), indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# TOOLS — read + write actions
# ══════════════════════════════════════════════════════════════════════════════

# ── Read ──────────────────────────────────────────────────────────────────────

@mcp.tool(description="Return a count of total, complete, ready, and blocked tasks.")
def get_summary() -> dict:
    return _get("/summary")


@mcp.tool(description="Return all tasks with computed status fields.")
def list_tasks() -> dict:
    return _get("/tasks")


@mcp.tool(description="Return one task by ID including producers, blocked_by, is_blocked.")
def get_task(task_id: str) -> dict:
    return _get(f"/tasks/{task_id}")


@mcp.tool(description="Return the next task that is ready to execute.")
def get_current_task() -> dict:
    return _get("/current")


@mcp.tool(description="Get the dependencies (inputs from other tasks) that must complete before a task can start.")
def get_dependencies(task_id: str) -> dict:
    return _get(f"/tasks/{task_id}/dependencies")


@mcp.tool(description="Return tasks in topological order. A partial result means a cycle exists.")
def get_execution_order() -> dict:
    data = _get("/toposort")
    total = _get("/summary").get("total", "?")
    order = data.get("order", [])
    return {
        "order": order,
        "total_tasks": total,
        "cycle_detected": isinstance(total, int) and len(order) < total,
    }


@mcp.tool(description="Check the workflow for structural issues.")
def validate_workflow() -> dict:
    return _get("/validate")


# ── Write ─────────────────────────────────────────────────────────────────────

@mcp.tool(description="Mark a task as complete. Enforces dependency order.")
def complete_task(task_id: str) -> dict:
    result, _ = _post(f"/tasks/{task_id}/complete")
    if result.get("status") == "complete":
        current = _get("/current")
        summary = _get("/summary")
        result["next_task"] = current.get("task")
        result["summary"] = summary
    return result


@mcp.tool(description="Mark a task as not complete (undo a completion).")
def uncomplete_task(task_id: str) -> dict:
    result, _ = _post(f"/tasks/{task_id}/uncomplete")
    return result


@mcp.tool(description="Reset every task in the workflow to incomplete.")
def reset_workflow() -> dict:
    result, _ = _post("/reset")
    result["summary"] = _get("/summary")
    return result


@mcp.tool(description="Add a new task to the workflow.")
def add_task(
    task_id: str,
    name: str,
    description: str,
    inputs: list,
    outputs: list,
) -> dict:
    result, code = _post("/tasks", {
        "id": task_id,
        "name": name,
        "description": description,
        "input": inputs,
        "outputs": outputs,
    })
    return result


@mcp.tool(description="Update an existing task's name, description, inputs, or outputs.")
def update_task(
    task_id: str,
    name: str,
    description: str,
    inputs: list,
    outputs: list,
) -> dict:
    result, _ = _put(f"/tasks/{task_id}", {
        "name": name,
        "description": description,
        "input": inputs,
        "outputs": outputs,
    })
    return result


@mcp.tool(description="Remove a task from the workflow by ID.")
def remove_task(task_id: str) -> dict:
    result, _ = _delete(f"/tasks/{task_id}")
    return result


@mcp.tool(description="Return all tasks that are ready to work on (not blocked, not complete).")
def get_ready_tasks() -> dict:
    return _get("/tasks/ready")


@mcp.tool(description="Return all incomplete tasks that are blocked by unmet dependencies.")
def get_blocked_tasks() -> dict:
    return _get("/tasks/blocked")


@mcp.tool(description="Return the list of task IDs directly blocking a given task.")
def get_blockers(task_id: str) -> dict:
    return _get(f"/tasks/{task_id}/blockers")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "streamable-http").lower()

    if transport == "stdio":
        mcp.run()  # stdio
    elif transport == "sse":
        print(f"[dependency-engine MCP] SSE on {MCP_HOST}:{MCP_PORT}/sse", flush=True)
        mcp.run(transport="sse")
    else:  # streamable-http (default for Odysseus)
        print(f"[dependency-engine MCP] streamable-http on {MCP_HOST}:{MCP_PORT}/mcp", flush=True)
        mcp.run(transport="streamable-http")