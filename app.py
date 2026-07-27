"""Flask REST API — exposes WorkflowStore via HTTP endpoints."""

import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from engine import WorkflowStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.')
CORS(app)
store = WorkflowStore('workflow.json')

# ─── API Routes ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    tasks = [store.annotate_task(tid) for tid in store.tasks]
    return jsonify({'tasks': tasks})

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    task = store.annotate_task(task_id)
    if not task:
        return jsonify({'error': f'Task {task_id} not found'}), 404
    return jsonify(task)

@app.route('/api/tasks', methods=['POST'])
def add_task():
    body = request.json
    required = ['id', 'name', 'description', 'input', 'output']
    if not all(k in body for k in required):
        return jsonify({'error': f'Missing fields. Required: {required}'}), 400
    if store.get_task(body['id']):
        return jsonify({'error': f'Task {body["id"]} already exists'}), 409
    task = store.add_task(
        body['id'], body['name'], body['description'],
        body['input'], body['output']
    )
    return jsonify(task), 201

@app.route('/api/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    body = request.json
    task = store.update_task(
        task_id, body.get('name', ''), body.get('description', ''),
        body.get('input', []), body.get('output', [])
    )
    if not task:
        return jsonify({'error': f'Task {task_id} not found'}), 404
    return jsonify(task)

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    ok = store.remove_task(task_id)
    if not ok:
        return jsonify({'error': f'Task {task_id} not found'}), 404
    return jsonify({'deleted': task_id})

@app.route('/api/tasks/<task_id>/complete', methods=['POST'])
def mark_complete(task_id):
    task = store.get_task(task_id)
    if not task:
        return jsonify({'error': f'Task {task_id} not found'}), 404
    if task.get('isComplete'):
        return jsonify({'status': 'already_complete', 'completed': task_id})
    ok, unmet = store.can_complete(task_id)
    if not ok:
        return jsonify({'status': 'blocked', 'blocked_by': unmet}), 409
    store.complete(task_id)
    return jsonify({'status': 'complete', 'completed': task_id})

@app.route('/api/tasks/<task_id>/uncomplete', methods=['POST'])
def mark_uncomplete(task_id):
    task = store.get_task(task_id)
    if not task:
        return jsonify({'error': f'Task {task_id} not found'}), 404
    store.uncomplete(task_id)
    return jsonify({'uncompleted': task_id})

@app.route('/api/tasks/<task_id>/dependencies', methods=['GET'])
def get_dependencies(task_id):
    task = store.get_task(task_id)
    if not task:
        return jsonify({'error': f'Task {task_id} not found'}), 404
    return jsonify({'dependencies': store.get_task_dependencies(task_id)})

@app.route('/api/reset', methods=['POST'])
def reset_all():
    store.reset()
    return jsonify({'reset': True})

@app.route('/api/validate', methods=['GET'])
def validate():
    result = store.validate()
    status = 200
    return jsonify(result), status

@app.route('/api/summary', methods=['GET'])
def summary():
    return jsonify(store.summary())

@app.route('/api/toposort', methods=['GET'])
def toposort():
    order = store.topological_sort()
    return jsonify({'order': order})

@app.route('/api/current', methods=['GET'])
def current():
    cid = store.current_task()
    task = store.annotate_task(cid) if cid else None
    return jsonify({'current': cid, 'task': task})

if __name__ == '__main__':
    logger.info("Starting Workflow Engine API on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)