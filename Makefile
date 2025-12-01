# Minimal Makefile for local dev & smoke testing
# Usage:
#   make venv         # create virtualenv
#   make install      # install deps into venv
#   make run-api      # start FastAPI on :8888
#   make smoke        # run scripts/smoke_test.py against localhost:8888
#   make dev          # install + run-api
#   make clean        # remove .venv

PYTHON ?= python3
VENV_DIR ?= .venv

# Bin paths inside venv (Unix/macOS)
PYTHON_VENV := $(VENV_DIR)/bin/python
PIP_VENV    := $(VENV_DIR)/bin/pip
UVICORN     := $(VENV_DIR)/bin/uvicorn

.PHONY: venv install dev run-api smoke clean

venv:
	@echo "📦 Creating virtualenv in $(VENV_DIR)…"
	$(PYTHON) -m venv $(VENV_DIR)

install: venv
	@echo "⬆️  Upgrading pip…"
	$(PIP_VENV) install --upgrade pip
	@echo "📥 Installing project dependencies…"
	@if [ -f "requirements.txt" ]; then \
		$(PIP_VENV) install -r requirements.txt; \
	elif [ -f "pyproject.toml" ]; then \
		$(PIP_VENV) install -e .; \
	else \
		echo "❌ No requirements.txt or pyproject.toml found. Please add dependencies."; \
		exit 1; \
	fi

dev: install run-api

run-api:
	@echo "🚀 Starting API on http://localhost:8888 …"
	$(UVICORN) app.api.fastapi_app:app --reload --port 8888

smoke:
	@echo "🧪 Running smoke tests against http://localhost:8888 …"
	$(PYTHON_VENV) scripts/smoke_test.py

clean:
	@echo "🧹 Removing virtualenv $(VENV_DIR)…"
	rm -rf $(VENV_DIR)
