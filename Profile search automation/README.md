# Resdex Candidate Profile Search Automation

An autonomous recruitment intelligence service for searching, matching, and ranking candidate profiles across talent portals (e.g. Naukri Resdex) using a schema-driven, deterministic architecture.

---

## Architecture & Features
* **Natural Language Parsing**: Extracts required skills, preferred skills, seniority levels, salary bounds, and notice periods from raw hiring text.
* **Deterministic Field Mapping**: Targets precise DOM selectors on Resdex candidate search forms without LLM browser guessing.
* **Visual Inspection / Dry-Run**: Inspect the generated search plan and parameters before submitting live to the portal.
* **Persistent Session Support**: Reuses cookies and browser profile to maintain authenticated state.

---

## Quick Start

### 1. Start Backend (Port 8002)
```bash
cd backend
py -m pip install -r requirements.txt
py -m uvicorn app.main:app --reload --port 8002
```
* Interactive API Documentation: `http://127.0.0.1:8002/docs`

### 2. Start Frontend (Port 5174)
```bash
cd frontend
npm install
npm run dev
```
* Web Interface: `http://localhost:5174`

---

## Running Tests
```bash
# From "Profile search automation" root directory:
py -m pytest tests/ -v
```
