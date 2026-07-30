FROM python:3.11-slim

WORKDIR /app

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy only requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application files
COPY engine.py .
COPY MCP_port.py .
COPY app.py .
COPY index.html .
COPY workflow.json .

# Ports
# 5000 — Flask web dashboard
# 8765 — MCP HTTP server
EXPOSE 5000 8765

# Default: run Flask dashboard. Run MCP_port separately or via command override.
CMD ["python", "app.py"]