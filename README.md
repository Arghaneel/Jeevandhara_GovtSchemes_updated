# Jeevandhara 🌾
> **AI-Powered Government Scheme Recommendation & Chatbot System for Farmers — in English and Hindi**

[![CI](https://github.com/1at24cs054-rgb/Govt_schems/actions/workflows/ci.yml/badge.svg)](https://github.com/1at24cs054-rgb/Govt_schems/actions/workflows/ci.yml)

Jeevandhara bridges the information gap between farmers and government schemes. It checks each farmer's profile against the rules of 17 central schemes, explains every match (or mismatch), helps them track applications and documents, and answers questions through a chatbot that understands English, Hindi and Hinglish — typed or spoken.

---

## 🚀 Key Features

*   **Try it before signing up**: the home page checks age, land and income against all 17 schemes as you type, and carries the answers into registration.
*   **Smarter matching with reasons**
    *   Age, income and land limits (hectare limits converted to acres), plus scheme-specific rules: land in your own name, tenant farmers, income tax payers, government employees, NPS/EPFO/ESIC members, bank account, social category and gender priorities.
    *   Three results per scheme: **Eligible**, **Check** (one more answer needed) and **Not eligible** — always with the reason, shown as a stamp on every scheme.
    *   Optional profile questions, a prompt to answer the ones that would confirm more schemes, and an editable profile.
*   **My Applications tracker**: save schemes with ☆, set the status (interested → collecting documents → applied → approved / rejected) and tick documents off a checklist with a progress bar.
*   **English / हिंदी**: one click switches the whole website, scheme names, eligibility explanations and the chatbot. The choice is remembered.
*   **AI chatbot assistant**
    *   Answers eligibility, benefits, documents, application and date questions from the scheme database — no AI install needed.
    *   Understands Hindi (Devanagari) and Hinglish ("pm kisan ke liye kaise apply kare") and replies in Hindi.
    *   🎤 Ask by voice and 🔊 hear answers read aloud (browser speech, Hindi and English).
    *   Follow-ups ("How to apply?" continues with the last scheme), personal checks ("Am I eligible for APY?"), suggestion chips, history and clear-chat.
    *   Uses **Ollama + Mistral** automatically when it's running, for more natural replies — falls back gracefully when not.
*   **Built for phones and first-time users**: one scheme list with Eligible / Check / Not eligible / All tabs and search, a profile panel that says which questions would confirm more schemes, large touch targets, full keyboard support, dark mode, and a bundled Devanagari-ready font so Hindi looks right even offline.
*   **Help, About, Contact & Privacy page**.
*   **Quality**: 90+ automated tests (unit, API and real-browser), Docker image, docker-compose, one-command start scripts and GitHub Actions CI.

---

## 🛠️ Technology Stack

*   **Frontend**: HTML5, CSS3, Vanilla JavaScript, Web Speech API (served by the backend, or any static server)
*   **Backend**: Python, FastAPI, Uvicorn
*   **Database**: SQLite (created and migrated automatically)
*   **Chatbot**: Intent and scheme detection over `schemes.json` (English/Hindi/Hinglish), optional Ollama (`mistral`) for generation
*   **Testing & delivery**: pytest, Playwright, Docker, GitHub Actions

---

## 📂 Project Structure

```text
Govt_schems/
├── backend/
│   ├── main.py              # FastAPI app: API routes + serves the website at /app/
│   ├── database.py          # SQLite schema, migrations and connections
│   ├── auth.py              # Password hashing (PBKDF2)
│   ├── recommender.py       # Eligibility matching (eligible / needs info / not eligible)
│   ├── scheme_rules.py      # Extra rules per scheme (ownership, exclusions, priorities)
│   ├── messages.py          # English + Hindi eligibility explanations, ₹ formatting
│   ├── chatbot.py           # Chatbot: knowledge base (en/hi) + optional Ollama
│   ├── schemes.json         # Master dataset of government schemes
│   ├── schemes_hi.json      # Hindi scheme names and taglines
│   ├── requirements.txt     # Python dependencies
│   ├── tests/               # pytest: recommender, chatbot, API, e2e/ browser tests
│   ├── test_db.py           # Quick database connection check
│   └── main_old.py, ai.py   # Earlier prototypes (not used by the app)
├── frontend/
│   ├── index / login / register / dashboard / scheme / help .html + .js
│   ├── common.js            # API base URL, session, theme, toasts, profile questions
│   ├── i18n.js              # English + Hindi text, language switch
│   ├── voice.js             # Voice input and read-aloud
│   ├── style.css            # Design system: colours, type, layout, light & dark
│   ├── fonts/               # Poppins (Latin + Devanagari subset, OFL licence)
│   └── schemes.json         # Offline copy of the scheme data (fallback)
├── scraper/                 # Raw scheme data collected from government sources
├── scratch/                 # create_schemes.py, test_api_flow.py
├── .github/workflows/ci.yml # Tests + Docker build on every push / PR
├── Dockerfile, docker-compose.yml, .dockerignore
├── run.sh, run.bat          # One-command start
├── requirements-dev.txt, pytest.ini
└── README.md
```

---

## 📦 Run It

### Option 1 — one command
*   **Windows**: double-click `run.bat`
*   **Linux / macOS**: `bash run.sh`

It creates `backend/.venv`, installs the dependencies the first time, starts the server and opens **http://127.0.0.1:8000/**.

### Option 2 — manually (Python 3.9+)
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py                 # or: uvicorn main:app --reload
```
Open **http://127.0.0.1:8000/** (it redirects to the website at `/app/`). API docs: http://127.0.0.1:8000/docs.
From the project root, `uvicorn backend.main:app --reload` also works; the database always stays in `backend/`.

### Option 3 — Docker
```bash
docker compose up --build                    # website + API
docker compose --profile ai up --build       # ...plus Ollama for the Mistral model
docker compose exec ollama ollama pull mistral   # first time with the AI profile
```
Or without Compose: `docker build -t jeevandhara . && docker run -p 8000:8000 -v jeevandhara-data:/data jeevandhara`.
Data is kept in the `jeevandhara-data` volume.

### Optional: Mistral via Ollama (without Docker)
The chatbot already answers from the scheme database. For more conversational answers (fully in Hindi when asked in Hindi), install [Ollama](https://ollama.com), run `ollama pull mistral` and keep it running — the backend detects it automatically (see `"chatbot"` in `GET /`).

### Settings (environment variables)

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Address for `python backend/main.py` |
| `JEEVANDHARA_DB` | `backend/jeevandhara.db` | Database file location |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama server |
| `OLLAMA_MODEL` | `mistral` | Model name |
| `OLLAMA_TIMEOUT` | `120` | Seconds to wait for an answer |
| `JEEVANDHARA_LLM` | `auto` | `off` = always use the built-in answers |

### Using a separate frontend server (optional)
Opening `frontend/index.html` directly or with VS Code Live Server also works: pages not served by the backend talk to `http://127.0.0.1:8000`. To use another address, run `localStorage.setItem("api_base", "http://your-host:8000")` in the browser console.

---

## ✅ Tests

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium     # for the browser tests
pytest                                    # everything (~30 s)
pytest -m "not e2e"                       # skip browser tests
```
Tests use a temporary database and never touch `backend/jeevandhara.db`. Browser tests are skipped automatically if Playwright isn't installed.
GitHub Actions runs the full suite and a Docker build on every push and pull request.

`python scratch/test_api_flow.py` is a quick manual check against a running server.

---

## 🔌 API Documentation

All errors return `{"status": "error", "message": "...", "detail": ...}` with a matching HTTP status code.
Endpoints marked 🌐 accept `?lang=hi` for Hindi explanations.

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Backend status (browsers are redirected to the website) |
| `/health` | `GET` | Health check (Docker / monitoring) |
| `/app/` | `GET` | The website |
| `/register` | `POST` | Register a farmer (`201`; `409` username taken; `422` invalid fields). Optional answers: `land_ownership`, `income_tax_payer`, `govt_employee`, `social_security`, `has_bank_account`, `social_category`, `gender` |
| `/login` | `POST` | Log in (`401` for wrong credentials) |
| `/quick-check` | `POST` 🌐 | Anonymous check used by the home page: `{"age", "income", "land_size"}` → scheme names grouped into `eligible`, `maybe`, `not_eligible` |
| `/profile/{user_id}` | `GET` / `PUT` | Read / update the profile (optional answers are kept unless sent; `null` = "not sure") |
| `/dashboard/{user_id}` | `GET` 🌐 | Profile + recommendations + saved schemes in one call |
| `/recommend/{user_id}` | `GET` 🌐 | `eligible_schemes`, `maybe_schemes`, `not_eligible_schemes` with reasons, and unanswered questions |
| `/eligibility/{user_id}/{scheme}` | `GET` 🌐 | One scheme checked for one farmer, plus its saved entry |
| `/schemes` | `GET` | All schemes (with Hindi names) |
| `/schemes/{scheme}` | `GET` | One scheme (case-insensitive, e.g. `kcc`) |
| `/saved/{user_id}` | `GET` 🌐 | Saved schemes with status and document progress |
| `/saved/{user_id}/{scheme}` | `PUT` 🌐 | Save a scheme or update `status`, `documents_done` (indices), `notes` |
| `/saved/{user_id}/{scheme}` | `DELETE` | Remove a saved scheme |
| `/ask/{user_id}` | `POST` | Chatbot: `{"question": "...", "lang": "en" \| "hi"}` → `answer`, `scheme`, `suggestions`, `source`, `lang` |
| `/chat-history/{user_id}` | `GET` / `DELETE` | Chat history (newest first, `?limit=`) / clear it |
| `/farmers` | `GET` | Debugging: registered farmers (passwords are never returned) |
# Jeevandhara_GovtSchemes_updated
