"""
Bootstrap — starts both servers and opens the dashboard in a browser.

Process model
-------------
Flask  (port 5000)  — main process, owns workflow.json, serves the web GUI.
MCP    (port 5001)  — subprocess, thin SSE proxy over the Flask API.

Both are shut down cleanly when this process exits (Ctrl-C or SIGTERM).
"""

import os
import sys
import signal
import subprocess
import threading
import time
import webbrowser
from app import app


MCP_PORT = int(os.environ.get("MCP_PORT", "5001"))


def start_mcp_server() -> subprocess.Popen:
    """Spawn MCP_port.py as an SSE subprocess."""
    env = os.environ.copy()
    env["MCP_TRANSPORT"] = "streamable-http"
    env["MCP_PORT"] = str(MCP_PORT)
    # Point MCP at Flask — both run on localhost in the same container.
    env.setdefault("WORKFLOW_API_URL", "http://localhost:5000/api")

    proc = subprocess.Popen(
        [sys.executable, os.path.join(os.path.dirname(__file__), "MCP_port.py")],
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    return proc


def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    mcp_proc = start_mcp_server()

    # Propagate SIGTERM to the MCP child before exiting.
    def _shutdown(sig, frame):
        mcp_proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)

    threading.Thread(target=open_browser, daemon=True).start()

    print(f"🚀 Flask dashboard  → http://localhost:5000")
    print(f"🔌 MCP streamable HTTP → http://localhost:{MCP_PORT}/mcp")

    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    finally:
        # Ctrl-C lands here — make sure MCP subprocess is always cleaned up.
        mcp_proc.terminate()
