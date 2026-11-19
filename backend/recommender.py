"""Scheme data loading and eligibility matching.

Every scheme is checked against the farmer's profile and lands in one of
three groups:

    eligible      all known rules pass
    maybe         nothing fails, but an unanswered profile question decides it
    not_eligible  at least one rule fails (with the reason)

Explanations come back in English or Hindi (``lang="hi"``).
"""

import json
import re
from pathlib import Path

from messages import field_label, format_inr, msg, normalize_lang
from scheme_rules import ACRES_PER_HECTARE, rules_for

BASE_DIR = Path(__file__).resolve().parent
SCHEMES_PATH = BASE_DIR / "schemes.json"
HINDI_PATH = BASE_DIR / "schemes_hi.json"

# Optional questions asked on the profile form (None = not answered yet).
PROFILE_QUESTIONS = (
    "land_ownership",
    "income_tax_payer",
    "govt_employee",
    "social_security",
    "has_bank_account",
    "social_category",
    "gender",
)


def load_schemes():
    with open(SCHEMES_PATH, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("schemes.json must contain a list of schemes")

    return [s for s in data if isinstance(s, dict) and s.get("scheme_name")]


def load_hindi_names():
    try:
        with open(HINDI_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


SCHEMES = load_schemes()
_HINDI = load_hindi_names()
for _scheme in SCHEMES:
    _hi = _HINDI.get(_scheme["scheme_name"], {})
    _scheme["title_hi"] = _hi.get("title")
    _scheme["tagline_hi"] = _hi.get("tagline")

_SCHEMES_BY_NAME = {s["scheme_name"].lower(): s for s in SCHEMES}


def find_scheme(name):
    if not name:
        return None
    return _SCHEMES_BY_NAME.get(str(name).strip().lower())


def details_of(scheme):
    details = scheme.get("scheme_details")
    return details if isinstance(details, dict) else {}


# -------------------------------------------------------------------------
# Value helpers
# -------------------------------------------------------------------------

def _number(value):
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return None


def _fmt_num(value):
    return f"{value:g}"


_LAND_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(hectares?|ha\b|acres?)?", re.IGNORECASE)


def max_land_in_acres(land_limit):
    """Return a scheme's maximum land holding in acres, or None if uncapped.

    Handles ``{"maximum_land_holding": "Up to 2 hectares ..."}``, plain numbers
    and free-text strings. Text without a number ("No land holding limit
    specified", "Varies by state") means there is no cap we can check.
    """
    if isinstance(land_limit, (int, float)) and not isinstance(land_limit, bool):
        return float(land_limit)

    if isinstance(land_limit, dict):
        text = land_limit.get("maximum_land_holding")
        if _number(text) is not None:
            return float(text)
        unit_required = False
    elif isinstance(land_limit, str):
        text = land_limit
        unit_required = True  # only trust free text that names a unit
    else:
        return None

    if not isinstance(text, str):
        return None

    match = _LAND_PATTERN.search(text)
    if not match:
        return None

    value = float(match.group(1))
    unit = (match.group(2) or "").lower()

    if not unit and unit_required:
        return None
    if unit.startswith("h"):
        value *= ACRES_PER_HECTARE

    return round(value, 2)


def _condition(condition, farmer):
    """True / False, or None when the profile doesn't answer it yet."""
    value = farmer.get(condition["field"])
    if value is None or value == "":
        return None
    if "in" in condition:
        return str(value).strip().lower() in condition["in"]
    if "equals" in condition:
        answer = _as_bool(value)
        return None if answer is None else answer == condition["equals"]
    if "max" in condition:
        number = _number(value)
        return None if number is None else number <= condition["max"]
    return None


# -------------------------------------------------------------------------
# Eligibility
# -------------------------------------------------------------------------

def check_eligibility(farmer, scheme, lang="en"):
    """Compare a farmer's profile with one scheme.

    ``farmer`` is a mapping with ``age``, ``income``, ``land_size`` (acres) and
    the optional PROFILE_QUESTIONS. Returns::

        {"status": "eligible" | "maybe" | "not_eligible", "eligible": bool,
         "reasons": [...], "failures": [...], "notes": [...],
         "missing": [field, ...], "missing_labels": [...], "missing_text": str}
    """
    lang = normalize_lang(lang)
    details = details_of(scheme)
    age = _number(farmer.get("age"))
    income = _number(farmer.get("income"))
    land = _number(farmer.get("land_size"))

    reasons, failures, notes, missing = [], [], [], []
    needs_confirmation = False

    # --- age -------------------------------------------------------------
    age_limit = details.get("age_limit")
    if isinstance(age_limit, dict) and age is not None:
        min_age = _number(age_limit.get("minimum_age"))
        max_age = _number(age_limit.get("maximum_age"))
        values = {"age": _fmt_num(age),
                  "min": _fmt_num(min_age) if min_age is not None else "",
                  "max": _fmt_num(max_age) if max_age is not None else ""}

        if min_age is not None and age < min_age:
            failures.append(msg("age_too_low", lang, **values))
        elif max_age is not None and age > max_age:
            failures.append(msg("age_too_high", lang, **values))
        elif min_age is not None and max_age is not None:
            reasons.append(msg("age_range_ok", lang, **values))
        elif min_age is not None:
            reasons.append(msg("age_min_ok", lang, **values))
        elif max_age is not None:
            reasons.append(msg("age_max_ok", lang, **values))

    # --- income ------------------------------------------------------------
    income_limit = details.get("income_limit")
    if isinstance(income_limit, dict) and income is not None:
        amount = _number(income_limit.get("amount"))
        if amount:
            values = {"income": format_inr(income), "limit": format_inr(amount)}
            if income > amount:
                failures.append(msg("income_too_high", lang, **values))
            else:
                reasons.append(msg("income_ok", lang, **values))

    # --- land size -----------------------------------------------------------
    max_land = max_land_in_acres(details.get("land_limit"))
    if max_land is not None and land is not None:
        values = {"land": _fmt_num(land), "limit": _fmt_num(max_land)}
        if land > max_land:
            failures.append(msg("land_too_high", lang, **values))
        else:
            reasons.append(msg("land_ok", lang, **values))

    # --- scheme-specific rules (ownership, exclusions, priorities) ----------
    for rule in rules_for(scheme.get("scheme_name")):
        if "note_if" in rule:
            if _condition(rule["note_if"], farmer) is True:
                notes.append(msg(rule["note"], lang))
            continue

        if "any_of" in rule:
            results = [_condition(c, farmer) for c in rule["any_of"]]
            if any(r is True for r in results):
                outcome = True
            elif any(r is None for r in results):
                outcome = None
            else:
                outcome = False
            unknown = [c["field"] for c, r in zip(rule["any_of"], results) if r is None]
        else:
            outcome = _condition(rule, farmer)
            unknown = [rule["field"]] if outcome is None else []

        if outcome is True:
            reasons.append(msg(rule["pass"], lang))
        elif outcome is False:
            if rule.get("soft"):
                notes.append(msg(rule["fail"], lang))
                needs_confirmation = True
            else:
                failures.append(msg(rule["fail"], lang))
        else:
            missing.extend(field for field in unknown if field not in missing)

    if failures:
        status = "not_eligible"
    elif missing or needs_confirmation:
        status = "maybe"
    else:
        status = "eligible"

    if not failures and not reasons and not missing:
        reasons.append(msg("open_to_all", lang))

    missing_labels = [field_label(field, lang) for field in missing]
    missing_text = msg("missing", lang, fields=", ".join(missing_labels)) if missing else ""

    return {
        "status": status,
        "eligible": status == "eligible",
        "reasons": reasons,
        "failures": failures,
        "notes": notes,
        "missing": missing,
        "missing_labels": missing_labels,
        "missing_text": missing_text,
    }


def scheme_summary(scheme):
    details = details_of(scheme)
    return {
        "scheme_name": scheme.get("scheme_name"),
        "title": scheme.get("title"),
        "title_hi": scheme.get("title_hi"),
        "website": scheme.get("website"),
        "tagline": details.get("tagline"),
        "tagline_hi": scheme.get("tagline_hi"),
        "benefits": details.get("benefits") or [],
        "documents_required": details.get("documents_required") or [],
        "application_process": details.get("application_process") or [],
    }


def recommend_for(farmer, lang="en"):
    """Group all schemes for a farmer: {"eligible": [...], "maybe": [...], "not_eligible": [...]}."""
    groups = {"eligible": [], "maybe": [], "not_eligible": []}

    for scheme in SCHEMES:
        try:
            result = check_eligibility(farmer, scheme, lang)
        except Exception:  # a malformed record should not break the dashboard
            continue

        if result["status"] == "not_eligible":
            groups["not_eligible"].append({
                "scheme_name": scheme.get("scheme_name"),
                "title": scheme.get("title"),
                "title_hi": scheme.get("title_hi"),
                "tagline": details_of(scheme).get("tagline"),
                "tagline_hi": scheme.get("tagline_hi"),
                "status": "not_eligible",
                "reasons": result["failures"],
            })
            continue

        item = scheme_summary(scheme)
        item["status"] = result["status"]
        item["notes"] = result["notes"]
        if result["status"] == "maybe":
            lead = [result["missing_text"]] if result["missing_text"] else []
            item["why_recommended"] = lead + result["notes"] + result["reasons"]
            item["missing"] = result["missing"]
            item["missing_labels"] = result["missing_labels"]
        else:
            item["why_recommended"] = result["reasons"] + result["notes"]
        groups[result["status"]].append(item)

    return groups


def unanswered_questions(farmer):
    return [field for field in PROFILE_QUESTIONS if farmer.get(field) is None]
