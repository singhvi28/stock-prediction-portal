# Use a slim Python base to minimize image size
FROM python:3.10-slim

# Prevent Python from writing .pyc files and ensure output is sent to logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Install system dependencies for psycopg2 and building packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend source code
COPY api/ /app/api/

# Default port for the FastAPI application
EXPOSE 8000

# Default command starts the API; can be overridden for the worker service
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
