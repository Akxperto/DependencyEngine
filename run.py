"""Bootstrap — starts Flask and opens the dashboard in a browser."""

import webbrowser
import threading
import time
from app import app

def open_browser():
    time.sleep(1.0)
    webbrowser.open('http://localhost:5000')

if __name__ == '__main__':
    threading.Thread(target=open_browser, daemon=True).start()
    print("🚀 Starting Workflow Engine — open http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)