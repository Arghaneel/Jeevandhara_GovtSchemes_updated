"""English and Hindi text for eligibility explanations.

Eligibility checks produce message codes; ``msg(code, lang, **params)`` turns
them into a sentence in the farmer's language.
"""

SUPPORTED_LANGS = ("en", "hi")

MESSAGES = {
    "en": {
        "age_range_ok": "Your age ({age}) is within the {min}–{max} years range",
        "age_min_ok": "Your age ({age}) meets the minimum age of {min}",
        "age_max_ok": "Your age ({age}) is below the maximum of {max}",
        "age_too_low": "Minimum age is {min} (you are {age})",
        "age_too_high": "Maximum entry age is {max} (you are {age})",
        "income_ok": "Your income ({income}) is within the {limit} limit",
        "income_too_high": "Annual income must be at most {limit} (yours: {income})",
        "land_ok": "Your land ({land} acres) is within the {limit}-acre limit",
        "land_too_high": "Land holding must be at most {limit} acres (yours: {land} acres)",
        "open_to_all": "Open to all farmers — no age, income or land-size limit",
        "own_land_ok": "The farm land is registered in your name",
        "own_land_required": "The land must be registered in your name",
        "cultivate_ok": "You cultivate farm land (as owner or tenant)",
        "cultivate_required": "You must own or cultivate farm land (tenants and sharecroppers count)",
        "landless_kcc_note": "Landless applicants can get KCC only for animal husbandry or fisheries",
        "not_taxpayer_ok": "You are not an income tax payer",
        "taxpayer_excluded": "Income tax payers are not eligible",
        "not_govt_ok": "You are not a government employee or pensioner",
        "govt_excluded": "Serving or retired government employees are not eligible",
        "no_social_security_ok": "You are not covered by NPS, EPFO or ESIC",
        "social_security_excluded": "People already covered by NPS, EPFO or ESIC are not eligible",
        "needs_bank_ok": "You have a savings bank account",
        "needs_bank_required": "You need a savings bank account linked to Aadhaar",
        "no_bank_ok": "You don't have a bank account yet — this scheme opens one for you",
        "has_bank_excluded": "Only for people who don't already have a bank account",
        "land_reform_ok": "You qualify as a landless, small/marginal or SC/ST farmer",
        "land_reform_excluded": "Only for landless labourers, small/marginal farmers (up to 2 ha) or SC/ST families",
        "priority_women": "Priority: women farmers get a higher subsidy",
        "priority_scst": "Priority: SC/ST farmers get a higher subsidy",
        "priority_small": "Priority: small and marginal farmers get a higher subsidy",
        "missing": "Tell us {fields} to confirm",
        "acres": "acres",
    },
    "hi": {
        "age_range_ok": "आपकी आयु ({age}) {min}–{max} वर्ष की सीमा में है",
        "age_min_ok": "आपकी आयु ({age}) न्यूनतम आयु {min} वर्ष पूरी करती है",
        "age_max_ok": "आपकी आयु ({age}) अधिकतम {max} वर्ष से कम है",
        "age_too_low": "न्यूनतम आयु {min} वर्ष है (आपकी आयु {age} है)",
        "age_too_high": "प्रवेश की अधिकतम आयु {max} वर्ष है (आपकी आयु {age} है)",
        "income_ok": "आपकी आय ({income}) {limit} की सीमा में है",
        "income_too_high": "वार्षिक आय अधिकतम {limit} होनी चाहिए (आपकी: {income})",
        "land_ok": "आपकी ज़मीन ({land} एकड़) {limit} एकड़ की सीमा में है",
        "land_too_high": "ज़मीन अधिकतम {limit} एकड़ होनी चाहिए (आपकी: {land} एकड़)",
        "open_to_all": "सभी किसानों के लिए — आयु, आय या ज़मीन की कोई सीमा नहीं",
        "own_land_ok": "खेती की ज़मीन आपके नाम पर दर्ज है",
        "own_land_required": "ज़मीन आपके नाम पर दर्ज होनी चाहिए",
        "cultivate_ok": "आप खेती करते हैं (मालिक या बटाईदार के रूप में)",
        "cultivate_required": "आपके पास खेती की ज़मीन होनी चाहिए या आप उस पर खेती करते हों (किरायेदार और बटाईदार भी मान्य)",
        "landless_kcc_note": "भूमिहीन आवेदक केवल पशुपालन या मत्स्य पालन के लिए KCC ले सकते हैं",
        "not_taxpayer_ok": "आप आयकर दाता नहीं हैं",
        "taxpayer_excluded": "आयकर दाता इस योजना के पात्र नहीं हैं",
        "not_govt_ok": "आप सरकारी कर्मचारी या पेंशनभोगी नहीं हैं",
        "govt_excluded": "वर्तमान या सेवानिवृत्त सरकारी कर्मचारी पात्र नहीं हैं",
        "no_social_security_ok": "आप NPS, EPFO या ESIC के अंतर्गत नहीं हैं",
        "social_security_excluded": "जो पहले से NPS, EPFO या ESIC के अंतर्गत हैं, वे पात्र नहीं हैं",
        "needs_bank_ok": "आपके पास बचत बैंक खाता है",
        "needs_bank_required": "आधार से जुड़ा बचत बैंक खाता होना ज़रूरी है",
        "no_bank_ok": "आपका अभी बैंक खाता नहीं है — यह योजना खाता खोलती है",
        "has_bank_excluded": "केवल उन लोगों के लिए जिनका पहले से बैंक खाता नहीं है",
        "land_reform_ok": "आप भूमिहीन, लघु/सीमांत या SC/ST किसान की श्रेणी में आते हैं",
        "land_reform_excluded": "केवल भूमिहीन मज़दूरों, लघु/सीमांत किसानों (2 हेक्टेयर तक) या SC/ST परिवारों के लिए",
        "priority_women": "प्राथमिकता: महिला किसानों को अधिक सब्सिडी मिलती है",
        "priority_scst": "प्राथमिकता: SC/ST किसानों को अधिक सब्सिडी मिलती है",
        "priority_small": "प्राथमिकता: लघु और सीमांत किसानों को अधिक सब्सिडी मिलती है",
        "missing": "पुष्टि के लिए बताएं: {fields}",
        "acres": "एकड़",
    },
}

# How each optional profile question is named when we ask the farmer for it.
FIELD_LABELS = {
    "en": {
        "land_ownership": "whether the land is in your name",
        "income_tax_payer": "whether you pay income tax",
        "govt_employee": "whether you are a government employee or pensioner",
        "social_security": "whether you are covered by NPS/EPFO/ESIC",
        "has_bank_account": "whether you have a bank account",
        "social_category": "your social category",
        "gender": "your gender",
    },
    "hi": {
        "land_ownership": "ज़मीन आपके नाम पर है या नहीं",
        "income_tax_payer": "क्या आप आयकर देते हैं",
        "govt_employee": "क्या आप सरकारी कर्मचारी/पेंशनभोगी हैं",
        "social_security": "क्या आप NPS/EPFO/ESIC में हैं",
        "has_bank_account": "क्या आपका बैंक खाता है",
        "social_category": "आपकी सामाजिक श्रेणी",
        "gender": "आपका लिंग",
    },
}


def normalize_lang(lang):
    return lang if lang in SUPPORTED_LANGS else "en"


def msg(code, lang="en", **params):
    lang = normalize_lang(lang)
    template = MESSAGES[lang].get(code) or MESSAGES["en"].get(code, code)
    return template.format(**params)


def field_label(field, lang="en"):
    lang = normalize_lang(lang)
    return FIELD_LABELS[lang].get(field) or FIELD_LABELS["en"].get(field, field)


def format_inr(amount):
    """Format rupees with Indian digit grouping: 120000 -> ₹1,20,000."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return "-"
    negative = value < 0
    whole = str(int(round(abs(value))))
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{'-' if negative else ''}₹{whole}"
