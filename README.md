# AICONNEX Industrial Excel Compiler

Deterministic ingestion service that transforms complex industrial spreadsheets into canonical, traceable long-format Parquet tables for AutoMLOps pipelines.

## Development Setup (Phase 0)

### 1. Prerequisites
- **Git** (2.40+)
- **Python 3.12**
- **uv** package manager
- **Docker & Docker Compose**

### 2. Environment Setup
```powershell
# Create virtual environment with Python 3.12
uv venv --python 3.12

# Sync all dependencies including dev tools
uv sync --extra dev

# Copy environment template
Copy-Item .env.example .env
```

### 3. Local Infrastructure (PostgreSQL & Temporal)
```powershell
docker compose -f infrastructure/local/docker-compose.yml up -d
```

### 4. Running Checks
```powershell
# Run linting and formatting checks
uv run ruff check .
uv run ruff format --check .

# Run test suite
uv run pytest -v

# Run the API server locally
uv run uvicorn apps.api.main:app --reload --port 8000
```
