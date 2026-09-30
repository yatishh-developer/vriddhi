FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

# The entrypoint upgrades the configured DATABASE_URL before replacing itself
# with Uvicorn.  A migration failure exits the container non-zero.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
