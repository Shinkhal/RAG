.PHONY: help install run test lint format typecheck check

# Windows PowerShell compatible targets
PYTHON ?= .venv\Scripts\python.exe

help:
	@echo Targets:
	@echo   install    Install dependencies from requirements.txt
	@echo   run        Start FastAPI app with reload
	@echo   test       Run pytest
	@echo   lint       Run ruff checks
	@echo   format     Format code with ruff
	@echo   typecheck  Run mypy on app/
	@echo   check      Run lint + typecheck + test

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) -m uvicorn app.main:app --reload

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

typecheck:
	$(PYTHON) -m mypy app

check: lint typecheck test
