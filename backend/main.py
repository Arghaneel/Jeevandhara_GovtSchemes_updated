"""Jeevandhara API — FastAPI backend.

Run from the backend folder:     uvicorn main:app --reload
or from the project root:        uvicorn backend.main:app --reload
or simply:                       python backend/main.py   (HOST / PORT env vars optional)

Then open http://127.0.0.1:8000/ for the website and /docs for the API docs.
"""

import json
import os
import sys
from pathlib import Path
from typing import Annotated, List, Literal, Optional

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

# Allow `uvicorn backend.main:app` from the project root as well.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI, HTTPException, Query, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field, StringConstraints  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

import chatbot  # noqa: E402
from auth import hash_password, is_hashed, verify_password  # noqa: E402
from database import get_connection  # noqa: E402
from messages import field_label  # noqa: E402
from recommender import (  # noqa: E402
    PROFILE_QUESTIONS,
    SCHEMES,
    check_eligibility,
    details_of,
    find_scheme,
    recommend_for,
    unanswered_questions,
)

app = FastAPI(
    title="Jeevandhara API",
    description="AI-powered government scheme recommendation system for farmers",
    version="3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# ERROR RESPONSES
# =========================
# Every error has the same shape: {"status": "error", "message": "...", "detail": ...}
# so the frontend can always show `message` to the farmer.

FIELD_LABELS = {
    "username": "Username",
    "password": "Password",
    "name": "Full name",
    "age": "Age",
    "income": "Annual income",
    "land_size": "Land size",
    "state": "State",
    "district": "District",
    "question": "Question",
    "status": "Status",
    "documents_done": "Documents",
    "notes": "Notes",
}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details, messages = [], []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path")]
        field = location[0] if location else ""
        message = str(error.get("msg", "is invalid"))
        details.append({"field": field, "message": message})
        messages.append(f"{FIELD_LABELS.get(field, field or 'Request')}: {message}")

    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": "; ".join(messages) or "Invalid request", "detail": details},
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": str(exc.detail), "detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


# =========================
# REQUEST MODELS
# =========================

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Lang = Literal["en", "hi"]
LandOwnership = Literal["owner", "tenant", "landless"]
SocialCategory = Literal["general", "obc", "sc", "st"]
Gender = Literal["male", "female", "other"]
ApplicationStatus = Literal["interested", "collecting", "applied", "approved", "rejected"]


class ProfileFields(BaseModel):
    name: ShortText
    age: int = Field(ge=1, le=120)
    income: float = Field(ge=0, le=1_000_000_000)
    land_size: float = Field(ge=0, le=1_000_000)
    state: ShortText
    district: ShortText

    # Optional questions that confirm or rule out specific schemes.
    # null = "not sure / not answered".
    land_ownership: Optional[LandOwnership] = None
    income_tax_payer: Optional[bool] = None
    govt_employee: Optional[bool] = None
    social_security: Optional[bool] = None
    has_bank_account: Optional[bool] = None
    social_category: Optional[SocialCategory] = None
    gender: Optional[Gender] = None


class RegisterUser(ProfileFields):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50)]
    password: Annotated[str, StringConstraints(min_length=6, max_length=128)]


class LoginUser(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class Question(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    lang: Optional[Lang] = None


class QuickCheck(BaseModel):
    age: int = Field(ge=1, le=120)
    income: float = Field(ge=0, le=1_000_000_000)
    land_size: float = Field(ge=0, le=1_000_000)


class SavedSchemeUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None
    documents_done: Optional[List[int]] = None
    notes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None


# =========================
# HELPERS
# =========================

BASE_PROFILE_FIELDS = ("name", "age", "income", "land_size", "state", "district")
BOOL_FIELDS = ("income_tax_payer", "govt_employee", "social_security", "has_bank_account")
PROFILE_FIELDS = ("id", "username") + BASE_PROFILE_FIELDS + PROFILE_QUESTIONS


def _profile_dict(row):
    keys = row.keys()
    data = {field: (row[field] if field in keys else None) for field in PROFILE_FIELDS}
    for field in BOOL_FIELDS:
        if data[field] is not None:
            data[field] = bool(data[field])
    return data


def _db_value(field, value):
    if field in BOOL_FIELDS and value is not None:
        return int(bool(value))
    return value


def get_farmer(user_id: int):
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM farmers WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Farmer not found")
    return _profile_dict(row)


def get_scheme_or_404(scheme_name):
    scheme = find_scheme(scheme_name)
    if scheme is None:
        raise HTTPException(status_code=404, detail=f"Scheme '{scheme_name}' not found")
    return scheme


def _upgrade_plaintext_passwords():
    """Hash any passwords stored in plain text by earlier versions."""
    with get_connection() as connection:
        rows = connection.execute("SELECT id, password FROM farmers").fetchall()
        for row in rows:
            if row["password"] and not is_hashed(row["password"]):
                connection.execute(
                    "UPDATE farmers SET password = ? WHERE id = ?",
                    (hash_password(row["password"]), row["id"]),
                )


_upgrade_plaintext_passwords()


# =========================
# HOME / STATUS
# =========================

@app.get("/")
def home(request: Request):
    # A browser visiting the API root is sent to the website.
    if "text/html" in request.headers.get("accept", "") and FRONTEND_DIR.is_dir():
        return RedirectResponse(url="/app/")

    return {
        "message": "Jeevandhara Backend Running",
        "schemes_loaded": len(SCHEMES),
        "chatbot": {
            "mode": "ollama" if chatbot.llm_available() else "knowledge_base",
            "ollama_url": chatbot.OLLAMA_URL,
            "ollama_model": chatbot.OLLAMA_MODEL,
            "languages": ["en", "hi"],
        },
        "frontend": "/app/",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    """Lightweight check for Docker / uptime monitors."""
    with get_connection() as connection:
        connection.execute("SELECT 1").fetchone()
    return {"status": "ok", "schemes": len(SCHEMES)}


# =========================
# AUTH
# =========================

@app.post("/register", status_code=201)
def register(user: RegisterUser):
    with get_connection() as connection:
        exists = connection.execute(
            "SELECT 1 FROM farmers WHERE username = ? COLLATE NOCASE", (user.username,)
        ).fetchone()
        if exists:
            return JSONResponse(
                status_code=409,
                content={"status": "error", "code": "username_taken",
                         "message": "That username is already taken. Please choose another."},
            )

        fields = ("username", "password") + BASE_PROFILE_FIELDS + PROFILE_QUESTIONS
        values = [user.username, hash_password(user.password)]
        values += [_db_value(f, getattr(user, f)) for f in BASE_PROFILE_FIELDS + PROFILE_QUESTIONS]
        cursor = connection.execute(
            f"INSERT INTO farmers({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
            values,
        )

    return {"status": "success", "message": "Registration Successful", "user_id": cursor.lastrowid}


@app.post("/login")
def login(user: LoginUser):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM farmers WHERE username = ? COLLATE NOCASE ORDER BY id LIMIT 1",
            (user.username,),
        ).fetchone()

        if row is None or not verify_password(user.password, row["password"]):
            return JSONResponse(
                status_code=401,
                content={"status": "failed", "message": "Invalid username or password"},
            )

        if not is_hashed(row["password"]):
            connection.execute(
                "UPDATE farmers SET password = ? WHERE id = ?",
                (hash_password(user.password), row["id"]),
            )

    return {
        "status": "success",
        "user_id": row["id"],
        "name": row["name"],
        "username": row["username"],
    }


# =========================
# PROFILE
# =========================

@app.get("/profile/{user_id}")
def profile(user_id: int):
    return get_farmer(user_id)


@app.put("/profile/{user_id}")
def update_profile(user_id: int, data: ProfileFields):
    get_farmer(user_id)  # 404 if missing

    # Base fields are always replaced; optional questions only when sent
    # (send null to clear an answer back to "not sure").
    fields = list(BASE_PROFILE_FIELDS) + [f for f in PROFILE_QUESTIONS if f in data.model_fields_set]
    values = [_db_value(f, getattr(data, f)) for f in fields]

    with get_connection() as connection:
        connection.execute(
            f"UPDATE farmers SET {', '.join(f'{f} = ?' for f in fields)} WHERE id = ?",
            values + [user_id],
        )

    return {"status": "success", "message": "Profile updated", "profile": get_farmer(user_id)}


# =========================
# SCHEMES & RECOMMENDATIONS
# =========================

@app.get("/schemes")
def list_schemes():
    return SCHEMES


@app.get("/schemes/{scheme_name}")
def get_scheme(scheme_name: str):
    return get_scheme_or_404(scheme_name)


def _recommendations(farmer, lang):
    groups = recommend_for(farmer, lang)
    missing = unanswered_questions(farmer)
    return {
        "farmer_name": farmer["name"],
        "age": farmer["age"],
        "income": farmer["income"],
        "land_size": farmer["land_size"],
        "total_schemes": len(SCHEMES),
        "total_eligible": len(groups["eligible"]),
        "total_maybe": len(groups["maybe"]),
        "eligible_schemes": groups["eligible"],
        "maybe_schemes": groups["maybe"],
        "not_eligible_schemes": groups["not_eligible"],
        "profile_missing": missing,
        "profile_missing_labels": [field_label(f, lang) for f in missing],
    }


@app.post("/quick-check")
def quick_check(data: QuickCheck, lang: Lang = "en"):
    """Anonymous check from the home page: age, income and land only, no account."""
    groups = recommend_for(data.model_dump(), lang)

    def brief(item):
        return {key: item.get(key) for key in ("scheme_name", "title", "title_hi")}

    return {
        "total": len(SCHEMES),
        "eligible": [brief(item) for item in groups["eligible"]],
        "maybe": [brief(item) for item in groups["maybe"]],
        "not_eligible": [brief(item) for item in groups["not_eligible"]],
    }


@app.get("/recommend/{user_id}")
def recommend(user_id: int, lang: Lang = "en"):
    return _recommendations(get_farmer(user_id), lang)


@app.get("/eligibility/{user_id}/{scheme_name}")
def scheme_eligibility(user_id: int, scheme_name: str, lang: Lang = "en"):
    """One scheme checked against one farmer, plus their saved/tracking entry."""
    farmer = get_farmer(user_id)
    scheme = get_scheme_or_404(scheme_name)
    result = check_eligibility(farmer, scheme, lang)
    return {"scheme_name": scheme["scheme_name"], **result, "saved": _get_saved(user_id, scheme, farmer, lang)}


@app.get("/dashboard/{user_id}")
def dashboard(user_id: int, lang: Lang = "en"):
    farmer = get_farmer(user_id)
    return {
        "profile": farmer,
        "recommendations": _recommendations(farmer, lang),
        "saved": _list_saved(user_id, farmer, lang),
    }


# =========================
# SAVED SCHEMES (application tracker + document checklist)
# =========================

def _saved_dict(row, scheme, farmer, lang):
    documents = details_of(scheme).get("documents_required") or []
    try:
        done = json.loads(row["documents_done"] or "[]")
    except ValueError:
        done = []
    done = sorted({i for i in done if isinstance(i, int) and 0 <= i < len(documents)})

    return {
        "scheme_name": scheme["scheme_name"],
        "title": scheme.get("title"),
        "title_hi": scheme.get("title_hi"),
        "tagline": details_of(scheme).get("tagline"),
        "tagline_hi": scheme.get("tagline_hi"),
        "website": scheme.get("website"),
        "status": row["status"],
        "notes": row["notes"],
        "documents_required": documents,
        "documents_total": len(documents),
        "documents_done": done,
        "eligibility_status": check_eligibility(farmer, scheme, lang)["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _get_saved(user_id, scheme, farmer, lang):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM saved_schemes WHERE user_id = ? AND scheme_name = ?",
            (user_id, scheme["scheme_name"]),
        ).fetchone()
    return _saved_dict(row, scheme, farmer, lang) if row else None


def _list_saved(user_id, farmer, lang):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM saved_schemes WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    result = []
    for row in rows:
        scheme = find_scheme(row["scheme_name"])
        if scheme:
            result.append(_saved_dict(row, scheme, farmer, lang))
    return result


@app.get("/saved/{user_id}")
def list_saved(user_id: int, lang: Lang = "en"):
    return _list_saved(user_id, get_farmer(user_id), lang)


@app.put("/saved/{user_id}/{scheme_name}")
def save_scheme(user_id: int, scheme_name: str, data: Optional[SavedSchemeUpdate] = None, lang: Lang = "en"):
    """Save a scheme, or update its status / ticked documents / notes."""
    farmer = get_farmer(user_id)
    scheme = get_scheme_or_404(scheme_name)
    data = data or SavedSchemeUpdate()
    documents_total = len(details_of(scheme).get("documents_required") or [])

    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM saved_schemes WHERE user_id = ? AND scheme_name = ?",
            (user_id, scheme["scheme_name"]),
        ).fetchone()

        done = json.loads(row["documents_done"] or "[]") if row else []
        if data.documents_done is not None:
            done = sorted({i for i in data.documents_done if 0 <= i < documents_total})

        status = data.status or (row["status"] if row else "interested")
        # Ticking the first document moves "interested" to "collecting documents".
        if data.status is None and status == "interested" and done:
            status = "collecting"

        notes = data.notes if "notes" in data.model_fields_set else (row["notes"] if row else None)

        if row:
            connection.execute(
                """
                UPDATE saved_schemes
                SET status = ?, documents_done = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, json.dumps(done), notes, row["id"]),
            )
        else:
            connection.execute(
                """
                INSERT INTO saved_schemes(user_id, scheme_name, status, documents_done, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, scheme["scheme_name"], status, json.dumps(done), notes),
            )

    return {"status": "success", "saved": _get_saved(user_id, scheme, farmer, lang)}


@app.delete("/saved/{user_id}/{scheme_name}")
def unsave_scheme(user_id: int, scheme_name: str):
    get_farmer(user_id)
    scheme = get_scheme_or_404(scheme_name)
    with get_connection() as connection:
        deleted = connection.execute(
            "DELETE FROM saved_schemes WHERE user_id = ? AND scheme_name = ?",
            (user_id, scheme["scheme_name"]),
        ).rowcount
    return {"status": "success", "deleted": bool(deleted)}


# =========================
# CHATBOT
# =========================

@app.post("/ask/{user_id}")
def ask_ai(user_id: int, query: Question):
    farmer = get_farmer(user_id)

    with get_connection() as connection:
        recent = connection.execute(
            """
            SELECT question, answer, scheme_name FROM chat_history
            WHERE user_id = ? ORDER BY id DESC LIMIT 3
            """,
            (user_id,),
        ).fetchall()

    previous_scheme = next((row["scheme_name"] for row in recent if row["scheme_name"]), None)
    history = [{"question": row["question"], "answer": row["answer"]} for row in reversed(recent)]
    reply_lang = chatbot.reply_language(query.question, query.lang)
    groups = recommend_for(farmer, reply_lang)

    result = chatbot.answer(
        query.question,
        farmer,
        eligible=groups["eligible"],
        maybe=groups["maybe"],
        previous_scheme=previous_scheme,
        history=history,
        lang=query.lang,
    )

    with get_connection() as connection:
        connection.execute(
            "INSERT INTO chat_history(user_id, question, answer, scheme_name) VALUES (?, ?, ?, ?)",
            (user_id, query.question, result["answer"], result["scheme"]),
        )

    return {
        "farmer": farmer["name"],
        "question": query.question,
        "answer": result["answer"],
        "scheme": result["scheme"],
        "suggestions": result["suggestions"],
        "source": result["source"],
        "lang": result["lang"],
    }


@app.get("/chat-history/{user_id}")
def chat_history(user_id: int, limit: int = Query(100, ge=1, le=1000)):
    get_farmer(user_id)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, question, answer, scheme_name, created_at FROM chat_history
            WHERE user_id = ? ORDER BY id DESC LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


@app.delete("/chat-history/{user_id}")
def clear_chat_history(user_id: int):
    get_farmer(user_id)
    with get_connection() as connection:
        deleted = connection.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,)).rowcount
    return {"status": "success", "deleted": deleted}


# =========================
# DEBUG
# =========================

@app.get("/farmers")
def all_farmers():
    """Internal debugging: registered farmers (passwords are never returned)."""
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM farmers ORDER BY id").fetchall()
    return [_profile_dict(row) for row in rows]


# =========================
# WEBSITE
# =========================
# Serving the frontend from the backend keeps everything on one origin, so the
# pages work at http://127.0.0.1:8000/app/ without a separate web server.

if FRONTEND_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"\n  Jeevandhara is running at http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}/\n")
    uvicorn.run(app, host=host, port=port)
