# Government Scheme Auto-Apply Agent — Stage 1 & Stage 2

A production-ready full-stack civic-tech platform for discovering, matching, and auto-applying to Indian government welfare schemes using AI demographic intake (LangChain + Google Gemini) and autonomous browser agents (TinyFish).

---

## 🏗 Project Architecture

```
gov-scheme-agent/
├── backend/
│   ├── database.py         # SQLite connection, engine & session generator
│   ├── main.py             # FastAPI app, CORS, CRUD, Matching & TinyFish endpoints
│   ├── matcher.py          # Eligibility rules evaluation & match scoring engine
│   ├── models.py           # SQLModel UserProfile, Scheme, and Application tables
│   ├── schemas.py          # Pydantic request/response validation schemas
│   ├── scheme_database.py  # Real Indian schemes catalog + idempotent seeder
│   ├── tinyfish_agent.py   # TinyFish web agent SDK integration & prompt goal builder
│   ├── requirements.txt    # Backend dependencies
│   ├── .env.example        # Environment variable template
│   └── .env                # Local secrets (GEMINI_API_KEY, TINYFISH_API_KEY)
├── frontend/
│   ├── index.html          # HTML5 entry with civic-tech branding
│   ├── package.json        # Frontend dependencies (React, Vite, Axios)
│   ├── vite.config.js      # Vite dev server configuration
│   └── src/
│       ├── App.css         # Modern civic portal stylesheet (Plain CSS)
│       ├── App.jsx         # 3-step profile form, tabs, AI Quick-Fill, DB inspector
│       ├── main.jsx        # React root mount
│       └── components/
│           └── SchemeList.jsx # Eligible scheme cards, criteria breakdown & TinyFish Auto-Apply
├── profiles.db             # SQLite database file (created at project root)
└── README.md               # Complete documentation & run guide
```

---

## ⚡ Quickstart Guide

### 1. Backend Setup & Run (FastAPI + SQLModel + SQLite)

Open a terminal in the `backend/` directory:

```powershell
cd C:\Users\Mayank\.gemini\antigravity\scratch\gov-scheme-agent\backend

# Activate the virtual environment:
.\.venv\Scripts\Activate.ps1

# Install any missing dependencies:
pip install -r requirements.txt

# Start the FastAPI server (runs on http://localhost:8000):
uvicorn main:app --reload --port 8000
```

> **Interactive API Docs:** Visit [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI) or [http://localhost:8000/redoc](http://localhost:8000/redoc).

---

### 2. Frontend Setup & Run (React + Vite)

Open a second terminal in the `frontend/` directory:

```powershell
cd C:\Users\Mayank\.gemini\antigravity\scratch\gov-scheme-agent\frontend

# Start Vite development server (runs on http://localhost:5173):
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 📡 API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/profile` | Create and validate a new citizen profile |
| `GET` | `/api/profile/{id}` | Retrieve profile details by ID |
| `PUT` | `/api/profile/{id}` | Update citizen profile fields |
| `GET` | `/api/profiles` | List all profiles (with pagination `skip` & `limit`) |
| `POST` | `/api/profile/conversational` | Extract demographic attributes from natural language |
| `GET` | `/api/schemes` | **Stage 2:** List all government welfare schemes |
| `GET` | `/api/schemes/{scheme_id}` | **Stage 2:** Retrieve specific scheme details & criteria |
| `GET` | `/api/match/{profile_id}` | **Stage 2:** Find eligible schemes sorted by match score |
| `POST` | `/api/apply` | **Stage 2:** Trigger TinyFish web agent auto-apply |
| `GET` | `/api/applications/{profile_id}` | **Stage 2:** List applications & execution statuses for a profile |
| `GET` | `/` | Service health status and metadata |

---

## 🧪 Sample cURL Commands

### 1. List All Available Government Schemes (`GET /api/schemes`)

```bash
curl -X GET "http://localhost:8000/api/schemes"
```

---

### 2. Match Eligible Schemes for a Citizen Profile (`GET /api/match/{profile_id}`)

```bash
curl -X GET "http://localhost:8000/api/match/1"
```

**Sample Response:**
```json
[
  {
    "scheme": {
      "id": 4,
      "name": "Post-Matric Scholarship for SC Students",
      "description": "Centrally sponsored scheme providing financial assistance including compulsory non-refundable fees...",
      "ministry": "Ministry of Social Justice and Empowerment",
      "state": null,
      "category": "Education",
      "official_url": "https://scholarships.gov.in",
      "application_url": "https://scholarships.gov.in/fresh/newstdRegfrmInstruction",
      "eligibility_text": "Citizen must belong to Scheduled Caste (SC) category...",
      "min_age": 14,
      "max_age": 35,
      "max_income": 250000.0,
      "allowed_castes": "sc",
      "allowed_genders": null,
      "allowed_states": null,
      "allowed_occupations": "student",
      "allowed_education": "12th,graduate,postgraduate"
    },
    "match_score": 1.0,
    "matched_criteria": [
      "Age 19 ≥ minimum age 14",
      "Age 19 ≤ maximum age 35",
      "Income ₹200,000 ≤ ₹250,000",
      "Caste category 'SC' eligible",
      "Occupation 'Student' eligible",
      "Education level '10th' eligible"
    ],
    "failed_criteria": []
  }
]
```

---

### 3. Trigger TinyFish Web Agent Auto-Apply (`POST /api/apply`)

```bash
curl -X POST "http://localhost:8000/api/apply" \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": 1,
    "scheme_id": 4
  }'
```

**Expected Response (202 Accepted):**
```json
{
  "application_id": 1,
  "status": "pending",
  "message": "Application #1 for 'Post-Matric Scholarship for SC Students' initiated. TinyFish web agent is automating form submission on the government portal in background.",
  "tinyfish_run_id": null
}
```

---

### 4. Check Application Status (`GET /api/applications/{profile_id}`)

```bash
curl -X GET "http://localhost:8000/api/applications/1"
```

**Sample Response:**
```json
[
  {
    "id": 1,
    "profile_id": 1,
    "scheme_id": 4,
    "status": "submitted",
    "tinyfish_run_id": "run_982348274",
    "result_url": "https://scholarships.gov.in/confirmation/app_982348274",
    "error_message": null,
    "created_at": "2026-10-16T03:45:00Z"
  }
]
```

---

## 🔒 Graceful Degradation & Resilience

- **TINYFISH_API_KEY Missing/Placeholder:** The backend catches missing credentials and returns a clear descriptive error in `error_message` while keeping the application server fully operational and responsive.
- **Idempotent Scheme Seeding:** The schemes table is checked on startup (`lifespan`); if records exist, seeding is safely skipped.
- **Timezone-Aware Timestamps:** All database models strictly use `datetime.now(timezone.utc)`.
