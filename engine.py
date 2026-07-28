"""Workflow Engine — WorkflowStore class for dependency-driven task management."""

import json
import pathlib
import logging
from collections import defaultdict, deque

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class WorkflowStore:
    """Stores and manages tasks with input/output dependency resolution."""

    def __init__(self, path: str = "workflow.json"):
        self.path = pathlib.Path(path)
        self.tasks: dict[str, dict] = {}
        self._output_index: dict[str, list[str]] = defaultdict(list)  # output_name → [producer task_ids]
        self._input_index: dict[str, list[str]] = defaultdict(list)   # output_name → [consumer task_ids]
        self._load()
        self.build_edges()
        self.save()

    # ─── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Re-read JSON from disk."""
        if not self.path.exists():
            self.tasks = {}
            return
        with open(self.path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.tasks = {t['id']: t for t in data.get('tasks', [])}
        logger.info(f"Loaded {len(self.tasks)} tasks from {self.path}")

    def save(self) -> None:
        """Write JSON to disk."""
        data = {'tasks': list(self.tasks.values())}
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        logger.info("Saved workflow to disk")

    # ─── Task CRUD ─────────────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> dict | None:
        return self.tasks.get(task_id)

    def add_task(self, task_id: str, name: str, description: str, inputs: list, outputs: list) -> dict:
        task = {
            'id': task_id,
            'name': name,
            'description': description,
            'input': inputs,
            'output': outputs,
            'isComplete': False
        }
        self.tasks[task_id] = task
        self.build_edges()
        self.save()
        return task

    def update_task(self, task_id: str, name: str, description: str, inputs: list, outputs: list) -> dict | None:
        if task_id not in self.tasks:
            return None
        self.tasks[task_id].update({
            'name': name,
            'description': description,
            'input': inputs,
            'output': outputs
        })
        self.build_edges()
        self.save()
        return self.tasks[task_id]

    def remove_task(self, task_id: str) -> bool:
        if task_id not in self.tasks:
            return False
        del self.tasks[task_id]
        self.build_edges()
        self.save()
        return True

    def get_task_dependencies(self, task_id: str) -> list[str]:
        """Return list of task IDs that feed into this task (blockers)."""
        task = self.tasks.get(task_id)
        if not task:
            return []
        blockers = []
        for dep in task.get('input', []):
            for source_id in self._output_index.get(dep, []):
                if source_id not in blockers:
                    blockers.append(source_id)
        return blockers

    def annotate_task(self, task_id: str) -> dict | None:
        """Return a task enriched with computed dependency/status fields
        (producers, blocked_by, is_blocked) for consumption by the UI."""
        task = self.tasks.get(task_id)
        if not task:
            return None
        producers = self.get_task_dependencies(task_id)
        blocked_by = [p for p in producers if not self.tasks[p].get('isComplete', False)]
        is_blocked = bool(blocked_by) and not task.get('isComplete', False)
        return {
            **task,
            'producers': producers,
            'blocked_by': blocked_by,
            'is_blocked': is_blocked,
        }

    def can_complete(self, task_id: str) -> tuple[bool, list[str]]:
        """Whether a task's blockers are all satisfied. Returns (ok, unmet_blocker_ids)."""
        blockers = self.get_task_dependencies(task_id)
        unmet = [b for b in blockers if not self.tasks[b].get('isComplete', False)]
        return (len(unmet) == 0, unmet)

    # ─── Graph ─────────────────────────────────────────────────────────────────

    def build_edges(self) -> None:
        """Rebuild the output → task indices (producers and consumers)."""
        self._output_index.clear()
        self._input_index.clear()
        for task_id, task in self.tasks.items():
            for out in task.get('output', []):
                self._output_index[out].append(task_id)
            for inp in task.get('input', []):
                self._input_index[inp].append(task_id)

    # ─── Validation ────────────────────────────────────────────────────────────

    def validate(self) -> dict:
        """Check for dangling inputs (nothing produces them)."""
        errors = []
        produced = set()
        consumed = set()
        for task_id, task in self.tasks.items():
            for out in task.get('output', []):
                produced.add(out)
            for inp in task.get('input', []):
                consumed.add(inp)
        orphaned = consumed - produced
        if orphaned:
            for item in sorted(orphaned):
                errors.append(f"'{item}' is consumed but never produced — fix task input[]")
        # Check for duplicate task IDs
        ids = [t['id'] for t in self.tasks.values()]
        if len(ids) != len(set(ids)):
            seen = set()
            for tid in ids:
                if tid in seen:
                    errors.append(f"Duplicate task ID: '{tid}'")
                seen.add(tid)
        return {'valid': len(errors) == 0, 'errors': errors}

    # ─── Execution ─────────────────────────────────────────────────────────────

    def topological_sort(self) -> list[str]:
        """Kahn's algorithm — returns tasks in execution order."""
        in_degree = defaultdict(int)
        all_task_ids = set(self.tasks.keys())

        for task_id in all_task_ids:
            blockers = self.get_task_dependencies(task_id)
            in_degree[task_id] = len(blockers)

        queue = deque([tid for tid in all_task_ids if in_degree[tid] == 0])
        result = []

        while queue:
            task_id = queue.popleft()
            result.append(task_id)
            task = self.tasks[task_id]
            for out in task.get('output', []):
                for consumer_id in self._input_index.get(out, []):
                    if consumer_id != task_id:
                        in_degree[consumer_id] -= 1
                        if in_degree[consumer_id] == 0:
                            queue.append(consumer_id)

        if len(result) != len(all_task_ids):
            logger.warning("Cycle detected — topological sort is partial")
        return result

    def current_task(self) -> str | None:
        """ID of first task that is ready (not complete, not blocked)."""
        for task_id in self.topological_sort():
            task = self.tasks.get(task_id)
            if task and not task.get('isComplete', False):
                blockers = self.get_task_dependencies(task_id)
                ready = all(self.tasks[b].get('isComplete', False) for b in blockers)
                if ready:
                    return task_id
        return None

    def complete(self, task_id: str) -> None:
        """Mark task as complete (no guard)."""
        if task_id in self.tasks:
            self.tasks[task_id]['isComplete'] = True
            self.save()

    def uncomplete(self, task_id: str) -> None:
        """Mark task as not complete."""
        if task_id in self.tasks:
            self.tasks[task_id]['isComplete'] = False
            self.save()

    def reset(self) -> None:
        """Reset all tasks to incomplete."""
        for task in self.tasks.values():
            task['isComplete'] = False
        self.save()

    def summary(self) -> dict:
        """Count of total/ready/blocked/complete tasks."""
        total = len(self.tasks)
        ready = blocked = complete = 0
        for task_id in self.topological_sort():
            task = self.tasks.get(task_id, {})
            if task.get('isComplete', False):
                complete += 1
            else:
                blockers = self.get_task_dependencies(task_id)
                if not blockers:
                    ready += 1
                else:
                    all_done = all(self.tasks[b].get('isComplete', False) for b in blockers)
                    if all_done:
                        ready += 1
                    else:
                        blocked += 1
        return {'total': total, 'ready': ready, 'blocked': blocked, 'complete': complete}