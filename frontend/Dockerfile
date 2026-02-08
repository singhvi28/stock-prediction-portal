FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies required for the dashboard and visualizations
COPY frontend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the frontend source code
COPY frontend/ /app/frontend/

# Streamlit default port
EXPOSE 8501

WORKDIR /app/frontend
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
