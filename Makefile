.PHONY: up down logs build dev-backend dev-frontend install lint

install:
	pip install -r requirements.txt

dev-backend:
	uvicorn backend.main:app --reload --port 8000

dev-frontend:
	python frontend/app.py

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

lint:
	ruff check backend/ frontend/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	rm -rf models/saved/ensemble_detector.pkl models/alerts.db
