# Candidate Dossier Compiler

A standalone application to upload a candidate photo, government identity proof, and resume, and automatically compile them into a unified OpenXML Word (`.docx`) file in strict sequence:
1. **Candidate Header & Photo** (22pt name, 13pt title, contact bar, 2.58" portrait)
2. **Verified Government ID Document** (6.2" wide exact image / rendered PDF)
3. **Original Candidate Resume** (6.5" wide exact verbatim copy / rendered PDF)

---

## Quick Start

### 1. Start the Backend (Port 8001)
```bash
cd backend
py -m pip install -r requirements.txt
py -m uvicorn app.main:app --reload --port 8001
```
* Interactive API Documentation: `http://127.0.0.1:8001/docs`

### 2. Start the Frontend (Port 5173)
```bash
cd frontend
npm install
npm run dev
```
* Web Interface: `http://localhost:5173`

---

## Running Tests
```bash
# From "Dossier compiler" root directory:
py -m pytest tests/ -v
```
