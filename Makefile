.PHONY: setup dev dev-backend dev-frontend build run stop clean reset

# === Development ===

setup:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

dev:
	@echo "Run in separate terminals:"
	@echo "  make dev-backend"
	@echo "  make dev-frontend"

# === Docker ===

build:
	docker compose build

run:
	docker compose up -d
	@echo ""
	@echo "AVIP PoC is running:"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8000"
	@echo "  API docs: http://localhost:8000/docs"
	@echo ""

stop:
	docker compose down

clean:
	docker compose down -v
	rm -rf backend/data

reset:
	@echo "Resetting demo data..."
	curl -s -X POST http://localhost:8000/api/v1/demo/reset | python -m json.tool

# === Testing ===

test:
	cd backend && python -m pytest tests/ -v

lint:
	cd backend && ruff check app/
	cd frontend && npm run lint
