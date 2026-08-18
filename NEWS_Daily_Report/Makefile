# =============================================================================
# NSE Daily Report - Makefile
# =============================================================================

PYTHON := python
PIP := pip

SRC := modules
TESTS := tests

# =============================================================================
# Installation
# =============================================================================

install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt

upgrade:
	$(PIP) install --upgrade pip

# =============================================================================
# Running
# =============================================================================

run:
	$(PYTHON) main.py

# =============================================================================
# Formatting
# =============================================================================

format:
	black .
	isort .

# =============================================================================
# Linting
# =============================================================================

lint:
	ruff check .
	flake8 .

# =============================================================================
# Type Checking
# =============================================================================

typecheck:
	mypy .

# =============================================================================
# Testing
# =============================================================================

test:
	pytest

coverage:
	pytest --cov=modules --cov-report=html

# =============================================================================
# Cleaning
# =============================================================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -f .coverage

# =============================================================================
# Full Quality Check
# =============================================================================

check:
	make format
	make lint
	make typecheck
	make test

# =============================================================================
# Help
# =============================================================================

help:
	@echo "Available commands:"
	@echo ""
	@echo "make install        Install runtime dependencies"
	@echo "make install-dev    Install development dependencies"
	@echo "make upgrade        Upgrade pip"
	@echo ""
	@echo "make run            Run application"
	@echo ""
	@echo "make format         Format code"
	@echo "make lint           Run Ruff + Flake8"
	@echo "make typecheck      Run MyPy"
	@echo ""
	@echo "make test           Run tests"
	@echo "make coverage       Generate coverage report"
	@echo ""
	@echo "make clean          Remove caches"
	@echo "make check          Run complete QA pipeline"