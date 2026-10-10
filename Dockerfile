FROM python:3.11-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS backend
COPY backend/ ./backend/
COPY data/ ./data/
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS frontend
COPY frontend/ ./frontend/
CMD ["python", "frontend/app.py"]
