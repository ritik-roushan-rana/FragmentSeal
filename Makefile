# Convenience wrappers around scripts/. Use either; they do the same thing.

.PHONY: help setup dev test backend frontend seed reset clean

help:
	@echo "make setup     install dependencies, create env files, seed demo data"
	@echo "make dev       run the API and web app together"
	@echo "make backend   run only the API      (http://127.0.0.1:8000)"
	@echo "make frontend  run only the web app  (http://localhost:3000)"
	@echo "make test      backend tests + frontend types, lint and build"
	@echo "make seed      re-seed demo accounts and sample documents"
	@echo "make reset     wipe the database and all stored files, then re-seed"
	@echo "make clean     remove build caches and virtual environments"

setup:
	./scripts/setup.sh

dev:
	./scripts/dev.sh

test:
	./scripts/test.sh

backend:
	cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

seed:
	cd backend && .venv/bin/python -m app.seed --documents

reset:
	rm -rf backend/storage
	cd backend && .venv/bin/python -m app.seed --documents

clean:
	rm -rf backend/.venv backend/.pytest_cache frontend/node_modules frontend/.next
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
