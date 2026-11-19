"""Chatbot: scheme/intent detection in English, Hindi and Hinglish, follow-ups,
Hindi replies, and the optional Ollama layer (with a fake Ollama server)."""

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import chatbot
from recommender import recommend_for

DEVANAGARI = re.compile(r"[ऀ-ॿ]")

FARMER = {
    "name": "Ravi Kumar", "age": 35, "income": 80000, "land_size": 2.0, "state": "Bihar", "district": "Patna",
    "land_ownership": "owner", "income_tax_payer": False, "govt_employee": False,
    "social_security": False, "has_bank_account": True, "social_category": "general", "gender": "male",
}


def ask(question, **kwargs):
    groups = recommend_for(FARMER, chatbot.reply_language(question, kwargs.get("lang")))
    return chatbot.answer(question, FARMER, eligible=groups["eligible"], maybe=groups["maybe"], **kwargs)


@pytest.mark.parametrize("question, scheme", [
    ("What is KCC?", "KCC"),
    ("tell me about kisan credit card", "KCC"),
    ("crop insurance premium", "PMFBY"),
    ("How do I get PM-KISAN money", "PM-KISAN"),
    ("can i buy a tractor with subsidy", "SNAM"),
    ("sell my crops online on enam", "eNAM"),
    ("किसान क्रेडिट कार्ड क्या है?", "KCC"),
    ("फसल बीमा के लिए दस्तावेज़", "PMFBY"),
    ("पीएम किसान की किस्त कब आएगी", "PM-KISAN"),
    ("अटल पेंशन योजना", "APY"),
    ("जैविक खेती का प्रमाणन", "PGS_India_NCOF"),
    ("pm kisan ke liye kaise apply kare", "PM-KISAN"),
])
def test_detect_scheme(question, scheme):
    matches = chatbot.detect_schemes(question)
    assert matches and matches[0]["scheme_name"] == scheme


@pytest.mark.parametrize("question, intent", [
    ("Who is eligible for KCC?", "eligibility"),
    ("documents needed", "documents"),
    ("how to apply", "apply"),
    ("what is the subsidy amount", "benefits"),
    ("last date to apply", "dates"),
    ("क्या मैं पात्र हूँ", "eligibility"),
    ("कौन से दस्तावेज़ चाहिए", "documents"),
    ("आवेदन कैसे करें", "apply"),
    ("कितना पैसा मिलेगा", "benefits"),
    ("अंतिम तिथि क्या है", "dates"),
    ("kagaz kya chahiye", "documents"),
    ("नमस्ते", "greeting"),
])
def test_detect_intent(question, intent):
    assert intent in chatbot.detect_intents(question)


def test_who_can_apply_means_eligibility_not_process():
    intents = chatbot.detect_intents("What is KCC and who can apply?")
    assert "eligibility" in intents and "apply" not in intents


def test_english_answer_with_profile_check():
    result = ask("Am I eligible for KCC?")
    assert result["scheme"] == "KCC"
    assert result["lang"] == "en"
    assert "✅ Your profile" in result["answer"]
    assert result["source"] == "knowledge_base"
    assert result["suggestions"]


def test_hindi_question_gets_hindi_answer():
    result = ask("किसान क्रेडिट कार्ड के लिए आवेदन कैसे करें?")
    assert result["lang"] == "hi"
    assert result["scheme"] == "KCC"
    assert "आवेदन कैसे करें" in result["answer"]
    assert all(DEVANAGARI.search(s) for s in result["suggestions"])


def test_hindi_website_setting_answers_in_hindi():
    result = ask("What is PMFBY?", lang="hi")
    assert result["lang"] == "hi"
    assert "प्रधानमंत्री फसल बीमा योजना" in result["answer"]


def test_follow_up_uses_previous_scheme():
    result = ask("Documents required?", previous_scheme="KCC")
    assert result["scheme"] == "KCC"
    assert "Documents needed for Kisan Credit Card" in result["answer"]

    hindi = ask("आवेदन कैसे करें?", previous_scheme="PMFBY")
    assert hindi["scheme"] == "PMFBY"


def test_new_topic_is_not_treated_as_follow_up():
    result = ask("tell me about organic farming", previous_scheme="KCC")
    assert result["scheme"] == "PGS_India_NCOF"


def test_faq_answer_is_used():
    result = ask("Is eKYC mandatory for PM-KISAN?")
    assert result["answer"].startswith("💡 Yes, eKYC is mandatory")


def test_recommendation_list():
    result = ask("Which schemes am I eligible for?")
    assert result["scheme"] is None
    assert "you are eligible for" in result["answer"]

    hindi = ask("मैं किन योजनाओं के लिए पात्र हूँ?")
    assert "योजनाओं के पात्र हैं" in hindi["answer"]


def test_greeting_and_unknown():
    assert "Namaste Ravi" in ask("hello")["answer"]
    assert "नमस्ते Ravi जी" in ask("नमस्ते")["answer"]
    unknown = ask("qwerty asdf")
    assert unknown["scheme"] is None
    assert "PM-KISAN" in unknown["answer"]


# --- optional Ollama layer -----------------------------------------------------

class _FakeOllama(BaseHTTPRequestHandler):
    fail = False
    last_prompt = ""

    def log_message(self, *args):
        pass

    def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, {"models": [{"name": "mistral:latest"}]})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        request = json.loads(self.rfile.read(length))
        type(self).last_prompt = request["prompt"]
        if type(self).fail:
            self._send(500, {"error": "boom"})
        else:
            self._send(200, {"response": "FAKE MISTRAL ANSWER"})


@pytest.fixture
def fake_ollama(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _FakeOllama)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _FakeOllama.fail = False
    monkeypatch.setattr(chatbot, "OLLAMA_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setattr(chatbot, "LLM_MODE", "auto")
    chatbot._llm_state.update(checked_at=0.0, available=False)
    yield _FakeOllama
    server.shutdown()
    chatbot._llm_state.update(checked_at=0.0, available=False)


def test_uses_ollama_when_available(fake_ollama):
    result = ask("What is KCC?")
    assert result["source"] == "ollama"
    assert result["answer"] == "FAKE MISTRAL ANSWER"
    assert "Scheme: Kisan Credit Card (KCC)" in fake_ollama.last_prompt
    assert "Reply in simple English" in fake_ollama.last_prompt


def test_ollama_prompt_asks_for_hindi(fake_ollama):
    ask("किसान क्रेडिट कार्ड क्या है?")
    assert "Hindi" in fake_ollama.last_prompt


def test_falls_back_when_ollama_fails(fake_ollama):
    fake_ollama.fail = True
    result = ask("What is KCC?")
    assert result["source"] == "knowledge_base"
    assert "Kisan Credit Card (KCC)" in result["answer"]


def test_greetings_never_go_to_ollama(fake_ollama):
    fake_ollama.last_prompt = ""
    assert ask("hello")["source"] == "knowledge_base"
    assert fake_ollama.last_prompt == ""


def test_llm_off_by_setting(monkeypatch):
    monkeypatch.setattr(chatbot, "LLM_MODE", "off")
    assert chatbot.llm_available() is False
