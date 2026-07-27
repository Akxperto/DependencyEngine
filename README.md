# Dependency Engine v4

A dependency-driven task workflow engine exposed as both a **web dashboard** and an **MCP server**. Tasks define their own `input[]` and `output[]` arrays. The engine resolves dependencies by matching task `output` values to other tasks' `input` values.

---
## Directory Layout
```
DEv4/
├── workflow.json task data store (all tasks with input/output)
├── engine.py WorkflowStore class (core dependency graph logic)
├── app.py Flask REST API (HTTP endpoints + serves UI)
├── MCP_port.py FastMCP server (thin proxy to Flask API)
├── run.py entry point (starts Flask + MCP server)
├── index.html cytoscape.js graph dashboard
├── styles.css dashboard styling
├── Dockerfile container image definition
└── requirements.txt flask, flask-cors, mcp

```
---
## Quick Start

### Local development
```bash
cd DEv4
pip install -r requirements.txt
python run.py
```
Starts Flask on port 5000 (web dashboard) and the MCP server on port 5001 (for AI agents).

---
### Docker
```bash
docker build -t dependencyengine .
docker run -d --name dependencyengine \
-p 5000:5000 \
-p 5001:5001 \
-v /path/to/DEv4:/app \
-e MCP_TRANSPORT=streamable-http \
-e MCP_HOST=0.0.0.0 \
-e MCP_PORT=5001 \
--restart unless-stopped \
dependencyengine
```
---
## Architecture
```
Browser
└── https://dependencyengine.alishcoordinatedchaos.tech/
    └── Caddy (TLS termination + reverse proxy)
        ├── / → port 5000 → Flask (app.py) → engine.py → workflow.json
        └── /mcp/* → port 5001 → FastMCP (MCP_port.py)
                                    └── proxies HTTP calls to Flask API

AI Agent (MCP client)
└── connects to https://dependencyengine.alishcoordinatedchaos.tech/mcp/
    └── FastMCP server exposes tools
        └── tools call Flask API under the hood
            └── engine.py is the only writer of workflow.json
```
**Why a thin proxy?** The MCP server never writes to `workflow.json` directly. Flask is the single source of truth for state and validation. MCP is just a translation layer. This eliminates file race conditions when the AI agent and the dashboard are both active.

---
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
---

## Flask API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tasks` | List all tasks |
| GET | `/api/tasks/<id>` | Get one task |
| POST | `/api/tasks` | Add a task |
| PUT | `/api/tasks/<id>` | Update a task |
| DELETE | `/api/tasks/<id>` | Remove a task |
| POST | `/api/tasks/<id>/complete` | Mark complete (with blocker guard) |
| POST | `/api/tasks/<id>/uncomplete` | Mark incomplete |
| GET | `/api/tasks/<id>/dependencies` | List blocking tasks |
| POST | `/api/reset` | Reset all to incomplete |
| GET | `/api/validate` | Check for dangling inputs and duplicate IDs |
| GET | `/api/summary` | Count ready/blocked/complete |
| GET | `/api/toposort` | Topological execution order |
| GET | `/api/current` | First ready-to-execute task |

---

## MCP Tools

The MCP server exposes the same operations as MCP tools, optimized for AI agent workflows.

### Query tools

| Tool | Description |
|------|-------------|
| `get_summary` | Counts: total, complete, ready, blocked |
| `list_tasks` | All tasks with computed state |
| `get_task(task_id)` | One task with state |
| `get_current_task` | Next task to execute (returns enriched response with task and summary) |
| `get_dependencies(task_id)` | Upstream blockers |
| `get_execution_order` | Topological sort and cycle detection |
| `validate_workflow` | Graph validation report |

### Mutation tools

| Tool | Description |
|------|-------------|
| `complete_task(task_id)` | Mark complete. Returns status (complete / blocked / already_complete), next_task, and summary in one call |
| `uncomplete_task(task_id)` | Mark incomplete |
| `reset_workflow` | Reset all tasks. Returns summary |
| `add_task(...)` | Add task with id, name, description, inputs, outputs |
| `update_task(...)` | Update task fields |
| `remove_task(task_id)` | Remove task |

### MCP Resources (read-only snapshots)

| Resource URI | Description |
|--------------|-------------|
| `workflow://summary` | Live task counts |
| `workflow://tasks` | Full task list with state |
| `workflow://current` | Current ready task |
| `workflow://execution-order` | Topological order |
| `workflow://validate` | Validation report |

---

## MCP Endpoints

| Transport | URL |
|-----------|-----|
| streamable-http (default) | `http://localhost:5001/mcp` |
| stdio | spawn `MCP_port.py` as subprocess |

---

## Validation

`validate_workflow` catches:
- Inputs consumed but never produced by any task
- Duplicate task IDs

---

## Status Colors

- 🔵 **READY** all inputs satisfied, not yet complete
- 🔴 **BLOCKED** waiting on upstream tasks
- 🟢 **COMPLETE** marked done

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TRANSPORT` | `streamable-http` | `stdio` or `streamable-http` |
| `MCP_HOST` | `0.0.0.0` | MCP server bind host |
| `MCP_PORT` | `5001` | MCP server port |
| `WORKFLOW_API_URL` | `http://localhost:5000/api` | Flask base URL for MCP server to proxy to |
