FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install Python dependencies (production only)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Copy and set up entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Make the venv's binaries available (gunicorn, celery, etc.)
ENV PATH="/app/.venv/bin:$PATH"

# SERVICE_TYPE=worker runs celery, anything else runs gunicorn
CMD ["/entrypoint.sh"]
