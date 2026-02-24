.PHONY: install dev contracts test seed demo up down

install:
	pip install -e ".[dev]"
	cd frontend && npm install

dev:
	uvicorn backend.main:app --reload --port 8000

contracts-compile:
	cd contracts && npx hardhat compile

contracts-test:
	cd contracts && npx hardhat test

contracts-deploy:
	python scripts/deploy.py

test:
	pytest tests/ -v

seed:
	python scripts/seed.py

demo:
	python scripts/demo_run.py

frontend:
	cd frontend && npm run dev

up:
	docker compose up -d

down:
	docker compose down

db-migrate:
	alembic upgrade head
