FROM python:3.11-slim

WORKDIR /app

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy only requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN uv pip install --upgrade --system --no-cache -r requirements.txt

# Copy application files
COPY engine.py .
COPY app.py .
COPY MCP_port.py .
COPY run.py .
COPY index.html .
COPY styles.css .
COPY workflow.json .

# Ports
# 5000 — Flask API + web dashboard
# 5001 — MCP SSE server (proxy over Flask API)
EXPOSE 5000 5001

# run.py starts Flask (5000) and the MCP SSE subprocess (5001).
CMD ["python", "run.py"]
