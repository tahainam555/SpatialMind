# SpatialMind

Agentic Vision-Language Model with Spatial Memory for Indoor 3D Scene Generation (FYP).

Pipeline: **Understand → Remember → Plan → Construct → Verify → Re-plan.**
Semantic reasoning comes from an LLM/VLM, and geometric validity comes from deterministic computation.

## Structure
```
backend/    FastAPI + agents, geometry engine, controller (Python)
frontend/   React + Vite UI
.github/    CI/CD workflows, PR template
```

## Getting started
### Backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m uvicorn spatialmind.main:app --reload
```

### Frontend
```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Copy `.env.example` to `.env`. Use `LLM_PROVIDER=mock` for no-key development.

## Branching
- `main`: protected, release-only
- `develop`: integration branch
- `feature/*`: one per module, merged by PR after CI passes

## Quality gates (CI)
`ruff` lint and format, `mypy` strict, `pytest` with an 80% coverage gate, frontend lint and build, Docker build.
