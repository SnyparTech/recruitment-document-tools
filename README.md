# Profile Bot AI - Unified Recruitment Intelligence & Dossier Suite

A unified recruitment platform combining **Autonomous Candidate Search Automation (Naukri Resdex)** and **Document Dossier Compilation (.DOCX)** under a single website and single backend.

```text
c:\Users\sriha\snypar\profile-bot/
├── frontend/                        # 🌐 UNIFIED SINGLE WEBSITE (Vite + React)
│   ├── index.html                   # Modern typography & SVG favicon
│   ├── src/
│   │   ├── App.jsx                  # Single app with seamless tab switching
│   │   ├── config.js                # Dynamic backend port selector (Port 8001)
│   │   ├── index.css                # Dark theme design system
│   │   ├── components/
│   │   │   ├── Navbar.jsx           # Unified navbar with brand, tab switcher & port config
│   │   │   ├── Icons.jsx            # SVG vector icon suite (no emojis)
│   │   │   └── SearchAgentView.jsx  # Resdex Candidate Search Agent
│   │   └── dossier-compiler/        # Candidate Dossier Compiler module (.DOCX)
│   └── package.json
│
├── backend/                         # ⚡ UNIFIED BACKEND (FastAPI on Port 8001)
│   ├── requirements.txt             # PyMuPDF, python-docx, Pillow, Selenium, FastAPI
│   └── app/
│       ├── main.py                  # Mounts /search, /profiles, /dossier, /health, and /app
│       ├── api/                     # API routers for search, profiles, and dossier
│       ├── services/                # DossierService, FormService, Matching, Ranking
│       ├── agents/                  # Resdex RequirementAgent
│       ├── selenium/                # Browser automation driver & form executor
│       └── core/                    # Security middlewares, DLP masking, rate limiter
│
├── tests/                           # 🧪 Unified test suite (59 passing tests)
├── pytest.ini                       # Test configuration
└── README.md
```

---

## Quick Start (Single Website + Single Backend)

### 1. Start the Unified Backend API
```powershell
cd backend
py -m uvicorn app.main:app --reload --port 8001
```
* **API Documentation**: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)
* **Health Check**: [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health)

### 2. Start the Unified Website
```powershell
cd frontend
npm run dev
```
* Access the unified portal at: **[http://localhost:5173](http://localhost:5173)**

---

## Features in the Unified Website

### 🔍 1. Candidate Search Agent (Naukri Resdex)
* Parse natural-language recruiter requirements into a structured `SearchPlan`.
* Validate plan deterministically against `resdex_schema.json`.
* Execution modes:
  * **Dry-Run**: Instant plan inspection and schema verification.
  * **Inspection**: Launches Chrome and populates the Resdex form without submitting.
  * **Live Search**: Fills form and triggers live search.
* Candidate matching & multi-factor scoring (0–100).

### 📑 2. Candidate Dossier Compiler
* Upload **Photo**, **ID Proof**, and **Resume**.
* High-resolution 150 DPI multi-page PDF rendering via PyMuPDF.
* Generates OpenXML `.DOCX` with exact layout:
  1. Candidate Header (Name, Title, Contact Line)
  2. Centered Candidate Photo (2.58" wide)
  3. Heading **"ID Proof"** (16pt Calibri Bold) + Centered ID document (6.2" wide)
  4. Page Break
  5. Heading **"Candidate Resume"** (16pt Calibri Bold) + Verbatim original resume pages (6.5" wide) with clean page breaks between multi-page resumes
  6. Blank footer (no reference tags or labels).

---

## Running Tests
Run all 59 unit and integration tests across both domains:
```powershell
py -m pytest tests/ -v
```
