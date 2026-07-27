# Workflow Engine — POC v1.0.0

A dependency-driven task workflow engine built as a **proof of concept**. Tasks define their own `input[]` and `output[]` arrays — the engine resolves dependencies by matching task `output` values to other tasks' `input` values.

## Directory Layout

```
workflow-engine/
└── v1.0.0/
    ├── workflow.json   ← task data store (all tasks with input/output)
    ├── engine.py        ← WorkflowStore class (core dependency graph logic)
    ├── app.py           ← Flask REST API (all HTTP endpoints)
    ├── index.html       ← browser dashboard (task list, status, add/remove)
    └── run.py           ← bootstrap (starts server + opens browser)
```

**Note:** All files live in `workflow-engine/v1.0.0/`. Do NOT move files out of this subdirectory — `app.py` serves `index.html` from the same directory, and `engine.py` reads `workflow.json` from the same directory.

## Quick Start

```bash
cd workflow-engine/v1.0.0
pip install flask flask-cors
python run.py
```

Opens Flask on port 5000 and launches the dashboard at `http://localhost:5000`.

## Task Object

```json
{
  "id": "make_coffee",
  "name": "Make Coffee",
  "description": "Brew a fresh pot",
  "input": ["water", "coffee_beans"],
  "output": ["hot_coffee"],
  "isComplete": false
}
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tasks` | List all tasks |
| GET | `/api/tasks/<id>` | Get one task |
| POST | `/api/tasks` | Add a task |
| PUT | `/api/tasks/<id>` | Update a task |
| DELETE | `/api/tasks/<id>` | Remove a task |
| POST | `/api/tasks/<id>/complete` | Mark complete |
| POST | `/api/tasks/<id>/uncomplete` | Mark incomplete |
| GET | `/api/tasks/<id>/dependencies` | List blocking tasks |
| POST | `/api/reset` | Reset all to incomplete |
| GET | `/api/validate` | Check for dangling inputs |
| GET | `/api/summary` | Count ready/blocked/complete |
| GET | `/api/toposort` | Kahn's algorithm execution order |
| GET | `/api/current` | First ready-to-execute task |

## Intentional Bug (preserved)

`crepe_make` has `input: ["crepe_batter"]` — **nothing produces `crepe_batter`**. The `validate()` endpoint catches this and shows it as a warning in the UI. Does NOT block any other functionality.

## Status Colors

- 🟢 **READY** — all inputs satisfied, not yet complete
- 🔴 **BLOCKED** — waiting on upstream tasks
- ⚫ **COMPLETE** — marked done

## Future Improvements

- Guard check on `complete()` — reject blocked tasks
- `completed[]` top-level list in JSON
- Atomic file writes / DB persistence
- Rich UI styling / GUI editor for task editing
- Separate data file from code (currently both in same dir)