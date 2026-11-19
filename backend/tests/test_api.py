"""API tests against the real app running on a local test server."""

import re

DEVANAGARI = re.compile(r"[ऀ-ॿ]")

ANSWERS = {
    "land_ownership": "owner",
    "income_tax_payer": False,
    "govt_employee": False,
    "social_security": False,
    "has_bank_account": True,
    "social_category": "obc",
    "gender": "female",
}


# --- status & website --------------------------------------------------------

def test_health(api):
    assert api("GET", "/health") == (200, {"status": "ok", "schemes": 17})


def test_root_returns_status_json(api):
    status, body = api("GET", "/")
    assert status == 200
    assert body["schemes_loaded"] == 17
    assert body["chatbot"]["languages"] == ["en", "hi"]


def test_root_redirects_browsers_to_website(api):
    status, headers, _ = api.raw("/", headers={"Accept": "text/html"})
    assert status in (302, 307)
    assert headers["location"].endswith("/app/")


def test_frontend_is_served(api):
    for path in ("/app/", "/app/dashboard.html", "/app/i18n.js", "/app/voice.js", "/app/style.css"):
        status, _, text = api.raw(path)
        assert status == 200, path
        assert text


# --- auth ------------------------------------------------------------------------

def test_register_validation_errors(api):
    status, body = api("POST", "/register", {
        "username": "x", "password": "1", "name": "", "age": 0, "income": -5,
        "land_size": 1, "state": "S", "district": "D",
    })
    assert status == 422
    assert body["status"] == "error"
    assert "Username" in body["message"] and "Age" in body["message"]


def test_register_rejects_bad_answers(api):
    status, body = api("POST", "/register", {
        "username": "valid_name", "password": "secret123", "name": "A", "age": 30, "income": 1,
        "land_size": 1, "state": "S", "district": "D", "land_ownership": "maybe",
    })
    assert status == 422


def test_duplicate_username_is_case_insensitive(api, farmer):
    status, body = api("POST", "/register", {
        "username": farmer["username"].upper(), "password": "secret123", "name": "Copy", "age": 30,
        "income": 1, "land_size": 1, "state": "S", "district": "D",
    })
    assert status == 409
    assert body["code"] == "username_taken"


def test_login(api, farmer):
    status, body = api("POST", "/login", {"username": farmer["username"], "password": "wrong-password"})
    assert status == 401 and body["status"] == "failed"
    status, body = api("POST", "/login", {"username": farmer["username"].upper(), "password": farmer["password"]})
    assert status == 200 and body["user_id"] == farmer["id"]


def test_plaintext_passwords_from_old_versions_are_upgraded(api):
    import main
    from database import get_connection

    with get_connection() as connection:
        connection.execute(
            "INSERT INTO farmers(username, password, name, age, income, land_size, state, district) "
            "VALUES ('legacy_user', 'oldpass99', 'Old', 40, 1000, 1, 'S', 'D')"
        )
    main._upgrade_plaintext_passwords()
    with get_connection() as connection:
        stored = connection.execute("SELECT password FROM farmers WHERE username = 'legacy_user'").fetchone()[0]
    assert stored.startswith("pbkdf2_sha256$")
    assert api("POST", "/login", {"username": "legacy_user", "password": "oldpass99"})[0] == 200


def test_farmers_list_never_returns_passwords(api, farmer):
    status, body = api("GET", "/farmers")
    assert status == 200
    assert all("password" not in row for row in body)


# --- profile -------------------------------------------------------------------------

def test_register_with_answers_and_partial_update(api, new_farmer):
    created = new_farmer(**ANSWERS)
    status, profile = api("GET", f"/profile/{created['id']}")
    assert status == 200
    assert {k: profile[k] for k in ANSWERS} == ANSWERS

    base = {k: created[k] for k in ("name", "age", "income", "land_size", "state", "district")}
    # Optional answers that aren't sent are kept...
    status, body = api("PUT", f"/profile/{created['id']}", {**base, "land_size": 9})
    assert status == 200
    assert body["profile"]["land_size"] == 9
    assert body["profile"]["land_ownership"] == "owner"
    # ...and null sets an answer back to "not sure".
    status, body = api("PUT", f"/profile/{created['id']}", {**base, "income_tax_payer": None})
    assert body["profile"]["income_tax_payer"] is None


def test_unknown_farmer_is_404(api):
    for path in ("/profile/999999", "/dashboard/999999", "/saved/999999", "/chat-history/999999"):
        status, body = api("GET", path)
        assert status == 404, path
        assert body["message"] == "Farmer not found"


# --- recommendations ---------------------------------------------------------------------

def test_dashboard_groups_and_prompts_for_missing_answers(api, farmer):
    status, body = api("GET", f"/dashboard/{farmer['id']}")
    assert status == 200
    rec = body["recommendations"]
    total = len(rec["eligible_schemes"]) + len(rec["maybe_schemes"]) + len(rec["not_eligible_schemes"])
    assert total == rec["total_schemes"] == 17
    assert rec["total_maybe"] > 0
    assert len(rec["profile_missing"]) == 7
    assert body["saved"] == []


def test_answers_turn_maybe_into_eligible(api, new_farmer):
    created = new_farmer(**ANSWERS)
    rec = api("GET", f"/recommend/{created['id']}")[1]
    names = {s["scheme_name"] for s in rec["eligible_schemes"]}
    assert {"PM-KISAN", "KCC", "APY"} <= names
    assert rec["profile_missing"] == []


def test_hindi_reasons(api, farmer):
    rec = api("GET", f"/recommend/{farmer['id']}?lang=hi")[1]
    reason = rec["eligible_schemes"][0]["why_recommended"][0]
    assert DEVANAGARI.search(reason)
    assert all(DEVANAGARI.search(label) for label in rec["profile_missing_labels"])


def test_bad_language_is_rejected(api, farmer):
    status, body = api("GET", f"/recommend/{farmer['id']}?lang=fr")
    assert status == 422


def test_scheme_endpoints(api):
    status, schemes = api("GET", "/schemes")
    assert status == 200 and len(schemes) == 17
    assert all(s["title_hi"] for s in schemes)
    assert api("GET", "/schemes/kcc")[1]["title"] == "Kisan Credit Card"
    assert api("GET", "/schemes/nope")[0] == 404


def test_single_scheme_eligibility(api, new_farmer):
    created = new_farmer(age=50, **ANSWERS)
    status, body = api("GET", f"/eligibility/{created['id']}/PM_KMY")
    assert status == 200
    assert body["status"] == "not_eligible"
    assert body["saved"] is None
    assert api("GET", f"/eligibility/{created['id']}/nope")[0] == 404


# --- saved schemes & document checklist ---------------------------------------------------------

def test_saved_scheme_tracking(api, farmer):
    uid = farmer["id"]

    status, body = api("PUT", f"/saved/{uid}/kcc", {})
    assert status == 200
    saved = body["saved"]
    assert saved["scheme_name"] == "KCC" and saved["status"] == "interested"
    assert saved["documents_total"] == 6 and saved["documents_done"] == []

    # Ticking documents (bad indices ignored) moves it to "collecting".
    saved = api("PUT", f"/saved/{uid}/KCC", {"documents_done": [2, 0, 2, 99, -1]})[1]["saved"]
    assert saved["documents_done"] == [0, 2]
    assert saved["status"] == "collecting"

    saved = api("PUT", f"/saved/{uid}/KCC", {"status": "applied", "notes": "Submitted at SBI"})[1]["saved"]
    assert saved["status"] == "applied" and saved["notes"] == "Submitted at SBI"
    assert saved["documents_done"] == [0, 2]  # unchanged

    assert api("PUT", f"/saved/{uid}/KCC", {"status": "lost"})[0] == 422
    assert api("PUT", f"/saved/{uid}/nope", {})[0] == 404

    listing = api("GET", f"/saved/{uid}")[1]
    assert [item["scheme_name"] for item in listing] == ["KCC"]
    assert api("GET", f"/dashboard/{uid}")[1]["saved"][0]["status"] == "applied"
    assert api("GET", f"/eligibility/{uid}/KCC")[1]["saved"]["status"] == "applied"

    assert api("DELETE", f"/saved/{uid}/KCC") == (200, {"status": "success", "deleted": True})
    assert api("GET", f"/saved/{uid}")[1] == []
    assert api("DELETE", f"/saved/{uid}/KCC")[1]["deleted"] is False


# --- chatbot -----------------------------------------------------------------------------------

def test_chat_flow_with_follow_up_and_history(api, new_farmer):
    uid = new_farmer(**ANSWERS)["id"]

    status, body = api("POST", f"/ask/{uid}", {"question": "What is KCC and who can apply?"})
    assert status == 200
    assert body["scheme"] == "KCC" and body["lang"] == "en" and body["source"] == "knowledge_base"

    body = api("POST", f"/ask/{uid}", {"question": "Documents required?"})[1]
    assert body["scheme"] == "KCC"
    assert "Documents needed" in body["answer"]

    body = api("POST", f"/ask/{uid}", {"question": "दस्तावेज़ क्या चाहिए?"})[1]
    assert body["lang"] == "hi" and body["scheme"] == "KCC"

    body = api("POST", f"/ask/{uid}", {"question": "Which schemes am I eligible for?", "lang": "hi"})[1]
    assert body["lang"] == "hi" and DEVANAGARI.search(body["answer"])

    history = api("GET", f"/chat-history/{uid}")[1]
    assert len(history) == 4
    assert history[0]["question"] == "Which schemes am I eligible for?"
    assert history[-1]["scheme_name"] == "KCC"

    assert api("DELETE", f"/chat-history/{uid}")[1]["deleted"] == 4
    assert api("GET", f"/chat-history/{uid}")[1] == []


def test_empty_question_is_rejected(api, farmer):
    status, body = api("POST", f"/ask/{farmer['id']}", {"question": "   "})
    assert status == 422
    assert body["message"].startswith("Question")


# --- quick check (home page, no account) ------------------------------------------------------

def test_quick_check(api):
    status, body = api("POST", "/quick-check", {"age": 35, "income": 80000, "land_size": 2.5})
    assert status == 200
    assert body["total"] == 17
    assert len(body["eligible"]) + len(body["maybe"]) + len(body["not_eligible"]) == 17
    assert body["maybe"], "without the optional answers some schemes need a check"
    assert set(body["eligible"][0]) == {"scheme_name", "title", "title_hi"}

    older = api("POST", "/quick-check", {"age": 70, "income": 80000, "land_size": 2.5})[1]
    assert "PM_KMY" in [item["scheme_name"] for item in older["not_eligible"]]

    assert api("POST", "/quick-check", {"age": 0, "income": -1, "land_size": 1})[0] == 422
