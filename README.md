# ResearchMind

<p align="center">
  <strong>An AI-powered research workspace that turns complex questions into structured, evidence-supported research reports.</strong>
</p>

<p align="center">
  <a href="https://researchmind-frontend-eaho.onrender.com"><strong>Live Demo</strong></a>
  ·
  <a href="https://researchmind-mnm7.onrender.com"><strong>API</strong></a>
  ·
  <a href="https://researchmind-mnm7.onrender.com/docs"><strong>API Docs</strong></a>
</p>

<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="ResearchMind dashboard" width="100%">
</p>

ResearchMind is an autonomous multi-agent research platform. It analyzes a research request, formulates focused subquestions, searches academic and web sources, compares findings, verifies claims against evidence, and produces a cited report with measurable quality signals.

The platform combines a React workspace with a FastAPI backend and a LangGraph agent workflow, while PostgreSQL with pgvector provides persistent research history and semantic source memory.

---

## Why ResearchMind

- **Adaptive research planning** - Breaks broad questions into focused, searchable subquestions.
- **Multi-agent execution** - Coordinates planning, academic research, web research, analysis, fact-checking, and report generation.
- **Evidence-oriented reports** - Separates findings, citations, source excerpts, and verification status.
- **Iterative gap detection** - Reframes missing information and can run additional focused research passes.
- **Semantic research memory** - Stores paper and web-source embeddings for similarity-based retrieval.
- **Live workflow visibility** - Tracks agent states and activity events as the research progresses.
- **Quality dashboard** - Measures coverage, citation accuracy, source quality, factual consistency, retrieval recall, and completion.
- **Persistent history** - Stores sessions, sources, claim verifications, reports, and evaluation metrics.
- **Export-ready reports** - Supports Markdown download and print/PDF workflows.
- **Cancellable jobs** - Stops a running research session before the next workflow step begins.

---

## Product Experience

### Research Workspace

Create a research session from a natural-language question, add optional guidance or scope constraints, and start a deep research workflow.

<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="ResearchMind research workspace" width="100%">
</p>

### Live Agent Execution

Follow the workflow graph as specialized agents move through planning, source collection, analysis, verification, and reporting.

<p align="center">
  <img src="docs/screenshots/live-execution.png" alt="Live multi-agent workflow" width="100%">
</p>

The live interface also displays a timestamped activity feed for inspectable workflow events.

<p align="center">
  <img src="docs/screenshots/live-activity.png" alt="Research activity feed" width="100%">
</p>

### Evidence-Supported Research Report

Reports present an executive summary, findings, source context, and a clear structure designed for reading, exporting, and further review.

<p align="center">
  <img src="docs/screenshots/research-report.png" alt="Generated research report" width="100%">
</p>

### Research Reliability Metrics

ResearchMind evaluates generated work across multiple dimensions and maps claim verifications back to supporting evidence.

<p align="center">
  <img src="docs/screenshots/quality-metrics.png" alt="Research quality and fact-check metrics" width="100%">
</p>

---

## Agent Architecture

```mermaid
flowchart LR
    U[Research Question] --> SG[Scope Gate]
    SG --> P[Research Planner]
    P --> M[Memory Retriever]
    M --> PR[Paper Researcher]
    PR --> WR[Web Researcher]
    WR --> A[Analysis Agent]
    A -->|Information gap found| GR[Gap Reframer]
    GR --> PR
    A -->|Evidence sufficient| FC[Fact Checker]
    FC --> N[Narrative Agent]
    N --> R[Report Generator]
    R --> DB[(PostgreSQL + pgvector)]
```

### Workflow

1. **Scope Gate** validates whether the request is in scope and whether additional clarification is needed.
2. **Research Planner** creates subquestions and targeted search queries.
3. **Memory Retriever** searches prior academic and web sources through vector similarity.
4. **Paper Researcher** retrieves relevant academic literature.
5. **Web Researcher** gathers supporting web sources.
6. **Analysis Agent** identifies patterns, comparisons, and missing information.
7. **Gap Reframer** converts missing evidence into additional focused subquestions.
8. **Fact Checker** evaluates claims and records verification status and confidence.
9. **Narrative and Report Agents** synthesize findings into a structured report.

The orchestrator supports a configurable maximum number of subquestions and additional research iterations.

---

## Technology Stack

| Layer | Technologies |
| --- | --- |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Lucide React |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic |
| AI Orchestration | LangGraph, LangChain, Google Gemini |
| Search | Tavily, arXiv, Semantic Scholar |
| Data | PostgreSQL, pgvector, SQLAlchemy, Asyncpg |
| Embeddings | Gemini text embeddings |
| Document Processing | PyMuPDF |
| Deployment | Docker, Docker Compose, Render |
| Evaluation | Custom quality metrics and pytest |

---

## API Overview

Interactive API documentation is available at [`/docs`](https://researchmind-mnm7.onrender.com/docs).

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health |
| `POST` | `/api/research` | Start a research session |
| `GET` | `/api/research` | List research sessions |
| `GET` | `/api/research/memory/search` | Search semantic research memory |
| `GET` | `/api/research/{session_id}` | Retrieve live session status |
| `POST` | `/api/research/{session_id}/cancel` | Cancel a running session |
| `GET` | `/api/research/{session_id}/report` | Retrieve the generated report |
| `GET` | `/api/research/{session_id}/metrics` | Retrieve research quality metrics |

---

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker and Docker Compose
- Google Gemini API key
- Tavily API key
- PostgreSQL with pgvector support for persistent storage

### 1. Clone the Repository

```bash
git clone https://github.com/Abdulsametsaba/ResearchMind.git
cd ResearchMind
```

### 2. Configure Environment Variables

Create a `.env` file in the project root.

```dotenv
# Application
APP_NAME=ResearchMind
APP_ENV=development
DEBUG=true
CROSS_ORIGIN=http://localhost:5173

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL_PLANNER=gemini-3.6-flash
GEMINI_MODEL_FAST=gemini-3.1-flash-lite
GEMINI_MODEL_EMBEDDING=models/text-embedding-004
GEMINI_TEMPERATURE=0.2

# Search providers
TAVILY_API_KEY=your_tavily_api_key
SEMANTIC_SCHOLAR_API_KEY=optional_semantic_scholar_api_key

# PostgreSQL
POSTGRES_USER=researchmind
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=researchmind
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://researchmind:your_secure_password@localhost:5432/researchmind

# Research limits
MAX_SUB_QUESTIONS=5
MAX_ITERATIONS=2
MAX_PAPERS_PER_SUBQUESTION=3
MAX_WEB_SOURCES_PER_SUBQUESTION=4
```

> Never commit `.env` or API keys to source control.

### 3. Run the Backend

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cd backend
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`, with Swagger documentation at `http://localhost:8000/docs`.

### 4. Run the Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env` when the frontend needs to target a different API:

```dotenv
VITE_API_URL=http://localhost:8000
```

Then start the development server:

```bash
npm run dev
```

Open `http://localhost:5173`.

### 5. Docker Deployment

The repository includes a backend Dockerfile and Docker Compose configuration:

```bash
docker compose up --build -d
docker compose logs -f api
```

The Compose API service listens on port `8000`. Stop the stack with:

```bash
docker compose down
```

---

## Project Structure

```text
ResearchMind/
├── backend/
│   ├── agents/            # Specialized research agents
│   ├── api/               # FastAPI routes and response schemas
│   ├── config/            # Typed environment configuration
│   ├── core/              # LLM setup and shared research state
│   ├── database/          # SQLAlchemy models and persistence services
│   ├── evaluation/        # Research quality metrics
│   ├── orchestrator/      # LangGraph workflow and cancellation state
│   ├── prompts/           # Agent prompt definitions
│   └── tools/             # Search, PDF, and embedding tools
├── frontend/
│   └── src/
│       ├── api/           # Typed frontend API client
│       ├── components/    # Dashboard, workflow, report, and metrics UI
│       └── types/         # Shared TypeScript response types
├── docs/screenshots/      # README screenshots
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Quality Evaluation

Completed research sessions are evaluated across six dimensions:

| Metric | Description |
| --- | --- |
| Research Coverage | Measures whether planned subquestions and source collection were completed |
| Citation Accuracy | Scores claim verifications and associated citation confidence |
| Source Quality | Combines source relevance, weighting academic material more heavily |
| Factual Consistency | Measures the proportion of claims verified or partially verified |
| Retrieval Recall | Compares retrieved sources with the theoretical source capacity |
| Completion Rate | Checks whether the workflow and final report were completed |

The overall score combines coverage, citation accuracy, source quality, factual consistency, and retrieval recall.

---

## Deployment

ResearchMind is deployed as separate frontend and backend services:

- **Frontend:** Render Static Site
- **Backend/API:** Docker-based Render Web Service
- **Database:** PostgreSQL with pgvector

For a production frontend deployment, set `VITE_API_URL` to the public API URL before building.

For the backend, configure all required API keys and database settings as environment variables in the hosting platform.

---

## Roadmap

- [ ] Streaming agent events over WebSockets or Server-Sent Events
- [ ] User accounts and private research workspaces
- [ ] Configurable model providers
- [ ] Citation export in BibTeX, RIS, and CSL formats
- [ ] Full-text PDF ingestion
- [ ] Collaborative report editing
- [ ] Automated benchmark and regression suites
- [ ] Expanded source provenance and traceability

---

## Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a focused feature branch.
3. Implement and test the change.
4. Open a pull request with a clear summary and validation notes.

For backend changes, run the relevant pytest suite. For frontend changes, build the Vite application before opening the pull request.

```bash
# Frontend validation
cd frontend
npm run build

# Backend tests
cd backend
pytest
```

---

## Author

Developed by [Abdul Samet Saba](https://github.com/Abdulsametsaba).
