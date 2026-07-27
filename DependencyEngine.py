"""
Dependency Engine — Flask Backend
Serves the workflow state machine API.
Run:  python app.py
"""

import json
import os
from pathlib import Path
from flask import Flask, jsonify, abort, request, send_from_directory

app = Flask(__name__, static_folder="ui", static_url_path="")

BASE_DIR   = Path(__file__).parent
WORKFLOW_FILE = BASE_DIR / "workflow.json"


def load_workflow():
    with open(WORKFLOW_FILE, "r") as f:
        wf = json.load(f)

    tasks = wf.get("tasks", {})

    # Normalize: support both {"tasks": {"id": {...}}} and
    # {"tasks": [{"id": "id", ...}, ...]} shapes.
    if isinstance(tasks, list):
        normalized = {}
        for t in tasks:
            tid = t.get("id")
            if tid is None:
                raise ValueError(
                    "workflow.json: each task in a list-style 'tasks' array "
                    "must have an 'id' field"
                )
            normalized[tid] = t
        wf["tasks"] = normalized

    return wf


def save_workflow(data):
    with open(WORKFLOW_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ─── Compute derived fields for every task ────────────────────────────────────

def _task_outputs(t: dict) -> list:
    return t.get("outputs", t.get("output", []))


def compute_task(task_id: str, tasks: dict) -> dict:
    """
    Returns a fresh dict for task_id with:
      isComplete   — bool (the task's own completion flag)
      is_blocked   — bool (true if any input artifact isn't produced yet)
      blocked_by   — list[str] (input artifact IDs not yet produced)
      producers    — list[str] (task IDs that produce any of this task's inputs)
      is_ready     — bool (not done, not blocked)
    """
    task = tasks[task_id]
    is_complete = task.get("isComplete", False)

    # Support both singular ("input"/"output") and plural
    # ("inputs"/"outputs") field names across different workflow.json shapes.
    task_inputs  = task.get("inputs",  task.get("input",  []))
    task_outputs = task.get("outputs", task.get("output", []))

    # An input artifact is "satisfied" once some task that produces it is
    # complete. blocked_by lists artifacts with no completed producer yet.
    blocked_by = [
        artifact for artifact in task_inputs
        if not any(
            artifact in _task_outputs(t) and t.get("isComplete", False)
            for t in tasks.values()
        )
    ]

    producers = [
        tid for tid, t in tasks.items()
        if any(out in task_inputs for out in _task_outputs(t))
    ]

    return {
        "id":         task_id,
        "name":       task.get("name", ""),
        "description": task.get("description", ""),
        "inputs":     task_inputs,
        "outputs":    task_outputs,
        "isComplete": is_complete,
        "is_blocked": bool(blocked_by) and not is_complete,
        "blocked_by": blocked_by,
        "producers":  producers,
        "is_ready":   (not blocked_by) and (not is_complete),
    }



# ─── Serve the frontend ────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ─── API Routes ───────────────────────────────────────────────────────────────

@app.route("/api/workflow")
def get_workflow():
    """Return computed task list."""
    wf = load_workflow()
    tasks = wf.get("tasks", {})
    return jsonify([compute_task(tid, tasks) for tid in wf.get("task_order", tasks.keys())])


@app.route("/api/workflow/summary")
def get_summary():
    """Return {total, complete, ready, blocked} counts."""
    wf = load_workflow()
    tasks = wf.get("tasks", {})

    total    = len(tasks)
    complete = 0
    ready    = 0
    blocked  = 0

    for tid in tasks:
        t = compute_task(tid, tasks)
        if t["isComplete"]:
            complete += 1
        elif t["is_blocked"]:
            blocked += 1
        elif t["is_ready"]:
            ready += 1

    return jsonify({"total": total, "complete": complete, "ready": ready, "blocked": blocked})


@app.route("/api/current")
def get_current():
    """Return the first ready (unblocked, incomplete) task."""
    wf = load_workflow()
    tasks = wf.get("tasks", {})

    for tid in wf.get("task_order", tasks.keys()):
        t = compute_task(tid, tasks)
        if t["is_ready"]:
            return jsonify(t)

    return jsonify({})   # no ready task found


@app.route("/api/complete/<task_id>", methods=["POST"])
def mark_complete(task_id: str):
    """Mark a task as complete if its inputs are all done."""
    wf = load_workflow()
    tasks = wf.get("tasks", {})

    if task_id not in tasks:
        abort(404, description=f"Task '{task_id}' not found")

    task = tasks[task_id]

    # Already done
    if task.get("isComplete", False):
        return jsonify({"status": "already_complete", "task": task_id})

    # Check blocking inputs — an input artifact is satisfied once some
    # task that produces it is complete (mirrors compute_task's logic).
    task_inputs = task.get("inputs", task.get("input", []))
    blocked_by = [
        artifact for artifact in task_inputs
        if not any(
            artifact in _task_outputs(t) and t.get("isComplete", False)
            for t in tasks.values()
        )
    ]

    if blocked_by:
        return jsonify({
            "status":     "blocked",
            "task":       task_id,
            "blocked_by": blocked_by,
        })

    # Mark complete
    tasks[task_id]["isComplete"] = True
    wf["tasks"] = tasks
    save_workflow(wf)

    return jsonify({"status": "complete", "task": task_id})


@app.route("/api/workflow/reset", methods=["POST"])
def reset_workflow():
    """Reset all tasks to isComplete = False."""
    wf = load_workflow()
    for task in wf.get("tasks", {}).values():
        task["isComplete"] = False
    save_workflow(wf)
    return jsonify({"status": "reset"})


if __name__ == "__main__":
    print("⚡ Dependency Engine running on http://localhost:5000")
    app.run(debug=True, port=5000)