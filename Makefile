.PHONY: help install dev test coverage lint format clean docker docker-up docker-down

PYTHON  ?= python
PIP     := $(PYTHON) -m pip
PYTEST  := $(PYTHON) -m pytest
RUFF    := $(PYTHON) -m ruff

# ── Default target ─────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  PageVault — Developer Commands"
	@echo "  ──────────────────────────────"
	@echo "  make install     Install runtime dependencies"
	@echo "  make dev         Install all dev dependencies"
	@echo "  make run         Start the development server"
	@echo "  make test        Run the test suite"
	@echo "  make coverage    Run tests and open HTML coverage report"
	@echo "  make lint        Run ruff linter"
	@echo "  make format      Auto-format code with ruff"
	@echo "  make clean       Remove cache and build artifacts"
	@echo "  make docker      Build the Docker image"
	@echo "  make docker-up   Start with Docker Compose"
	@echo "  make docker-down Stop Docker Compose"
	@echo ""

# ── Setup ──────────────────────────────────────────────────────────────────────
install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

dev:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt

# ── Run ────────────────────────────────────────────────────────────────────────
run:
	$(PYTHON) app.py

# ── Tests ──────────────────────────────────────────────────────────────────────
test:
	$(PYTEST)

coverage:
	$(PYTEST) --cov=app --cov-report=html --cov-report=term-missing
	@echo "\n✅  Coverage report → htmlcov/index.html"
	-@$(PYTHON) -m webbrowser htmlcov/index.html

# ── Code quality ───────────────────────────────────────────────────────────────
lint:
	$(RUFF) check .

format:
	$(RUFF) format .
	$(RUFF) check --fix .

# ── Cleanup ────────────────────────────────────────────────────────────────────
clean:
	@$(PYTHON) -c "import pathlib, shutil; root = pathlib.Path('.'); [shutil.rmtree(p, ignore_errors=True) for p in root.rglob('__pycache__') if p.is_dir()]; [shutil.rmtree(p, ignore_errors=True) for p in root.rglob('.pytest_cache') if p.is_dir()]; [shutil.rmtree(p, ignore_errors=True) for p in root.rglob('htmlcov') if p.is_dir()]; [p.unlink(missing_ok=True) for p in root.rglob('*.pyc') if p.is_file()]; (root / '.coverage').unlink(missing_ok=True); (root / 'coverage.xml').unlink(missing_ok=True)"
	@echo "🧹  Cleaned."

# ── Docker ─────────────────────────────────────────────────────────────────────
docker:
	docker build -t pagevault:latest .

docker-up:
	docker compose up -d
	@echo "📚  PageVault running at http://localhost:5000"

docker-down:
	docker compose down
