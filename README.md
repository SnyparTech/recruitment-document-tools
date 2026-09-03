# Recruitment Document Tools

The workspace is organized into two completely decoupled, standalone applications:

```text
c:\Users\sriha\snypar\profile-bot/
│
├── Dossier compiler/             # 📑 Standalone Dossier Compiler Application
│   ├── frontend/                 # Vite + React (Port 5173)
│   ├── backend/                  # FastAPI + PyMuPDF DOCX Compiler (Port 8001)
│   ├── tests/                    # Dossier & rendering test suite
│   ├── pytest.ini
│   └── README.md
│
├── Profile search automation/    # 🔍 Standalone Candidate Search Automation Application
│   ├── frontend/                 # Vite + React (Port 5174)
│   ├── backend/                  # FastAPI + Selenium Automation Agent (Port 8002)
│   ├── tests/                    # Search, matching & ranking test suite
│   ├── pytest.ini
│   └── README.md
│
└── README.md
```

---

## 1. Dossier Compiler (Photo + ID + Resume)
A dedicated application to upload a candidate photo, government ID proof, and resume, and automatically compile them into a unified `.docx` file in exact sequence:
1. **Candidate Header & Photo** (22pt name, 13pt title, contact bar, 2.58" portrait)
2. **Verified Government ID Document** (6.2" wide exact image / rendered PDF)
3. **Original Candidate Resume** (6.5" wide exact verbatim copy / rendered PDF)

* **Backend**: `cd "Dossier compiler/backend" && py -m uvicorn app.main:app --reload --port 8001`
* **Frontend**: `cd "Dossier compiler/frontend" && npm run dev` (Runs on `http://localhost:5173`)

---

## 2. Profile Search Automation (Resdex Candidate Search Agent)
A dedicated recruitment intelligence application for parsing natural language job descriptions, mapping criteria to Resdex candidate search forms, and automating portal workflows.

* **Backend**: `cd "Profile search automation/backend" && py -m uvicorn app.main:app --reload --port 8002`
* **Frontend**: `cd "Profile search automation/frontend" && npm run dev` (Runs on `http://localhost:5174`)
