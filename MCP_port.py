#!/usr/bin/env python3
"""
MCP_port.py — MCP server for the Workflow Engine.
Exposes WorkflowStore methods as MCP tools over streamable-http.

Run standalone:  python MCP_port.py
Default port: 8765 (set via MCP_PORT env var).
"""

import sys
import os

# Resolve engine relative to this file
_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ENGINE_DIR)

from fastmcp import FastMCP
from engine import WorkflowStore

mcp = FastMCP("Workflow Engine")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_FILE = os.path.join(BASE_DIR, "workflow.json")
store = WorkflowStore(WORKFLOW_FILE)


# ─── Query tools ───────────────────────────────────────────────────────────────

@mcp.tool()
def get_tasks() -> dict:
    """List all tasks in the workflow with their current status."""
    tasks = store.get_all_tasks()
    return {"tasks": tasks, "count": len(tasks)}


@mcp.tool()
def get_task(task_id: str) -> dict:
    """Get a single task by ID, including its current status and dependencies."""
    task = store.get_task(task_id)
    if not task:
        return {"error": f"Task '{task_id}' not found"}
    deps = store.get_task_dependencies(task_id)
    status = store.task_status(task_id)
    return {"task": task, "dependencies": deps, "status": status}


@mcp.tool()
def get_workflow_summary() -> dict:
    """Get workflow summary: total, ready, blocked, complete counts."""
    return store.summary()


@mcp.tool()
def get_workflow_validation() -> dict:
    """Validate the workflow graph for errors like orphaned inputs or duplicate IDs."""
    return store.validate()


@mcp.tool()
def get_current_task() -> dict:
    """Get the next ready task (first unblocked, incomplete task)."""
    current_id = store.current_task()
    if not current_id:
        return {"current": None, "message": "No ready tasks. All done or workflow empty."}
    task = store.get_task(current_id)
    return {"current": current_id, "task": task}


@mcp.tool()
def get_ready_tasks() -> dict:
    """Get all ready tasks (unblocked, incomplete)."""
    ready_ids = store.get_ready_tasks()
    ready_tasks = [store.get_task(tid) for tid in ready_ids]
    return {"ready_tasks": ready_tasks, "count": len(ready_tasks)}


@mcp.tool()
def get_task_dependencies(task_id: str) -> dict:
    """Get tasks that block a given task (upstream producers and their artifacts)."""
    task = store.get_task(task_id)
    if not task:
        return {"error": f"Task '{task_id}' not found"}
    return store.get_task_dependencies(task_id)


# ─── Mutation tools ───────────────────────────────────────────────────────────

@mcp.tool()
def add_task(
    task_id: str,
    name: str,
    description: str,
    inputs: list[str],
    outputs: list[str],
) -> dict:
    """Add a new task to the workflow."""
    existing = store.get_task(task_id)
    if existing:
        return {"error": f"Task '{task_id}' already exists"}
    if not task_id or not name:
        return {"error": "task_id and name are required"}
    new_id = store.add_task(task_id, name, description, inputs, outputs)
    return {"added": store.get_task(new_id)}


@mcp.tool()
def complete_task(task_id: str) -> dict:
    """Mark a task as complete."""
    task = store.get_task(task_id)
    if not task:
        return {"error": f"Task '{task_id}' not found"}
    was_complete = task.get("isComplete", False)
    result = store.complete(task_id)
    return {"task_id": task_id, "completed": True, "was_already_complete": was_complete, "task": result}


@mcp.tool()
def reset_workflow() -> dict:
    """Reset all tasks to incomplete (clear completion state)."""
    store.reset()
    return {"reset": True}


# ─── Start the server ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("MCP_PORT", 8765))
    print(f"Starting Workflow Engine MCP server on port {port}", flush=True)
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)