"""Eligibility rules, land-unit conversion and data consistency."""

import re

import pytest

from messages import format_inr
from recommender import (
    PROFILE_QUESTIONS,
    SCHEMES,
    check_eligibility,
    find_scheme,
    max_land_in_acres,
    recommend_for,
    unanswered_questions,
)
from scheme_rules import RULES, SMALL_MARGINAL_ACRES

DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def farmer(**overrides):
    base = {"name": "Test", "age": 35, "income": 80000, "land_size": 2.0}
    base.update(overrides)
    return base


ALL_ANSWERS = {
    "land_ownership": "owner",
    "income_tax_payer": False,
    "govt_employee": False,
    "social_security": False,
    "has_bank_account": True,
    "social_category": "general",
    "gender": "male",
}


# --- data -----------------------------------------------------------------

def test_all_17_schemes_load_with_hindi_names():
    assert len(SCHEMES) == 17
    for scheme in SCHEMES:
        assert scheme["title_hi"], scheme["scheme_name"]
        assert scheme["tagline_hi"], scheme["scheme_name"]
        assert DEVANAGARI.search(scheme["title_hi"])


def test_rules_refer_to_real_schemes():
    for name in RULES:
        assert find_scheme(name) is not None, name


def test_find_scheme_is_case_insensitive():
    assert find_scheme("kcc")["scheme_name"] == "KCC"
    assert find_scheme(" pm-kisan ")["scheme_name"] == "PM-KISAN"
    assert find_scheme("nope") is None


# --- helpers ----------------------------------------------------------------

@pytest.mark.parametrize("limit, expected", [
    ({"maximum_land_holding": "Up to 2 hectares cultivable land"}, 4.94),
    ({"maximum_land_holding": "5 acres"}, 5.0),
    ({"maximum_land_holding": "3"}, 3.0),
    (7, 7.0),
    ("Up to 5 acres", 5.0),
    ("Applicable to all registered land parcels", None),
    ("Varies by state ceiling laws.", None),
    ("2", None),  # free text without a unit is not trusted
    (None, None),
])
def test_max_land_in_acres(limit, expected):
    assert max_land_in_acres(limit) == expected


@pytest.mark.parametrize("amount, text", [
    (0, "₹0"), (999, "₹999"), (120000, "₹1,20,000"), (1234567, "₹12,34,567"), (200799, "₹2,00,799"),
])
def test_format_inr(amount, text):
    assert format_inr(amount) == text


# --- age / income / land ------------------------------------------------------

def test_pm_kmy_age_limit():
    result = check_eligibility(farmer(age=45, **ALL_ANSWERS), find_scheme("PM_KMY"))
    assert result["status"] == "not_eligible"
    assert any("40" in reason for reason in result["failures"])


def test_pm_kmy_land_limit_uses_hectares():
    small = check_eligibility(farmer(land_size=4.9, **ALL_ANSWERS), find_scheme("PM_KMY"))
    large = check_eligibility(farmer(land_size=5.0, **ALL_ANSWERS), find_scheme("PM_KMY"))
    assert small["status"] == "eligible"
    assert large["status"] == "not_eligible"


def test_aif_income_limit():
    result = check_eligibility(farmer(income=300000), find_scheme("AIF"))
    assert result["status"] == "not_eligible"
    assert "₹2,00,799" in result["failures"][0]


def test_open_scheme_explains_why():
    result = check_eligibility(farmer(), find_scheme("NMSA"))
    assert result["status"] == "eligible"
    assert result["reasons"] == ["Open to all farmers — no age, income or land-size limit"]


# --- extra rules ----------------------------------------------------------------

def test_unanswered_question_means_maybe_not_rejected():
    result = check_eligibility(farmer(), find_scheme("PM-KISAN"))
    assert result["status"] == "maybe"
    assert set(result["missing"]) == {"land_ownership", "income_tax_payer", "govt_employee"}
    assert result["missing_text"].startswith("Tell us")


def test_pm_kisan_excludes_tax_payers_and_tenants():
    taxpayer = check_eligibility(farmer(**{**ALL_ANSWERS, "income_tax_payer": True}), find_scheme("PM-KISAN"))
    tenant = check_eligibility(farmer(**{**ALL_ANSWERS, "land_ownership": "tenant"}), find_scheme("PM-KISAN"))
    owner = check_eligibility(farmer(**ALL_ANSWERS), find_scheme("PM-KISAN"))
    assert taxpayer["status"] == "not_eligible"
    assert "Income tax payers are not eligible" in taxpayer["failures"]
    assert tenant["status"] == "not_eligible"
    assert owner["status"] == "eligible"


def test_kcc_allows_tenants_and_flags_landless():
    tenant = check_eligibility(farmer(land_ownership="tenant"), find_scheme("KCC"))
    landless = check_eligibility(farmer(land_ownership="landless"), find_scheme("KCC"))
    assert tenant["status"] == "eligible"
    assert landless["status"] == "maybe"
    assert any("animal husbandry" in note for note in landless["notes"])


def test_bank_account_rules_for_jan_dhan_and_apy():
    with_account = farmer(**ALL_ANSWERS)
    without_account = farmer(**{**ALL_ANSWERS, "has_bank_account": False})
    assert check_eligibility(with_account, find_scheme("PMJDY"))["status"] == "not_eligible"
    assert check_eligibility(without_account, find_scheme("PMJDY"))["status"] == "eligible"
    assert check_eligibility(with_account, find_scheme("APY"))["status"] == "eligible"
    assert check_eligibility(without_account, find_scheme("APY"))["status"] == "not_eligible"


def test_land_reforms_any_of_rule():
    small = farmer(land_size=SMALL_MARGINAL_ACRES)
    large_general = farmer(land_size=20, land_ownership="owner", social_category="general")
    large_unknown = farmer(land_size=20)
    large_st = farmer(land_size=20, social_category="st")
    scheme = find_scheme("LAND_REFORMS")
    assert check_eligibility(small, scheme)["status"] == "eligible"
    assert check_eligibility(large_general, scheme)["status"] == "not_eligible"
    assert check_eligibility(large_unknown, scheme)["status"] == "maybe"
    assert check_eligibility(large_st, scheme)["status"] == "eligible"


def test_snam_priority_notes():
    result = check_eligibility(farmer(gender="female", social_category="sc", land_size=2), find_scheme("SNAM"))
    assert result["status"] == "eligible"
    assert len(result["notes"]) == 3


def test_string_answers_from_forms_are_understood():
    result = check_eligibility(farmer(**{**ALL_ANSWERS, "income_tax_payer": "false"}), find_scheme("PM-KISAN"))
    assert result["status"] == "eligible"


# --- language -------------------------------------------------------------------

def test_hindi_explanations():
    result = check_eligibility(farmer(age=45, **ALL_ANSWERS), find_scheme("PM_KMY"), lang="hi")
    assert DEVANAGARI.search(result["failures"][0])
    maybe = check_eligibility(farmer(), find_scheme("PM-KISAN"), lang="hi")
    assert maybe["missing_text"].startswith("पुष्टि के लिए बताएं")


def test_unknown_language_falls_back_to_english():
    result = check_eligibility(farmer(), find_scheme("NMSA"), lang="fr")
    assert result["reasons"][0].startswith("Open to all")


# --- grouping ---------------------------------------------------------------------

def test_recommend_for_puts_every_scheme_in_one_group():
    groups = recommend_for(farmer(**ALL_ANSWERS))
    names = [s["scheme_name"] for g in groups.values() for s in g]
    assert sorted(names) == sorted(s["scheme_name"] for s in SCHEMES)
    for item in groups["eligible"] + groups["maybe"]:
        assert item["why_recommended"]
    for item in groups["not_eligible"]:
        assert item["reasons"]


def test_unanswered_questions():
    assert unanswered_questions(farmer()) == list(PROFILE_QUESTIONS)
    assert unanswered_questions(farmer(**ALL_ANSWERS)) == []
