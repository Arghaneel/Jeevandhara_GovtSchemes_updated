"""Extra eligibility rules that go beyond age, income and land size.

Each rule comes from the eligibility / exclusion text in schemes.json (for
example PM-KISAN excludes income tax payers and government employees). Rules
use the optional profile questions:

    land_ownership   "owner" | "tenant" | "landless"
    income_tax_payer, govt_employee, social_security, has_bank_account   True/False
    social_category  "general" | "obc" | "sc" | "st"
    gender           "male" | "female" | "other"

A profile answer of None means "not answered yet"; the scheme is then shown as
"needs more info" instead of being ruled out.

Rule shapes:
    {"field": ..., "in": [...], "pass": code, "fail": code}        value must be one of
    {"field": ..., "equals": bool, "pass": code, "fail": code}     yes/no question
    {"field": ..., "max": number, ...}                              numeric upper bound
    {"any_of": [condition, ...], "pass": code, "fail": code}        at least one holds
    add "soft": True to turn a failure into "needs confirmation" instead of "not eligible"
    {"note_if": condition, "note": code}                            positive note only
"""

ACRES_PER_HECTARE = 2.47105
SMALL_MARGINAL_ACRES = round(2 * ACRES_PER_HECTARE, 2)  # 2 hectares

OWNS_LAND = {"field": "land_ownership", "in": ["owner"], "pass": "own_land_ok", "fail": "own_land_required"}
CULTIVATES = {"field": "land_ownership", "in": ["owner", "tenant"], "pass": "cultivate_ok", "fail": "cultivate_required"}
NOT_TAXPAYER = {"field": "income_tax_payer", "equals": False, "pass": "not_taxpayer_ok", "fail": "taxpayer_excluded"}
NOT_GOVT = {"field": "govt_employee", "equals": False, "pass": "not_govt_ok", "fail": "govt_excluded"}
NO_SOCIAL_SECURITY = {
    "field": "social_security", "equals": False,
    "pass": "no_social_security_ok", "fail": "social_security_excluded",
}

RULES = {
    # "All landholding farmer families possessing cultivable land in their names",
    # excluding government employees and income tax payers.
    "PM-KISAN": [OWNS_LAND, NOT_TAXPAYER, NOT_GOVT],

    # Owners, tenants, sharecroppers; landless only for animal husbandry/fisheries.
    "KCC": [{**CULTIVATES, "fail": "landless_kcc_note", "soft": True}],

    # Small & marginal farmers who own land; not NPS/EPFO/ESIC members or tax payers.
    "PM_KMY": [OWNS_LAND, NOT_TAXPAYER, NO_SOCIAL_SECURITY],

    # Farmers growing notified crops, including tenants and sharecroppers.
    "PMFBY": [CULTIVATES],

    # "Any Indian citizen who does not have an existing bank account".
    "PMJDY": [{"field": "has_bank_account", "equals": False, "pass": "no_bank_ok", "fail": "has_bank_excluded"}],

    # Needs an Aadhaar-linked savings account; not tax payers or covered by social security.
    "APY": [
        {"field": "has_bank_account", "equals": True, "pass": "needs_bank_ok", "fail": "needs_bank_required"},
        NOT_TAXPAYER,
        NO_SOCIAL_SECURITY,
    ],

    # "All registered land owners".
    "BHU_AADHAAR_ULPIN": [OWNS_LAND],

    # Landless labourers, small and marginal farmers, SC/ST families.
    "LAND_REFORMS": [{
        "any_of": [
            {"field": "land_ownership", "in": ["landless"]},
            {"field": "land_size", "max": SMALL_MARGINAL_ACRES},
            {"field": "social_category", "in": ["sc", "st"]},
        ],
        "pass": "land_reform_ok",
        "fail": "land_reform_excluded",
    }],

    # "Special preference for small/marginal, women, SC, and ST farmers".
    "SNAM": [
        {"note_if": {"field": "gender", "in": ["female"]}, "note": "priority_women"},
        {"note_if": {"field": "social_category", "in": ["sc", "st"]}, "note": "priority_scst"},
        {"note_if": {"field": "land_size", "max": SMALL_MARGINAL_ACRES}, "note": "priority_small"},
    ],
}


def rules_for(scheme_name):
    return RULES.get(scheme_name, [])
