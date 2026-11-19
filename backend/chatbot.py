"""Jeevandhara chatbot (English and Hindi).

Answers come from two layers:

1. Knowledge base (always on). The question is matched to a scheme in
   schemes.json (by name, acronym, Hindi name or common phrases such as
   "crop insurance" / "फसल बीमा") and answered from that scheme's structured
   fields: eligibility, benefits, documents, application steps, dates and
   FAQs. Follow-up questions like "How to apply?" / "आवेदन कैसे करें?" reuse
   the scheme the farmer last asked about.

2. Ollama LLM (optional). When an Ollama server with the configured model is
   reachable, the same scheme data is sent to the model as context so the
   reply reads more naturally (fully in Hindi when asked in Hindi). If Ollama
   is not running, or the call fails, the knowledge-base answer is used.

Replies are in Hindi when the question is written in Devanagari or the
website is set to Hindi (``lang="hi"``); otherwise English.

Environment variables:
    OLLAMA_URL      default http://127.0.0.1:11434
    OLLAMA_MODEL    default mistral
    OLLAMA_TIMEOUT  seconds, default 120
    JEEVANDHARA_LLM "auto" (default) uses Ollama when available, "off" never does
"""

import json
import os
import re
import time
import urllib.error
import urllib.request

from messages import format_inr
from recommender import SCHEMES, check_eligibility, details_of, find_scheme

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))
LLM_MODE = os.getenv("JEEVANDHARA_LLM", "auto").strip().lower()

# Talk to the local Ollama server directly, never through a system proxy.
_ollama_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# -------------------------------------------------------------------------
# Text normalisation (works for English, Hindi and Hinglish)
# -------------------------------------------------------------------------

_DEV = "ऀ-ॿ"  # Devanagari block
_WORD = rf"[\w{_DEV}]"


def has_devanagari(text):
    return re.search(rf"[{_DEV}]", str(text or "")) is not None


def _normalize(text):
    text = str(text or "").lower()
    text = text.replace("‌", "").replace("‍", "")   # zero-width joiners
    text = text.replace("़", "")                          # nukta: ज़ -> ज
    text = text.replace("ँ", "ं")                    # chandrabindu -> anusvara
    text = re.sub(r"[_\-'’।॥]", " ", text)           # _ - ' and danda ।
    text = re.sub(rf"[^\w{_DEV}₹\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains(text, phrase):
    return re.search(rf"(?<!{_WORD}){re.escape(phrase)}(?!{_WORD})", text) is not None


def _stem(token):
    # Very light English stemming so "loans"/"loan" and "documents"/"document" match.
    if token.isascii() and len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


_RAW_STOPWORDS = """
a an the is are was were be been am i me my we our you your it its this that these those of in on
at to for from by with and or not no do does did can could should would will shall may might what
which who whom whose how why when where there here about any all some much many more most get got
give tell please want need know help also than then so if as up per under into out over only just
like etc
scheme schemes yojana pradhan mantri pm national india indian government govt programme program
mission farmer farmers farming agriculture agricultural kisan fund card services
kya hai hain ke ki ka ko liye mujhe main mein mera meri mere kaise chahiye sakta sakte sakti aur
है हैं था थे का की के को में से पर लिए क्या कैसे मैं मेरा मेरी मेरे मुझे हम आप आपका आपकी और या
यह वह ये वो कौन कहां कितना कितनी एक भी तो ही कर करें करे करना करूं होता होती हो जी बताओ बताइए
बताएं बताये चाहिए सकता सकती सकते योजना योजनाएं योजनाओं किसान किसानों सरकार सरकारी सब कुछ नहीं
हां इस उस इसके उसके कोई किस किन मिलेगा मिलता मिलती
"""
STOPWORDS = {_normalize(word) for word in _RAW_STOPWORDS.split()}


def _tokens(text):
    return {_stem(t) for t in _normalize(text).split() if t not in STOPWORDS and len(t) > 2}


# -------------------------------------------------------------------------
# Vocabulary
# -------------------------------------------------------------------------

# Short, readable labels used in replies and suggestion chips.
SHORT_NAMES = {
    "PM_KMY": "PM-KMY",
    "BHU_AADHAAR_ULPIN": "ULPIN",
    "PGS_India_NCOF": "PGS-India",
    "WDC_PMKSY": "WDC-PMKSY",
    "LAND_REFORMS": "Land Reforms",
}

# Extra ways farmers refer to each scheme (English, Hindi, Hinglish), matched as whole words.
ALIASES = {
    "PM-KISAN": ["pm kisan", "pmkisan", "kisan samman", "samman nidhi", "6000", "6 000",
                 "पीएम किसान", "पी एम किसान", "किसान सम्मान निधि", "सम्मान निधि", "किसान सम्मान"],
    "KCC": ["kcc", "kisan credit card", "credit card", "crop loan", "kisan card",
            "किसान क्रेडिट कार्ड", "क्रेडिट कार्ड", "केसीसी", "फसल ऋण", "फसल लोन", "किसान कार्ड"],
    "PM_KMY": ["pm kmy", "pmkmy", "maandhan", "mandhan", "kisan pension", "farmer pension",
               "farmers pension", "old age pension", "pension",
               "मानधन", "किसान मानधन", "किसान पेंशन", "पेंशन", "वृद्धावस्था पेंशन"],
    "PMFBY": ["pmfby", "fasal bima", "crop insurance", "insurance", "crop loss", "crop damage",
              "फसल बीमा", "बीमा", "फसल नुकसान", "फसल खराब"],
    "PMJDY": ["pmjdy", "jan dhan", "jandhan", "bank account", "zero balance", "rupay",
              "जन धन", "जनधन", "बैंक खाता", "जीरो बैलेंस", "खाता खुलवाना"],
    "NMSA": ["nmsa", "sustainable agriculture", "soil health", "climate resilient",
             "सतत कृषि", "मृदा स्वास्थ्य", "सॉइल हेल्थ", "मिट्टी की जांच"],
    "AIF": ["aif", "agriculture infrastructure", "infrastructure fund", "agri infra",
            "warehouse", "cold storage", "post harvest",
            "कृषि अवसंरचना", "अवसंरचना कोष", "गोदाम", "कोल्ड स्टोरेज", "भंडारण"],
    "APY": ["apy", "atal pension", "atal", "pension", "अटल पेंशन", "अटल", "पेंशन"],
    "BHU_AADHAAR_ULPIN": ["ulpin", "bhu aadhaar", "bhu aadhar", "land parcel", "land id",
                          "भू आधार", "भूआधार", "यूएलपिन", "भूखंड पहचान"],
    "DILRMP": ["dilrmp", "land records", "land record", "bhulekh", "digital land",
               "भूमि रिकॉर्ड", "भूमि अभिलेख", "भूलेख", "खसरा", "खतौनी"],
    "ICAR": ["icar", "krishi vigyan", "kvk", "agricultural research",
             "आईसीएआर", "कृषि विज्ञान केंद्र", "केवीके", "कृषि अनुसंधान"],
    "LAND_REFORMS": ["land reform", "land reforms", "tenancy", "surplus land", "landless",
                     "भूमि सुधार", "भूमिहीन", "काश्तकारी"],
    "NEERANCHAL": ["neeranchal", "watershed project", "नीरांचल", "वाटरशेड परियोजना"],
    "PGS_India_NCOF": ["pgs", "pgs india", "organic certification", "organic farming", "organic",
                       "जैविक", "जैविक खेती", "जैविक प्रमाणन", "पीजीएस"],
    "SNAM": ["snam", "smam", "mechanization", "mechanisation", "machinery", "tractor",
             "custom hiring", "farm machine", "farm machines", "farm equipment",
             "मशीनरी", "ट्रैक्टर", "कृषि यंत्र", "यंत्रीकरण", "कस्टम हायरिंग", "मशीन"],
    "WDC_PMKSY": ["wdc", "pmksy", "watershed development", "krishi sinchayee",
                  "जलग्रहण", "वाटरशेड विकास", "कृषि सिंचाई", "सिंचाई योजना"],
    "eNAM": ["enam", "e nam", "national agriculture market", "mandi", "online market",
             "sell my crop", "sell crops", "sell produce",
             "ई नाम", "मंडी", "राष्ट्रीय कृषि बाजार", "फसल बेचना", "ऑनलाइन मंडी"],
}

INTENT_KEYWORDS = {
    "eligibility": ["eligible", "eligibility", "who can", "qualify", "qualifies", "criteria",
                    "can i get", "am i", "allowed", "entitled",
                    "patra", "patrata", "yogya", "yogyata",
                    "पात्र", "पात्रता", "योग्य", "योग्यता", "कौन ले सकता", "हकदार", "कौन आवेदन"],
    "documents": ["document", "documents", "docs", "papers", "paper", "proof", "proofs",
                  "certificate", "kyc", "ekyc", "id proof", "aadhaar card",
                  "dastavej", "dastavez", "kagaz", "kagzat", "kagjat",
                  "दस्तावेज", "दस्तावेजों", "कागज", "कागजात", "प्रमाण", "प्रमाणपत्र", "केवाईसी"],
    "apply": ["apply", "application", "register", "registration", "enrol", "enroll",
              "enrolment", "enrollment", "how to get", "process", "steps", "procedure",
              "where to", "sign up", "join",
              "aavedan", "avedan", "kaise apply", "kaise milega", "kaise kare", "kaise karen",
              "आवेदन", "अप्लाई", "पंजीकरण", "रजिस्ट्रेशन", "कैसे करें", "कैसे मिलेगा",
              "प्रक्रिया", "तरीका"],
    "benefits": ["benefit", "benefits", "amount", "money", "how much", "subsidy", "interest",
                 "premium", "rupees", "₹", "assistance", "support",
                 "advantage", "advantages", "get paid", "payment", "installment", "instalment",
                 "labh", "fayda", "faida", "paisa", "paise", "kitna", "kitne", "rashi",
                 "लाभ", "फायदा", "फायदे", "पैसा", "पैसे", "राशि", "कितना", "कितने", "सब्सिडी",
                 "अनुदान", "ब्याज", "प्रीमियम", "किस्त"],
    "dates": ["date", "dates", "deadline", "last date", "when", "timeline", "season",
              "cut off", "cutoff", "tarikh", "tareekh", "antim tithi", "kab",
              "तारीख", "तिथि", "अंतिम तिथि", "कब", "समय सीमा"],
    "overview": ["what is", "what s", "whats", "tell me about", "tell me more", "explain", "about",
                 "details", "information", "info", "overview", "meaning",
                 "kya hai", "batao", "bataiye", "jankari", "jaankari",
                 "क्या है", "बताओ", "बताइए", "बताएं", "जानकारी", "के बारे में", "विवरण"],
    "website": ["website", "portal", "link", "url", "site", "online",
                "वेबसाइट", "पोर्टल", "लिंक", "ऑनलाइन"],
    "recommend": ["my schemes", "which schemes", "which scheme", "what schemes",
                  "recommend", "recommended", "suggest", "eligible schemes", "schemes for me",
                  "best scheme", "best schemes", "list schemes", "all schemes",
                  "available schemes", "kaun si yojana", "konsi yojana", "kaunsi yojana",
                  "meri yojana", "mere liye",
                  "किन योजनाओं", "कौन सी योजना", "कौन सी योजनाएं", "कौनसी योजना",
                  "कौन कौन सी", "मेरे लिए", "योजनाएं बताओ", "योजनाएं सुझाओ", "सभी योजनाएं"],
    "greeting": ["hi", "hello", "hey", "namaste", "namaskar", "good morning",
                 "good afternoon", "good evening", "hii", "ram ram", "pranam",
                 "नमस्ते", "नमस्कार", "हेलो", "राम राम", "प्रणाम"],
    "thanks": ["thank", "thanks", "thank you", "dhanyavad", "dhanyawad", "shukriya", "ok thanks",
               "धन्यवाद", "शुक्रिया", "थैंक्स"],
}
_INTENT_PHRASES = {
    intent: [_normalize(k) for k in keywords] for intent, keywords in INTENT_KEYWORDS.items()
}
INTENT_WORDS = {_stem(word) for phrases in _INTENT_PHRASES.values() for phrase in phrases
                for word in phrase.split()}

# Words that only say *what* is being asked (not *which* scheme). A question made
# of just these, e.g. "Documents required?", is a follow-up to the last scheme.
FOLLOW_UP_WORDS = {_normalize(w) for w in (
    "required", "require", "needed", "necessary", "list", "full", "complete", "step",
    "procedure", "form", "online", "offline", "detail", "eligible", "eligibility",
    "document", "apply", "benefit", "date", "process", "much", "amount", "money",
    "ज़रूरी", "जरूरी", "आवश्यक", "पूरी", "सूची", "फॉर्म",
)}

SECTION_ORDER = ["overview", "eligibility", "benefits", "documents", "apply", "dates", "website"]

# -------------------------------------------------------------------------
# Reply templates
# -------------------------------------------------------------------------

T = {
    "en": {
        "elig_header": "👨‍🌾 Who is eligible for {label}:",
        "elig_none": "• No specific eligibility rules are listed.",
        "profile_ok": "✅ Your profile: you appear eligible ({reasons}).",
        "profile_fail": "❌ Your profile: you may not be eligible — {failures}.",
        "profile_maybe": "❔ Your profile: you may be eligible. {missing}.",
        "profile_note": "ℹ️ {notes}.",
        "final_note": "(Final approval is decided by the implementing agency.)",
        "benefits_header": "💰 Benefits of {label}:",
        "benefits_none": "💰 No benefit details are listed for {label}.",
        "docs_header": "📂 Documents needed for {label}:",
        "docs_none": ("📂 No document checklist is listed for {label}. "
                      "Please contact your nearest bank, CSC or Krishi Vigyan Kendra."),
        "apply_header": "📝 How to apply for {label}:",
        "apply_none": "• Visit the official website or your nearest CSC.",
        "website_line": "🌐 Official website: {url}",
        "dates_header": "📅 Important dates for {label}:",
        "dates_none": "No fixed deadline is listed — registration is ongoing.",
        "website_only": "🌐 Official website for {label}: {url}",
        "not_listed": "not listed",
        "related": "Related: {items}",
        "profile_fmt": "age {age}, income {income}, {land} acres",
        "rec_none": ("Based on your profile ({profile}) I could not find a matching scheme. "
                     "Try updating your profile, or ask me about a specific scheme."),
        "rec_header": "🌾 Based on your profile ({profile}), you are eligible for {n} of {total} schemes:",
        "rec_maybe": "❔ {n} more may fit once you answer the extra profile questions: {names}",
        "rec_footer": "Ask me about any of them, e.g. \"How to apply for {name}?\"",
        "greeting": ("Namaste {name}! 🙏 I can help you with government schemes — eligibility, "
                     "benefits, documents and how to apply.\n"
                     "Try \"Which schemes am I eligible for?\" or \"What is KCC?\""),
        "thanks": "You're welcome, {name}! 🙏 Ask me anything else about government schemes.",
        "related_found": ("I couldn't find an exact match, but these schemes look related: {names}.\n"
                          "Ask about one of them, e.g. \"What is {first}?\""),
        "no_match": ("Sorry {name}, I couldn't match that to a scheme. I can answer questions about: "
                     "{known}.\nTry \"Which schemes am I eligible for?\" or \"What is PMFBY?\""),
        "english_note": "",
        "sugg_eligibility": "Am I eligible for {n}?",
        "sugg_documents": "Documents for {n}?",
        "sugg_apply": "How to apply for {n}?",
        "sugg_benefits": "Benefits of {n}?",
        "sugg_dates": "Important dates for {n}?",
        "sugg_what": "What is {n}?",
        "defaults": ["Which schemes am I eligible for?", "What is PM-KISAN?", "How to apply for KCC?"],
        "llm_language": "Reply in simple English.",
    },
    "hi": {
        "elig_header": "👨‍🌾 {label} के लिए कौन पात्र है:",
        "elig_none": "• पात्रता के कोई विशेष नियम नहीं दिए गए हैं।",
        "profile_ok": "✅ आपकी प्रोफ़ाइल के अनुसार आप पात्र लगते हैं ({reasons})।",
        "profile_fail": "❌ आपकी प्रोफ़ाइल के अनुसार आप शायद पात्र नहीं हैं — {failures}।",
        "profile_maybe": "❔ आप शायद पात्र हैं। {missing}।",
        "profile_note": "ℹ️ {notes}।",
        "final_note": "(अंतिम स्वीकृति योजना लागू करने वाली संस्था देती है।)",
        "benefits_header": "💰 {label} के लाभ:",
        "benefits_none": "💰 {label} के लाभों की जानकारी उपलब्ध नहीं है।",
        "docs_header": "📂 {label} के लिए ज़रूरी दस्तावेज़:",
        "docs_none": ("📂 {label} के लिए दस्तावेज़ों की सूची उपलब्ध नहीं है। "
                      "कृपया नज़दीकी बैंक, CSC या कृषि विज्ञान केंद्र से संपर्क करें।"),
        "apply_header": "📝 {label} के लिए आवेदन कैसे करें:",
        "apply_none": "• आधिकारिक वेबसाइट या नज़दीकी CSC पर जाएँ।",
        "website_line": "🌐 आधिकारिक वेबसाइट: {url}",
        "dates_header": "📅 {label} की महत्वपूर्ण तिथियाँ:",
        "dates_none": "कोई निश्चित अंतिम तिथि नहीं है — पंजीकरण जारी है।",
        "website_only": "🌐 {label} की आधिकारिक वेबसाइट: {url}",
        "not_listed": "उपलब्ध नहीं",
        "related": "संबंधित: {items}",
        "profile_fmt": "आयु {age}, आय {income}, {land} एकड़",
        "rec_none": ("आपकी प्रोफ़ाइल ({profile}) के अनुसार कोई मेल खाती योजना नहीं मिली। "
                     "अपनी प्रोफ़ाइल अपडेट करें या किसी योजना के बारे में पूछें।"),
        "rec_header": "🌾 आपकी प्रोफ़ाइल ({profile}) के अनुसार आप {total} में से {n} योजनाओं के पात्र हैं:",
        "rec_maybe": "❔ प्रोफ़ाइल के बाकी सवालों के जवाब देने पर {n} और योजनाएँ मिल सकती हैं: {names}",
        "rec_footer": "इनमें से किसी के बारे में पूछें, जैसे \"{name} के लिए आवेदन कैसे करें?\"",
        "greeting": ("नमस्ते {name} जी! 🙏 मैं सरकारी योजनाओं में आपकी मदद कर सकता हूँ — पात्रता, "
                     "लाभ, दस्तावेज़ और आवेदन की प्रक्रिया।\n"
                     "पूछें: \"मैं किन योजनाओं के लिए पात्र हूँ?\" या \"किसान क्रेडिट कार्ड क्या है?\""),
        "thanks": "आपका स्वागत है, {name} जी! 🙏 सरकारी योजनाओं के बारे में कुछ और पूछें।",
        "related_found": ("सटीक मेल नहीं मिला, लेकिन ये योजनाएँ संबंधित लगती हैं: {names}।\n"
                          "इनमें से किसी के बारे में पूछें, जैसे \"{first} क्या है?\""),
        "no_match": ("माफ़ कीजिए {name} जी, यह किसी योजना से मेल नहीं खाया। मैं इन योजनाओं के बारे में "
                     "बता सकता हूँ: {known}।\nपूछें: \"मैं किन योजनाओं के लिए पात्र हूँ?\" "
                     "या \"फसल बीमा योजना क्या है?\""),
        "english_note": "ℹ️ योजना का विस्तृत विवरण अभी अंग्रेज़ी में उपलब्ध है।",
        "sugg_eligibility": "क्या मैं {n} के लिए पात्र हूँ?",
        "sugg_documents": "{n} के लिए दस्तावेज़?",
        "sugg_apply": "{n} के लिए आवेदन कैसे करें?",
        "sugg_benefits": "{n} के लाभ क्या हैं?",
        "sugg_dates": "{n} की महत्वपूर्ण तिथियाँ?",
        "sugg_what": "{n} क्या है?",
        "defaults": ["मैं किन योजनाओं के लिए पात्र हूँ?", "पीएम किसान क्या है?",
                     "किसान क्रेडिट कार्ड के लिए आवेदन कैसे करें?"],
        "llm_language": "Reply ONLY in simple Hindi (Devanagari script). Keep scheme names and numbers as they are.",
    },
}


def _t(lang, key, **params):
    template = T.get(lang, T["en"]).get(key) or T["en"][key]
    return template.format(**params) if params else template


# -------------------------------------------------------------------------
# Scheme matching
# -------------------------------------------------------------------------


def short_name(scheme):
    name = scheme.get("scheme_name", "")
    return SHORT_NAMES.get(name, name)


def _title(scheme, lang):
    if lang == "hi" and scheme.get("title_hi"):
        return scheme["title_hi"]
    return scheme.get("title") or scheme.get("scheme_name")


def _label(scheme, lang):
    return f"{_title(scheme, lang)} ({short_name(scheme)})"


def _tagline(scheme, lang):
    if lang == "hi" and scheme.get("tagline_hi"):
        return scheme["tagline_hi"]
    return details_of(scheme).get("tagline") or ""


def _aliases_for(scheme):
    name = scheme["scheme_name"]
    code = _normalize(name)
    aliases = {code, code.replace(" ", ""), _normalize(SHORT_NAMES.get(name, name))}
    for title in (scheme.get("title"), scheme.get("title_hi")):
        if title:
            aliases.add(_normalize(title))
    aliases.update(_normalize(a) for a in ALIASES.get(name, []))
    return {a for a in aliases if a}


_SCHEME_INDEX = []
for _scheme in SCHEMES:
    _details = details_of(_scheme)
    _SCHEME_INDEX.append({
        "scheme": _scheme,
        "code": _normalize(_scheme["scheme_name"]),
        "aliases": _aliases_for(_scheme),
        "title_tokens": _tokens(f"{_scheme.get('title', '')} {_details.get('tagline', '')}"),
        "all_tokens": _tokens(" ".join([
            str(_scheme.get("title", "")),
            str(_details.get("tagline", "")),
            str(_details.get("overview", "")),
            " ".join(map(str, _details.get("benefits") or [])),
        ])),
    })


def detect_schemes(question):
    """Return schemes the question names, best match first."""
    text = _normalize(question)
    tokens = _tokens(question)
    scored = []

    for entry in _SCHEME_INDEX:
        score = 0
        for alias in entry["aliases"]:
            if _contains(text, alias):
                bonus = 20 if alias == entry["code"] else 0
                score = max(score, 10 + bonus + len(alias))
        if not score:
            overlap = len(tokens & entry["title_tokens"])
            if overlap >= 2:
                score = overlap
        if score:
            scored.append((score, entry["scheme"]))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [scheme for _, scheme in scored]


def search_schemes(question, limit=3):
    """Loose full-text search used when no scheme is named."""
    tokens = {t for t in _tokens(question) if len(t) >= 4}
    if not tokens:
        return []
    scored = []
    for entry in _SCHEME_INDEX:
        overlap = len(tokens & entry["all_tokens"])
        if overlap:
            scored.append((overlap, entry["scheme"]))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [scheme for _, scheme in scored[:limit]]


def detect_intents(question):
    text = _normalize(question)
    intents = set()

    # "who can apply" / "can I apply" ask about eligibility, not the process.
    for phrase in ("who can apply", "can i apply", "eligible to apply", "who all can apply",
                   "कौन आवेदन कर सकता", "कौन आवेदन कर सकते"):
        phrase = _normalize(phrase)
        if _contains(text, phrase):
            intents.add("eligibility")
            text = text.replace(phrase, " ")

    for intent, phrases in _INTENT_PHRASES.items():
        if any(_contains(text, phrase) for phrase in phrases):
            intents.add(intent)
    return intents


# -------------------------------------------------------------------------
# Knowledge-base answers
# -------------------------------------------------------------------------


def _bullets(items, limit=8, numbered=False):
    lines = []
    for index, item in enumerate(list(items)[:limit], start=1):
        prefix = f"{index}." if numbered else "•"
        lines.append(f"{prefix} {item}")
    return "\n".join(lines)


def _profile_check_line(farmer, scheme, lang):
    result = check_eligibility(farmer, scheme, lang)
    if result["status"] == "eligible":
        line = _t(lang, "profile_ok", reasons="; ".join(result["reasons"]))
    elif result["status"] == "not_eligible":
        line = _t(lang, "profile_fail", failures="; ".join(result["failures"]))
    else:
        line = _t(lang, "profile_maybe", missing=result["missing_text"] or "; ".join(result["notes"]))
    if result["notes"] and result["status"] != "maybe":
        line += "\n" + _t(lang, "profile_note", notes="; ".join(result["notes"]))
    return line


def _scheme_name_words(scheme):
    name = scheme.get("scheme_name", "")
    names = [name, SHORT_NAMES.get(name, name), name.replace("-", "").replace("_", ""),
             scheme.get("title", "")]
    return {_stem(word) for text in names for word in _normalize(text).split()}


def _faq_answer(question, scheme):
    # Ignore the scheme's own name so "...for KCC?" doesn't count as a match.
    name_words = _scheme_name_words(scheme)
    question_tokens = _tokens(question) - name_words
    best, best_score = None, 0.0
    for faq in details_of(scheme).get("faqs") or []:
        if not isinstance(faq, dict):
            continue
        faq_tokens = _tokens(faq.get("question", "")) - name_words
        if not faq_tokens:
            continue
        shared = question_tokens & faq_tokens
        overlap = len(shared)
        ratio = overlap / len(faq_tokens)
        distinctive = shared - INTENT_WORDS - FOLLOW_UP_WORDS
        strong = (overlap >= 2 and ratio >= 0.6) or (distinctive and ratio >= 0.5)
        if strong and ratio > best_score:
            best, best_score = faq.get("answer"), ratio
    return best


def _section(intent, scheme, farmer, lang, include_profile=True):
    details = details_of(scheme)
    label = _label(scheme, lang)
    website = scheme.get("website")

    if intent == "overview":
        parts = [label]
        tagline = _tagline(scheme, lang)
        if tagline:
            parts.append(tagline)
        if lang != "hi" and details.get("overview"):
            parts.append("\n" + details["overview"])
        money = details.get("money_benefits")
        if isinstance(money, dict) and money:
            parts.append("\n💰 " + str(next(iter(money.values()))))
        if include_profile:
            parts.append("\n" + _profile_check_line(farmer, scheme, lang))
        return "\n".join(parts)

    if intent == "eligibility":
        rules = details.get("eligibility") or []
        text = _t(lang, "elig_header", label=label) + "\n"
        text += _bullets(rules) if rules else _t(lang, "elig_none")
        text += "\n\n" + _profile_check_line(farmer, scheme, lang)
        text += "\n" + _t(lang, "final_note")
        return text

    if intent == "benefits":
        lines = []
        money = details.get("money_benefits")
        if isinstance(money, dict):
            lines.extend(str(v) for v in money.values() if v)
        lines.extend(str(b) for b in details.get("benefits") or [])
        if not lines:
            return _t(lang, "benefits_none", label=label)
        return _t(lang, "benefits_header", label=label) + "\n" + _bullets(lines, limit=7)

    if intent == "documents":
        docs = details.get("documents_required") or []
        if not docs:
            return _t(lang, "docs_none", label=label)
        return _t(lang, "docs_header", label=label) + "\n" + _bullets(docs)

    if intent == "apply":
        steps = details.get("application_process") or []
        text = _t(lang, "apply_header", label=label) + "\n"
        text += _bullets(steps, numbered=True) if steps else _t(lang, "apply_none")
        if website:
            text += "\n\n" + _t(lang, "website_line", url=website)
        return text

    if intent == "dates":
        dates = details.get("important_dates") or _t(lang, "dates_none")
        return _t(lang, "dates_header", label=label) + "\n" + str(dates)

    if intent == "website":
        return _t(lang, "website_only", label=label, url=website or _t(lang, "not_listed"))

    return ""


def _profile_summary(farmer, lang):
    return _t(lang, "profile_fmt",
              age=farmer.get("age"),
              income=format_inr(farmer.get("income") or 0),
              land=f"{float(farmer.get('land_size') or 0):g}")


def _recommend_answer(farmer, eligible, maybe, lang):
    profile = _profile_summary(farmer, lang)
    if not eligible and not maybe:
        return _t(lang, "rec_none", profile=profile)

    lines = []
    for item in eligible:
        scheme = find_scheme(item.get("scheme_name")) or item
        lines.append(f"{short_name(scheme)} — {_tagline(scheme, lang) or item.get('title') or ''}")

    text = _t(lang, "rec_header", profile=profile, n=len(eligible), total=len(SCHEMES))
    if lines:
        text += "\n" + _bullets(lines, limit=len(lines))
    if maybe:
        names = ", ".join(short_name(find_scheme(m.get("scheme_name")) or m) for m in maybe)
        text += "\n\n" + _t(lang, "rec_maybe", n=len(maybe), names=names)
    first = (eligible or maybe)[0]
    text += "\n\n" + _t(lang, "rec_footer", name=short_name(find_scheme(first.get("scheme_name")) or first))
    return text


def _suggestions(scheme, covered, lang):
    if not scheme:
        return list(_t(lang, "defaults"))
    name = short_name(scheme)
    options = ["eligibility", "documents", "apply", "benefits", "dates"]
    return [_t(lang, f"sugg_{intent}", n=name) for intent in options if intent not in covered][:3]


def knowledge_base_answer(question, farmer, eligible=None, previous_scheme=None, lang="en", maybe=None):
    """Answer from schemes.json. Returns dict(answer, scheme, suggestions, context)."""
    eligible = eligible or []
    maybe = maybe or []
    first_name = (str(farmer.get("name") or "Farmer").split() or ["Farmer"])[0]
    intents = detect_intents(question)
    matches = detect_schemes(question)
    scheme = matches[0] if matches else None

    conversational = intents & {"greeting", "thanks"}
    content_intents = intents - {"greeting", "thanks", "recommend"}

    # Follow-up such as "How to apply?" — continue with the last scheme discussed,
    # unless the question brings up a new topic ("tell me about organic farming").
    if scheme is None and previous_scheme and content_intents and "recommend" not in intents:
        topic = {t for t in _tokens(question) if len(t) >= 4} - INTENT_WORDS - FOLLOW_UP_WORDS
        if not topic or not search_schemes(" ".join(topic)):
            scheme = find_scheme(previous_scheme)

    if scheme is None:
        if "recommend" in intents or "eligibility" in intents:
            suggestions = [_t(lang, "sugg_apply", n=short_name(find_scheme(e["scheme_name"]) or e))
                           for e in eligible[:3]]
            return {"answer": _recommend_answer(farmer, eligible, maybe, lang), "scheme": None,
                    "suggestions": suggestions or list(_t(lang, "defaults")), "context": []}
        if "thanks" in conversational:
            return {"answer": _t(lang, "thanks", name=first_name), "scheme": None,
                    "suggestions": list(_t(lang, "defaults")), "context": []}
        if "greeting" in conversational and not content_intents:
            return {"answer": _t(lang, "greeting", name=first_name), "scheme": None,
                    "suggestions": list(_t(lang, "defaults")), "context": []}
        related = search_schemes(question)
        if related:
            names = ", ".join(f"{short_name(s)} ({_title(s, lang)})" for s in related)
            text = _t(lang, "related_found", names=names, first=short_name(related[0]))
            suggestions = [_t(lang, "sugg_what", n=short_name(s)) for s in related]
        else:
            known = ", ".join(short_name(s) for s in SCHEMES)
            text = _t(lang, "no_match", name=first_name, known=known)
            suggestions = list(_t(lang, "defaults"))
        return {"answer": text, "scheme": None, "suggestions": suggestions, "context": related}

    sections = [i for i in SECTION_ORDER if i in content_intents]
    if not sections:
        sections = ["overview"]
    elif sections == ["benefits"] and "overview" in intents:
        sections = ["overview", "benefits"]

    parts = []
    faq = _faq_answer(question, scheme)
    if faq:
        parts.append(f"💡 {faq}")
    profile_in_overview = "eligibility" not in sections
    parts.extend(_section(intent, scheme, farmer, lang, profile_in_overview) for intent in sections)

    other = [s for s in matches[1:3] if s is not scheme]
    if other and sections == ["overview"]:
        parts.append(_t(lang, "related", items=", ".join(f"{short_name(s)} ({_title(s, lang)})" for s in other)))

    if lang == "hi" and (faq or set(sections) - {"overview", "website"}):
        parts.append(_t(lang, "english_note"))

    return {
        "answer": "\n\n".join(p for p in parts if p),
        "scheme": scheme.get("scheme_name"),
        "suggestions": _suggestions(scheme, set(sections), lang),
        "context": [scheme] + other,
    }


# -------------------------------------------------------------------------
# Optional Ollama layer
# -------------------------------------------------------------------------

_llm_state = {"checked_at": 0.0, "available": False}


def llm_enabled():
    return LLM_MODE not in {"off", "false", "0", "no", "none", "disabled"}


def llm_available(max_age_seconds=30):
    """True when Ollama is reachable and has the configured model pulled."""
    if not llm_enabled():
        return False

    now = time.monotonic()
    if now - _llm_state["checked_at"] < max_age_seconds:
        return _llm_state["available"]

    available = False
    try:
        with _ollama_opener.open(f"{OLLAMA_URL}/api/tags", timeout=1.5) as response:
            tags = json.load(response)
        names = {str(m.get("name", "")) for m in tags.get("models", []) if isinstance(m, dict)}
        available = any(n == OLLAMA_MODEL or n.split(":")[0] == OLLAMA_MODEL for n in names)
    except (urllib.error.URLError, OSError, ValueError, AttributeError):
        available = False

    _llm_state.update(checked_at=now, available=available)
    return available


def _scheme_context(scheme):
    details = details_of(scheme)
    lines = [f"Scheme: {scheme.get('title')} ({scheme.get('scheme_name')})",
             f"Website: {scheme.get('website')}"]
    if scheme.get("title_hi"):
        lines.append(f"Hindi name: {scheme['title_hi']}")
    for key in ("tagline", "overview", "implemented_by", "important_dates"):
        if details.get(key):
            lines.append(f"{key.replace('_', ' ').title()}: {details[key]}")
    for key in ("eligibility", "benefits", "documents_required", "application_process"):
        values = details.get(key) or []
        if values:
            lines.append(f"{key.replace('_', ' ').title()}:")
            lines.extend(f"- {v}" for v in values)
    money = details.get("money_benefits")
    if isinstance(money, dict) and money:
        lines.append("Financial support:")
        lines.extend(f"- {v}" for v in money.values())
    for limit in ("age_limit", "income_limit", "land_limit"):
        if details.get(limit):
            lines.append(f"{limit.replace('_', ' ').title()}: {details[limit]}")
    for faq in details.get("faqs") or []:
        if isinstance(faq, dict):
            lines.append(f"FAQ: {faq.get('question')} — {faq.get('answer')}")
    return "\n".join(lines)


def _build_prompt(question, farmer, eligible, context_schemes, history, lang):
    eligible_names = ", ".join(e.get("scheme_name", "") for e in eligible) or "none found"
    context = "\n\n".join(_scheme_context(s) for s in context_schemes)
    checks = "\n".join(
        f"- {s.get('scheme_name')}: {_profile_check_line(farmer, s, 'en')}" for s in context_schemes
    )
    conversation = "\n".join(
        f"Farmer: {turn['question']}\nAssistant: {turn['answer'][:400]}"
        for turn in (history or [])[-3:]
    ) or "(none)"

    return f"""You are Jeevandhara AI, a friendly assistant that helps Indian farmers understand government schemes.

Rules:
- Use ONLY the scheme information below. If it does not contain the answer, say you don't have that information and point to the official website.
- Keep the answer short (under 150 words), simple and farmer friendly. Use short bullet points for lists.
- Never invent amounts, dates, documents or websites.
- {_t(lang, "llm_language")}

Farmer profile: name {farmer.get('name')}, age {farmer.get('age')}, annual income {format_inr(farmer.get('income') or 0)}, land {farmer.get('land_size')} acres, {farmer.get('district')}, {farmer.get('state')}.
Schemes this farmer matches: {eligible_names}
Eligibility check for the schemes below:
{checks}

Scheme information:
{context}

Recent conversation:
{conversation}

Farmer's question: {question}
Answer:"""


def ask_llm(prompt):
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with _ollama_opener.open(request, timeout=OLLAMA_TIMEOUT) as response:
        data = json.load(response)
    text = str(data.get("response") or "").strip()
    if not text:
        raise ValueError("Ollama returned an empty answer")
    return text


def reply_language(question, lang=None):
    """Hindi if the question is in Devanagari or the website is set to Hindi."""
    if has_devanagari(question):
        return "hi"
    return "hi" if lang == "hi" else "en"


def answer(question, farmer, eligible=None, previous_scheme=None, history=None, lang=None, maybe=None):
    """Main entry point used by the API.

    Returns ``{"answer", "scheme", "suggestions", "source", "lang"}`` where
    source is ``"ollama"`` or ``"knowledge_base"``.
    """
    reply_lang = reply_language(question, lang)
    result = knowledge_base_answer(question, farmer, eligible, previous_scheme, reply_lang, maybe)
    context = result.pop("context", [])
    result["source"] = "knowledge_base"
    result["lang"] = reply_lang

    # Only hand questions with real scheme context to the LLM; greetings and
    # the eligible-schemes list are already exact from the knowledge base.
    if context and llm_available():
        try:
            prompt = _build_prompt(question, farmer, eligible or [], context[:2], history, reply_lang)
            result["answer"] = ask_llm(prompt)
            result["source"] = "ollama"
        except Exception:
            _llm_state.update(checked_at=time.monotonic(), available=False)

    return result
