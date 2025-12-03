# Minimal Makefile for local dev, unit tests & smoke testing
# Usage:
#   make venv         # create virtualenv
#   make install      # install deps (including dev extras) into venv
#   make run-api      # start FastAPI on :8888
#   make smoke        # run scripts/smoke.py against localhost:8888
#   make test         # run pytest unit tests
#   make test-all     # run pytest + smoke test
#   make dev          # install + run-api
#   make clean        # remove .venv

PYTHON ?= python3
VENV_DIR ?= .venv

# Bin paths inside venv (Unix/macOS/WSL)
PYTHON_VENV := $(VENV_DIR)/bin/python
PIP_VENV    := $(VENV_DIR)/bin/pip
UVICORN     := $(VENV_DIR)/bin/uvicorn

.PHONY: venv install dev run-api smoke test test-all clean

venv:
	@echo "📦 Creating virtualenv in $(VENV_DIR)…"
	$(PYTHON) -m venv $(VENV_DIR)

install: venv
	@echo "⬆️  Upgrading pip…"
	$(PIP_VENV) install --upgrade pip
	@echo "📥 Installing project dependencies (including dev extras if pyproject.toml is present)…"
	@if [ -f "pyproject.toml" ]; then \
		$(PIP_VENV) install -e ".[dev]"; \
	elif [ -f "requirements.txt" ]; then \
		$(PIP_VENV) install -r requirements.txt; \
	else \
		echo "❌ No pyproject.toml or requirements.txt found. Please add dependencies."; \
		exit 1; \
	fi

dev: install run-api

run-api:
	@echo "🚀 Starting API on http://localhost:8888 …"
	$(UVICORN) app.api.fastapi_app:app --reload --port 8888

smoke:
	@echo "🧪 Running smoke tests against http://localhost:8888 …"
	$(PYTHON_VENV) scripts/smoke.py

test:
	@echo "🧪 Running unit tests with pytest …"
	$(PYTHON_VENV) -m pytest

test-all: test smoke

clean:
	@echo "🧹 Removing virtualenv $(VENV_DIR)…"
	rm -rf $(VENV_DIR)
