# ⚡ Dependency Engine

A lightweight workflow state machine built with Flask + vanilla HTML/CSS/JS.

## Quick Start

```bash
pip install flask
python app.py
```

Then open **http://localhost:5000** in your browser.

## Project Files

| File | Purpose |
|------|---------|
| `index.html` | Frontend UI — loads from Flask API |
| `styles.css` | Dark-theme styles |
| `app.py` | Flask backend — serves API endpoints |
| `workflow.json` | Task definitions with inputs, outputs & `isComplete` |

## How It Works

**Each task has:**
- `inputs` — artifacts it needs from other tasks
- `outputs` — artifacts it produces (used as inputs by downstream tasks)
- `isComplete` — boolean flag set to `true` when the task is done

**State logic:**
- **Blocked** — one or more inputs not yet complete
- **Ready** — all inputs complete, not yet done
- **Done** — `isComplete === true`

The engine walks the task graph and surfaces the first **Ready** task as "Current Task." Marking it complete unlocks the next ones downstream.

## API Endpoints

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/workflow` | Full task list with computed state |
| GET | `/api/workflow/summary` | `{total, complete, ready, blocked}` |
| GET | `/api/current` | First ready task |
| POST | `/api/complete/<id>` | Mark task done (checks blocking) |
| POST | `/api/workflow/reset` | Reset all `isComplete` to `false` |

## Screenshots

- **Summary bar** — live counts at a glance
- **Current Task** — highlighted ready task with inputs/outputs
- **All Tasks** — cards showing Done / Ready / Blocked status per task
- **Auto-refresh** — UI reloads every 5 seconds