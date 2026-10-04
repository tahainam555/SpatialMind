# SpatialMind

**Agentic Vision-Language Model with Spatial Memory for Indoor 3D Scene Generation**  
*Final Year Project (Development Track) — FYP-1 Mid-Supervisory Milestone*

---

## 🎯 Architecture & Workflow

SpatialMind implements an observe-and-improve agentic loop rather than single-pass text-to-3D:

$$\text{User Request} \longrightarrow \text{Understand (Agent 1)} \longrightarrow \text{Plan (Agent 2)} \longrightarrow \text{Construct (Agent 3)} \longrightarrow \text{Verify (Agent 4)} \longrightarrow \text{Re-plan}$$

- **Agent 1 (Scene Understanding):** Natural language parsing with schema-validated Pydantic extraction (`NEAR`, `AWAY_FROM`, `AGAINST_WALL`, `CLEARANCE`). Supports both local deterministic mock and Google Gemini Pro / Flash.
- **Agent 2 (Spatial Planning & Memory):** Multi-start deterministic constraint solver. Persistent spatial memory maintains room geometry, object transforms, active constraints, and rejected poses across iterations.
- **Agent 3 (Scene Construction Contract):** Emits standard `spatialmind.scene/v1` payloads with real-world metric coordinates and Z-up rotations for Blender `bpy` integration.
- **Agent 4 (Verification & Refinement):** Deterministic AABB collision checks, room boundaries, door swing safety zones, window blockages, and clearance verification. Triggers closed-loop re-planning when violations occur.
- **Deterministic Workflow Controller:** Python state machine managing execution sequence and error recovery.

---

## 🚀 Running the Live Interface

### Quick Start (Single Full-Stack Server)
The built React frontend is bundled and auto-served directly by FastAPI:

```powershell
# In root directory:
cd backend
.\.venv\Scripts\python.exe -m uvicorn spatialmind.main:app --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser!

### Development Mode (Hot-Reload)
Run frontend and backend concurrently:
```powershell
# Terminal 1 - Backend API:
cd backend
.\.venv\Scripts\python.exe -m uvicorn spatialmind.main:app --reload --port 8000

# Terminal 2 - React Vite Dev Server:
cd frontend
npm.cmd run dev
```

---

## 🧪 CI/CD Pipeline & Quality Gates

The project strictly follows software engineering industry best practices:

- **Branching Strategy:**
  - `main`: Protected release branch. Every merge publishes a Docker image to GitHub Packages (GHCR) and creates a tagged release.
  - `develop`: Integration branch.
  - `feature/*`: Dedicated branches for each component (`feature/schemas-memory`, `feature/geometry-engine`, `feature/planner`, `feature/agent1-understanding`, `feature/controller`, `feature/frontend`).
- **Continuous Integration (CI):**
  - **Backend Test Matrix:** Python 3.10, 3.11, 3.12 running `ruff check`, `ruff format --check`, strict `mypy`, and 62 automated `pytest` unit tests with **>98% test coverage** (enforced by an 80% coverage threshold).
  - **Frontend Verification:** `oxlint` linting and TypeScript compile (`tsc -b && vite build`).
  - **Container Packaging:** Multi-stage production `Dockerfile` build check.
- **Continuous Delivery (CD):**
  - Automatic multi-architecture Docker image publish to **GitHub Container Registry (GHCR)**.
  - Automatic GitHub Release packaging (`v0.1.0-mid-eval`).
  - Optional Render web service deploy hook integration.

---

## 🖥️ Live Evaluation Features for Supervisory Presentation

1. **Preset Starters:** One-click loading of the proposal defense examples (Bedroom, Living Room, Office).
2. **Interactive 2D Spatial Canvas:** Real-time top-down SVG rendering with wall cardinal directions (North, South, East, West), door swing safety zones, and furniture front-facing orientation arrows.
3. **Interactive Object Inspector:** Hover over any furniture item to inspect real-time metric coordinates $(x, y)$, dimensions $(w \times d \times h)$, and rotation angles.
4. **Fault Injection (Self-Repair Demonstration):** Toggle *"Inject Fault (Evaluation Mode)"* to deliberately induce a collision. The state-machine execution trace visually shows:
   - Initial layout flagged with collisions by Agent 4.
   - Spatial memory updated with rejected poses.
   - Agent 2 re-planning a valid, collision-free alternative.
   - Result: 100% verified scene.

