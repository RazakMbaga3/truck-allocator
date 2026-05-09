# ─────────────────────────────────────────────────────────────────────────────
# Makefile — Smart Return Truck Allocator
# Lake Cement Limited / Nyati Cement, Tanzania
#
# Usage (Windows PowerShell — requires GNU Make or nmake):
#   make install       Install Python dependencies in venv
#   make migrate       Run Alembic migrations (create/upgrade DB schema)
#   make seed          Seed routes, transporters, customers from Excel data
#   make test          Run full pytest suite
#   make test-fast     Run tests excluding slow integration tests
#   make demo          Run demo_allocation.py (3 trucks × 10 orders)
#   make demo-assert   Run demo with assertions (CI-safe)
#   make run           Start FastAPI dev server (port 8001, hot reload)
#   make run-prod      Start Gunicorn production server (4 workers)
#   make lint          Run ruff + mypy type checks
#   make integration   Run scripts/integration_test.py end-to-end test
#   make clean         Remove __pycache__, .pytest_cache, *.pyc
#   make help          Show this help
#
# Prerequisites:
#   Python 3.11+ in PATH
#   GNU Make (Windows: choco install make  OR  scoop install make)
# ─────────────────────────────────────────────────────────────────────────────

PYTHON      := python
PIP         := $(PYTHON) -m pip
PYTEST      := $(PYTHON) -m pytest
ALEMBIC     := $(PYTHON) -m alembic
UVICORN     := $(PYTHON) -m uvicorn
VENV        := venv
VENV_PYTHON := $(VENV)/Scripts/python  # Windows; Linux: venv/bin/python

APP         := app.main:app
PORT        := 8001

.PHONY: all install migrate seed test test-fast demo demo-assert \
        run run-prod lint integration clean help


# ── Default target ────────────────────────────────────────────────────────────

all: help


# ── Environment setup ─────────────────────────────────────────────────────────

install:
	@echo "==> Creating virtual environment and installing dependencies"
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt
	@echo ""
	@echo "==> Done. Activate with:"
	@echo "    Windows:  venv\\Scripts\\activate"
	@echo "    Linux:    source venv/bin/activate"
	@echo ""
	@echo "==> Then run: make migrate && make seed && make run"


# ── Database ──────────────────────────────────────────────────────────────────

migrate:
	@echo "==> Running Alembic migrations"
	$(ALEMBIC) upgrade head
	@echo "==> Database schema up to date"

migrate-new:
	@echo "==> Creating new Alembic migration (autogenerate)"
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

migrate-history:
	$(ALEMBIC) history --verbose

migrate-rollback:
	@echo "==> Rolling back last migration"
	$(ALEMBIC) downgrade -1


# ── Seeding ───────────────────────────────────────────────────────────────────

seed: seed-routes seed-transporters
	@echo "==> All seed data loaded"

seed-routes:
	@echo "==> Seeding Tanzania route corridors"
	$(PYTHON) scripts/seed_routes.py

seed-transporters:
	@echo "==> Seeding transporter master data from Excel"
	$(PYTHON) scripts/seed_transporters.py

seed-customers:
	@echo "==> Seeding customer logistics profiles"
	$(PYTHON) scripts/seed_customers.py


# ── Development server ────────────────────────────────────────────────────────

run:
	@echo "==> Starting FastAPI dev server on http://localhost:$(PORT)"
	@echo "==> Dashboard: http://localhost:$(PORT)/"
	@echo "==> API docs:  http://localhost:$(PORT)/docs"
	$(UVICORN) $(APP) --reload --host 0.0.0.0 --port $(PORT) --log-level info

run-prod:
	@echo "==> Starting Gunicorn production server (4 workers)"
	$(PYTHON) -m gunicorn $(APP) \
	    --workers 4 \
	    --worker-class uvicorn.workers.UvicornWorker \
	    --bind 0.0.0.0:$(PORT) \
	    --access-logfile - \
	    --error-logfile -


# ── Tests ─────────────────────────────────────────────────────────────────────

test:
	@echo "==> Running full test suite"
	$(PYTEST) tests/ -v --tb=short --asyncio-mode=auto

test-fast:
	@echo "==> Running fast unit tests (skipping integration)"
	$(PYTEST) tests/ -v --tb=short --asyncio-mode=auto \
	    -m "not integration" \
	    --ignore=tests/test_odoo_sync.py

test-coverage:
	@echo "==> Running tests with coverage report"
	$(PYTEST) tests/ -v --tb=short --asyncio-mode=auto \
	    --cov=app --cov-report=term-missing --cov-report=html
	@echo "==> Coverage report: htmlcov/index.html"

test-matching:
	@echo "==> Running matching engine tests only"
	$(PYTEST) tests/test_matching_engine.py -v --tb=long --asyncio-mode=auto

test-savings:
	@echo "==> Running freight savings tests"
	$(PYTEST) tests/test_freight_savings.py tests/test_route_calculator.py \
	    -v --tb=short --asyncio-mode=auto

test-odoo:
	@echo "==> Running Odoo sync tests (mocked XML-RPC)"
	$(PYTEST) tests/test_odoo_sync.py -v --tb=short --asyncio-mode=auto


# ── Demo ─────────────────────────────────────────────────────────────────────

demo:
	@echo "==> Running end-to-end demo (3 trucks × 10 orders)"
	$(PYTHON) scripts/demo_allocation.py

demo-assert:
	@echo "==> Running demo with assertions (CI mode)"
	$(PYTHON) scripts/demo_allocation.py --assert


# ── Integration test ──────────────────────────────────────────────────────────

integration:
	@echo "==> Running full integration test against live server"
	@echo "==> (Requires server running on http://localhost:$(PORT))"
	$(PYTHON) scripts/integration_test.py


# ── Code quality ──────────────────────────────────────────────────────────────

lint:
	@echo "==> Running ruff linter"
	$(PYTHON) -m ruff check app/ tests/ scripts/
	@echo "==> Running mypy type checker"
	$(PYTHON) -m mypy app/ --ignore-missing-imports --no-strict-optional

format:
	@echo "==> Auto-formatting with ruff"
	$(PYTHON) -m ruff format app/ tests/ scripts/


# ── Odoo utilities ────────────────────────────────────────────────────────────

test-odoo-connection:
	@echo "==> Testing Odoo 15 XML-RPC connection"
	$(PYTHON) scripts/test_odoo_connection.py

sync-now:
	@echo "==> Triggering immediate Odoo sync via API"
	curl -s -X POST http://localhost:$(PORT)/api/orders/sync \
	    -H "X-API-Key: $$(grep APP_API_KEY .env | cut -d= -f2)" | python -m json.tool


# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	@echo "==> Cleaning Python artifacts"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "*.pyo" -delete 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	@echo "==> Clean complete"

clean-db:
	@echo "==> Removing local SQLite database"
	rm -f return_trucks.db
	@echo "==> Run 'make migrate && make seed' to rebuild"


# ── Help ─────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  Smart Return Truck Allocator — Lake Cement Limited / Nyati Cement"
	@echo "  ─────────────────────────────────────────────────────────────────"
	@echo ""
	@echo "  Setup:"
	@echo "    make install          Create venv + install dependencies"
	@echo "    make migrate          Run database migrations"
	@echo "    make seed             Seed routes + transporters from Excel"
	@echo ""
	@echo "  Development:"
	@echo "    make run              Start dev server (port $(PORT), hot reload)"
	@echo "    make demo             Run demo: 3 trucks × 10 orders"
	@echo "    make demo-assert      Demo with CI assertions"
	@echo ""
	@echo "  Testing:"
	@echo "    make test             Full pytest suite"
	@echo "    make test-fast        Unit tests only (skip Odoo tests)"
	@echo "    make test-coverage    Tests + HTML coverage report"
	@echo "    make test-matching    Matching engine tests only"
	@echo ""
	@echo "  Production:"
	@echo "    make run-prod         Gunicorn (4 workers)"
	@echo "    make integration      End-to-end integration test"
	@echo ""
	@echo "  Odoo:"
	@echo "    make test-odoo-connection   Verify XML-RPC connectivity"
	@echo "    make sync-now               Trigger immediate sync via API"
	@echo ""
	@echo "  Maintenance:"
	@echo "    make lint             ruff + mypy checks"
	@echo "    make format           Auto-format with ruff"
	@echo "    make clean            Remove __pycache__, *.pyc, coverage"
	@echo "    make clean-db         Delete local SQLite DB"
	@echo ""
