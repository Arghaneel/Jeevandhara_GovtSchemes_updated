"""End-to-end browser tests (Playwright + Chromium).

Skipped automatically when Playwright or its browser isn't installed. To run:
    pip install -r requirements-dev.txt
    python -m playwright install chromium
    pytest -m e2e
"""

import re
import time

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
expect = sync_api.expect

pytestmark = pytest.mark.e2e

IGNORED_CONSOLE = ("fonts.googleapis", "fonts.gstatic", "unsplash", "ERR_TUNNEL", "ERR_NAME_NOT_RESOLVED",
                   "ERR_INTERNET_DISCONNECTED", "ERR_CONNECTION", "status of 401", "status of 404")


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Exception as error:  # browser binary not installed
            pytest.skip(f"Chromium not available: {error}")
        yield browser
        browser.close()


@pytest.fixture
def page(browser, server):
    context = browser.new_context(viewport={"width": 1366, "height": 900}, base_url=f"{server}/app/")
    page = context.new_page()
    page.errors = []
    page.on("pageerror", lambda error: page.errors.append(str(error)))
    page.on("console", lambda msg: page.errors.append(msg.text)
            if msg.type == "error" and not any(s in msg.text for s in IGNORED_CONSOLE) else None)
    yield page
    context.close()


def register_and_login(page, username, **answers):
    page.goto("register.html")
    page.fill("#username", username)
    page.fill("#password", "pass1234")
    page.fill("#name", "Kamla Devi")
    page.fill("#age", "34")
    page.fill("#income", "80000")
    page.fill("#land_size", "2.5")
    page.fill("#state", "Rajasthan")
    page.fill("#district", "Jaipur")
    for field, value in answers.items():
        page.select_option(f"#reg-{field}", value)
    page.click("#submit-btn")
    page.wait_for_url(re.compile(r"login\.html$"), timeout=10000)
    expect(page.locator("#username")).to_have_value(username)
    page.fill("#password", "pass1234")
    page.click("#submit-btn")
    page.wait_for_url(re.compile(r"dashboard\.html$"), timeout=10000)
    expect(page.locator("#scheme-list .scheme-row").first).to_be_visible()


def test_landing_page_links(page):
    page.goto("index.html")
    for anchor in ("about", "contact", "help", "privacy"):
        page.goto("index.html")
        page.click(f"a[href='help.html#{anchor}']")
        expect(page).to_have_url(re.compile(rf"help\.html#{anchor}$"))
        expect(page.locator(f"section#{anchor}")).to_be_visible()

    # Quick check works without an account, and carries over to registration.
    page.goto("index.html")
    page.fill("#qc-age", "34")
    page.fill("#qc-land", "2.5")
    page.fill("#qc-income", "80000")
    expect(page.locator(".qc-row")).to_have_count(3)
    expect(page.locator(".qc-row .stamp--eligible")).to_be_visible()
    page.click("#qc-result a.btn-primary")
    page.wait_for_url(re.compile(r"register\.html$"))
    expect(page.locator("#age")).to_have_value("34")
    expect(page.locator("#land_size")).to_have_value("2.5")

    page.goto("dashboard.html")
    page.wait_for_url(re.compile(r"login\.html$"))
    assert page.errors == []


def test_full_farmer_journey(page):
    username = f"kamla{int(time.time() * 1000)}"
    register_and_login(page, username, land_ownership="owner", has_bank_account="true", gender="female")

    # Some schemes need more answers -> "Check" tab and a completion prompt.
    expect(page.locator("#profile-complete-banner")).to_be_visible()
    page.click("#tab-maybe")
    expect(page.locator("#tab-maybe")).to_have_attribute("aria-selected", "true")
    expect(page.locator("#scheme-list .scheme-row .stamp--maybe").first).to_be_visible()

    # Answer everything in Edit Profile -> no more prompt.
    page.click("#profile-complete-banner button")
    expect(page.locator("#profile-modal")).to_be_visible()
    for field in ("income_tax_payer", "govt_employee", "social_security"):
        page.select_option(f"#edit-{field}", "false")
    page.select_option("#edit-social_category", "general")
    page.click("#profile-save-btn")
    expect(page.locator("#profile-modal")).to_be_hidden()
    expect(page.locator("#profile-complete-banner")).to_be_hidden()

    # Save KCC and track it.
    page.click("#tab-all")
    card = page.locator("#scheme-list .scheme-row", has_text="Kisan Credit Card")
    expect(card.locator(".stamp--eligible")).to_be_visible()
    card.locator(".save-star").click()
    expect(page.locator(".saved-item")).to_have_count(1)
    expect(page.locator("#stat-saved-count")).to_have_text("1")

    # Document checklist on the scheme page.
    page.locator(".saved-item a.btn-small").click()
    page.wait_for_url(re.compile(r"scheme\.html\?id=KCC#documents$"))
    expect(page.locator(".elig-status")).to_contain_text("you can apply")
    expect(page.locator("#eligibility-body .stamp--eligible")).to_be_visible()
    boxes = page.locator(".doc-check input")
    expect(boxes).to_have_count(6)
    boxes.nth(0).check()
    expect(page.locator("#docs-progress-text")).to_have_text("1 of 6 ready")
    expect(page.locator("#scheme-status-select")).to_have_value("collecting")
    page.select_option("#scheme-status-select", "applied")
    page.reload()
    expect(page.locator(".doc-check input").nth(0)).to_be_checked()
    expect(page.locator("#scheme-status-select")).to_have_value("applied")

    # Ask AI from the scheme page opens the chat with the question.
    page.click("#ask-ai-link")
    page.wait_for_url(re.compile(r"dashboard\.html"))
    expect(page.locator(".message-bubble.bot").last).to_contain_text("Kisan Credit Card (KCC)", timeout=10000)
    page.locator(".chat-chip", has_text="Documents").click()
    expect(page.locator(".message-bubble.bot").last).to_contain_text("Documents needed", timeout=10000)

    # Switch to Hindi: page text, scheme names and chat all change.
    page.click("#chat-close-btn")
    page.click("#lang-btn")
    expect(page.locator("html")).to_have_attribute("lang", "hi")
    expect(page.locator("[data-i18n='saved.title']")).to_have_text("मेरे आवेदन")
    expect(page.locator("#tab-eligible")).to_contain_text("पात्र")
    expect(page.locator(".saved-item .status-select")).to_have_value("applied")
    expect(page.locator(".saved-title").first).to_have_text("किसान क्रेडिट कार्ड")
    page.click("#chatbot-collapsed")
    page.fill("#chatbot-input-field", "फसल बीमा क्या है?")
    page.press("#chatbot-input-field", "Enter")
    expect(page.locator(".message-bubble.bot").last).to_contain_text("प्रधानमंत्री फसल बीमा योजना", timeout=10000)
    page.click("#chat-close-btn")

    # Language choice survives a reload; switch back.
    page.reload()
    expect(page.locator("#lang-btn .lang-long")).to_have_text("English")
    page.click("#lang-btn")
    expect(page.locator("#lang-btn .lang-long")).to_have_text("हिंदी")

    # Remove the saved scheme, then log out.
    page.locator(".saved-item .btn-link-danger").click()
    expect(page.locator(".saved-item")).to_have_count(0)
    page.click("text=Log out")
    page.wait_for_url(re.compile(r"index\.html$"))

    assert page.errors == []


def test_scheme_page_when_logged_out(page):
    page.goto("scheme.html?id=PMFBY")
    expect(page.locator("#scheme-title")).to_have_text("Pradhan Mantri Fasal Bima Yojana")
    expect(page.locator(".nav-home-link")).to_have_text("Home")
    expect(page.locator("#eligibility-body")).to_contain_text("Log in")
    expect(page.locator("#save-scheme-btn")).to_be_hidden()

    page.goto("scheme.html?id=NOPE")
    expect(page.locator(".scheme-detail-container")).to_contain_text("was not found")


def test_dashboard_tabs_and_search(page):
    username = f"ravi{int(time.time() * 1000)}"
    register_and_login(page, username, land_ownership="tenant", income_tax_payer="true")

    counts = {f: int(page.inner_text(f"#count-{f}")) for f in ("eligible", "maybe", "not_eligible", "all")}
    assert counts["eligible"] + counts["maybe"] + counts["not_eligible"] == counts["all"] == 17
    assert counts["not_eligible"] >= 1  # tenant + tax payer rules out PM-KISAN

    page.click("#tab-not_eligible")
    row = page.locator("#scheme-list .scheme-row", has_text="Pradhan Mantri Kisan Samman Nidhi")
    expect(row.locator(".scheme-reason")).to_contain_text("registered in your name")
    expect(page.locator("#scheme-list .scheme-row")).to_have_count(counts["not_eligible"])

    page.click("#tab-all")
    page.fill("#search-schemes-input", "pension")
    names = page.locator("#scheme-list .scheme-row .row-link").all_inner_texts()
    assert "Atal Pension Yojana" in names and "Pradhan Mantri Kisan Maandhan Yojana" in names
    assert len(names) < 17

    page.fill("#search-schemes-input", "zzzz")
    expect(page.locator(".list-empty-state")).to_be_visible()

    # Keyboard: arrow keys move between tabs.
    page.fill("#search-schemes-input", "")
    page.focus("#tab-all")
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#tab-not_eligible")).to_have_attribute("aria-selected", "true")
    assert page.errors == []
