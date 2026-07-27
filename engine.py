"""
Task Engine — builds dependency graph from JSON task definitions.
Loads, links, validates, sorts, and optionally executes tasks.
"""

import json
from collections import defaultdict


def load_tasks(path):
    """Load tasks from a JSON file."""
    with open(path) as f:
        data = json.load(f)
    return data.get("tasks", [])


# ─── Step 1: Index every output ─────────────────────────────────────────────

def build_output_index(tasks):
    """Map each artifact name to the task(s) that produce it."""
    index = {}
    for t in tasks:
        for out in t.get("output", []):
            index.setdefault(out, []).append(t["id"])
    return index


# ─── Step 2: Match outputs → inputs and build edge list ─────────────────────

def build_edges(tasks):
    """
    For each task, find which other tasks produce its inputs.
    Returns a list of {'from': producer, 'to': consumer} edges.
    """
    output_index = build_output_index(tasks)
    edges = []
    for t in tasks:
        for inp in t.get("input", []):
            producers = output_index.get(inp, [])
            for p in producers:
                edges.append({"from": p, "to": t["id"]})
    return edges


# ─── Step 3: Validate — no dangling inputs ──────────────────────────────────

def validate(tasks):
    """Check that every input has at least one producer. Return list of errors."""
    produced = {out for t in tasks for out in t.get("output", [])}
    errors = []
    for t in tasks:
        for inp in t.get("input", []):
            if inp not in produced:
                errors.append(f"'{t['id']}' needs '{inp}' — no task produces it")
    return errors


# ─── Step 4: Topological sort — find safe execution order ───────────────────

def topological_sort(tasks, edges):
    """Return tasks in an order where all dependencies come first (Kahn's algorithm)."""
    upstream = defaultdict(list)
    for e in edges:
        upstream[e["to"]].append(e["from"])

    ready = [t for t in tasks if not upstream[t["id"]]]
    order = []

    while ready:
        current = ready.pop(0)
        order.append(current)
        for id, deps in upstream.items():
            if current in deps:
                deps.remove(current)
                if not deps:
                    ready.append(id)

    return order


# ─── Step 5: Execute ────────────────────────────────────────────────────────

def get_task_dependencies(task, tasks):
    """
    For a given task, find which tasks produce its inputs.
    Returns list of upstream task IDs.
    """
    output_index = build_output_index(tasks)
    deps = []
    for inp in task.get("input", []):
        deps.extend(output_index.get(inp, []))
    return list(dict.fromkeys(deps))   # dedupe, preserve order


def execute_tasks(tasks, callback=None):
    """
    Run each task in topological order.
    callback(task) is called for every task that runs.
    """
    tasks_dict = {t["id"]: t for t in tasks}
    for t in tasks:
        if callback:
            callback(t)
        print(f"  ▶ {t['id']:20s}  inputs={t.get('input', [])}  output={t.get('output', [])}")


def run_workflow(tasks_path="workflow.json", dry_run=True):
    """Main entry point: load → link → validate → sort → execute."""
    tasks = load_tasks(tasks_path)
    print(f"[Engine] Loaded {len(tasks)} tasks")

    edges = build_edges(tasks)
    print(f"[Engine] Built {len(edges)} edges")

    errors = validate(tasks)
    if errors:
        for e in errors:
            print(f"[Engine] ⚠ {e}")
    else:
        print("[Engine] All inputs satisfied ✓")

    order = topological_sort(tasks, edges)
    print(f"[Engine] Execution order ({len(order)} tasks):")
    for t in order:
        print(f"  {t['id']}")

    if not dry_run:
        execute_tasks(order)


if __name__ == "__main__":
    run_workflow()