// Scheme details page (scheme.html?id=<scheme_name>).
// The status column shows the farmer's stamp (eligible / check / not eligible),
// the reasons, saving and application status, document progress and the
// assistant. Shared helpers come from common.js and i18n.js.

const STATUSES = ["interested", "collecting", "applied", "approved", "rejected"];

let currentScheme = null;
let currentSaved = null;
let currentStatus = null;
let busy = false;

document.addEventListener("DOMContentLoaded", () => {
    setupNavigation();
    loadSchemeDetails();
});

document.addEventListener("languagechange", () => {
    setupNavigation();
    if (currentScheme) {
        renderScheme(currentScheme);
        loadEligibility(false);
    } else {
        loadSchemeDetails();
    }
});

function schemeId() {
    return new URLSearchParams(window.location.search).get("id");
}

// Logged-in farmers go back to the dashboard; visitors go home.
function setupNavigation() {
    const loggedIn = Boolean(Session.userId);
    document.getElementById("brand-link").href = loggedIn ? "dashboard.html" : "index.html";
    document.querySelectorAll(".nav-home-link").forEach((link) => {
        link.href = loggedIn ? "dashboard.html" : "index.html";
        link.textContent = loggedIn ? t("nav.dashboard") : t("nav.home");
    });
    document.querySelectorAll(".nav-back-link").forEach((link) => {
        link.href = loggedIn ? "dashboard.html" : "index.html";
        link.querySelector(".back-text").textContent = loggedIn ? t("nav.back_dashboard") : t("nav.back_home");
    });
}

async function fetchScheme(id) {
    try {
        return await apiRequest(`/schemes/${encodeURIComponent(id)}`);
    } catch (error) {
        if (error.status === 404) return null;

        // Backend unreachable: fall back to the bundled copy of the data.
        const response = await fetch("schemes.json");
        if (!response.ok) throw error;
        const schemes = await response.json();
        return schemes.find((s) => String(s.scheme_name).toLowerCase() === id.toLowerCase()) || null;
    }
}

async function loadSchemeDetails() {
    const id = schemeId();
    if (!id) {
        renderErrorState(t("scheme.error_none"));
        return;
    }

    let scheme;
    try {
        scheme = await fetchScheme(id);
    } catch (error) {
        console.error("Error loading scheme details:", error);
        renderErrorState(t("scheme.error_load", { message: error.message || "" }));
        return;
    }

    if (!scheme) {
        renderErrorState(t("scheme.error_not_found", { id }));
        return;
    }

    currentScheme = scheme;
    renderScheme(scheme);
    await loadEligibility(true);

    if (window.location.hash === "#documents") {
        document.getElementById("documents").scrollIntoView({ block: "start" });
    }
}

// -------------------------------------------------------------------------
// Scheme content
// -------------------------------------------------------------------------

function fillList(listId, items, emptyText) {
    const list = document.getElementById(listId);
    list.innerHTML = "";

    const values = Array.isArray(items) ? items : items ? [items] : [];
    if (values.length === 0) {
        const li = document.createElement("li");
        li.className = "list-empty";
        li.textContent = emptyText;
        list.appendChild(li);
        return;
    }

    values.forEach((item) => {
        const li = document.createElement("li");
        li.textContent = item;
        list.appendChild(li);
    });
}

function addChip(container, text) {
    const chip = document.createElement("span");
    chip.className = "eligibility-badge";
    chip.textContent = text;
    container.appendChild(chip);
}

function renderScheme(scheme) {
    const details = scheme.scheme_details || {};
    const title = localized(scheme, "title") || scheme.scheme_name;

    document.title = `${title} - Jeevandhara`;
    document.getElementById("scheme-hero-icon").innerHTML = schemeIcon(scheme.scheme_name, 32);
    document.getElementById("scheme-title").textContent = title;
    document.getElementById("scheme-tagline").textContent = localized(scheme, "tagline") || t("scheme.default_tagline");
    document.getElementById("scheme-year").textContent = details.launch_year || "-";
    document.getElementById("scheme-implementor").textContent = details.implemented_by || "-";
    document.getElementById("scheme-dept").textContent = details.department || t("scheme.default_dept");

    const webLink = document.getElementById("scheme-web-link");
    if (scheme.website) webLink.href = scheme.website;
    else webLink.hidden = true;

    // Hindi readers: say that the long text below is still English.
    const note = document.getElementById("english-note");
    const noteText = t("scheme.english_note");
    note.innerHTML = noteText ? `${icon("info", 18)}<span>${escapeHTML(noteText)}</span>` : "";
    note.hidden = !noteText;

    document.getElementById("scheme-overview").textContent = details.overview || t("scheme.no_overview");

    // Money box
    const moneyContainer = document.getElementById("scheme-benefits-money");
    moneyContainer.innerHTML = "";
    const money = details.money_benefits;
    if (money && typeof money === "object" && Object.keys(money).length > 0) {
        const box = document.createElement("div");
        box.className = "money-benefits-box";

        const heading = document.createElement("h3");
        heading.textContent = t("scheme.money");
        box.appendChild(heading);

        const list = document.createElement("ul");
        Object.entries(money).forEach(([key, value]) => {
            const li = document.createElement("li");
            const label = document.createElement("strong");
            label.textContent = `${key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())}: `;
            li.append(label, String(value));
            list.appendChild(li);
        });
        box.appendChild(list);
        moneyContainer.appendChild(box);
    }

    fillList("scheme-benefits-list", details.benefits, t("scheme.no_benefits"));

    // Limits as chips
    const chips = document.getElementById("scheme-eligibility-limits");
    chips.innerHTML = "";

    if (details.age_limit && typeof details.age_limit === "object") {
        const min = details.age_limit.minimum_age;
        const max = details.age_limit.maximum_age;
        let text = t("scheme.age_all");
        if (min && max) text = t("scheme.age_range", { min, max });
        else if (min) text = t("scheme.age_min", { min });
        else if (max) text = t("scheme.age_max", { max });
        addChip(chips, t("scheme.age_badge", { text }));
    }

    if (details.land_limit) {
        const text =
            typeof details.land_limit === "object"
                ? details.land_limit.maximum_land_holding || details.land_limit.category || t("scheme.restricted")
                : details.land_limit;
        addChip(chips, t("scheme.land_badge", { text }));
    }

    if (details.income_limit) {
        let text = details.income_limit;
        if (typeof details.income_limit === "object") {
            text = details.income_limit.amount
                ? t("scheme.income_max", { amount: formatRupees(details.income_limit.amount) })
                : t("scheme.restricted");
        }
        addChip(chips, t("scheme.income_badge", { text }));
    }
    chips.hidden = !chips.children.length;

    fillList("scheme-eligibility-list", details.eligibility, t("scheme.no_eligibility"));
    renderDocuments();
    fillList("scheme-process-list", details.application_process, t("scheme.no_process"));

    document.getElementById("scheme-dates").textContent = details.important_dates || t("scheme.no_dates");

    renderFaqs(scheme, details);
}

function documentsOf(scheme) {
    const details = (scheme && scheme.scheme_details) || {};
    return Array.isArray(details.documents_required) ? details.documents_required : [];
}

function renderDocuments() {
    const docs = documentsOf(currentScheme);
    const list = document.getElementById("scheme-documents-list");
    const loggedIn = Boolean(Session.userId);
    const done = new Set((currentSaved && currentSaved.documents_done) || []);

    list.innerHTML = "";
    list.classList.toggle("is-checklist", loggedIn && docs.length > 0);

    if (docs.length === 0) {
        fillList("scheme-documents-list", [], t("scheme.no_docs"));
    } else if (!loggedIn) {
        fillList("scheme-documents-list", docs, "");
    } else {
        docs.forEach((doc, index) => {
            const li = document.createElement("li");
            li.className = done.has(index) ? "doc-done" : "";

            const label = document.createElement("label");
            label.className = "doc-check";

            const box = document.createElement("input");
            box.type = "checkbox";
            box.checked = done.has(index);
            box.dataset.index = String(index);
            box.addEventListener("change", () => toggleDocument(index, box));

            const text = document.createElement("span");
            text.textContent = doc;

            label.append(box, text);
            li.appendChild(label);
            list.appendChild(li);
        });
    }

    const showProgress = loggedIn && docs.length > 0;
    const progressLabel = t("scheme.docs_progress", { done: done.size, total: docs.length });
    const percent = docs.length ? Math.round((done.size / docs.length) * 100) : 0;

    document.getElementById("docs-hint").hidden = !showProgress;
    document.getElementById("docs-progress").hidden = !showProgress;
    const progressText = document.getElementById("docs-progress-text");
    progressText.hidden = !showProgress;
    progressText.textContent = progressLabel;
    document.getElementById("docs-progress-bar").style.width = `${percent}%`;

    // Mirror the progress in the status column.
    const asideDocs = document.getElementById("aside-docs");
    asideDocs.hidden = !showProgress;
    document.getElementById("aside-docs-text").textContent = t("saved.docs", { done: done.size, total: docs.length });
    document.getElementById("aside-docs-bar").style.width = `${percent}%`;
}

function renderFaqs(scheme, details) {
    const faqContainer = document.getElementById("scheme-faq-container");
    faqContainer.innerHTML = "";

    const faqs =
        Array.isArray(details.faqs) && details.faqs.length
            ? details.faqs
            : [
                  {
                      question: t("scheme.faq1_q"),
                      answer: t("scheme.faq1_a", { site: scheme.website || t("scheme.official_portal") }),
                  },
                  {
                      question: t("scheme.faq2_q"),
                      answer: t("scheme.faq2_a", { by: details.implemented_by || t("scheme.central_govt") }),
                  },
              ];

    faqs.forEach((item, index) => {
        const faqItem = document.createElement("div");
        faqItem.className = "faq-item";
        faqItem.innerHTML = `
            <button type="button" class="faq-question-btn" onclick="toggleFaq(${index})" aria-expanded="false" aria-controls="faq-answer-${index}">
                <span>${escapeHTML(item.question)}</span>
                <span class="faq-chevron" aria-hidden="true"></span>
            </button>
            <div class="faq-answer-panel" id="faq-answer-${index}">
                <p>${escapeHTML(item.answer)}</p>
            </div>
        `;
        faqContainer.appendChild(faqItem);
    });
}

function toggleFaq(index) {
    const faqItems = document.querySelectorAll(".faq-item");
    const target = faqItems[index];
    if (!target) return;

    const wasActive = target.classList.contains("active");
    faqItems.forEach((item) => {
        item.classList.remove("active");
        const button = item.querySelector(".faq-question-btn");
        if (button) button.setAttribute("aria-expanded", "false");
    });

    if (!wasActive) {
        target.classList.add("active");
        const button = target.querySelector(".faq-question-btn");
        if (button) button.setAttribute("aria-expanded", "true");
    }
}

// -------------------------------------------------------------------------
// Status column (logged-in farmers)
// -------------------------------------------------------------------------

async function loadEligibility(animate) {
    const body = document.getElementById("eligibility-body");

    if (!Session.userId) {
        currentSaved = null;
        body.innerHTML = `
            <p class="muted">${escapeHTML(t("scheme.login_to_check"))}</p>
            <a href="login.html" class="btn btn-primary btn-block" style="margin-top: 14px;">${escapeHTML(t("nav.login"))}</a>
        `;
        renderActions();
        renderDocuments();
        return;
    }

    try {
        const result = await apiRequest(
            `/eligibility/${encodeURIComponent(Session.userId)}/${encodeURIComponent(currentScheme.scheme_name)}?lang=${currentLang()}`
        );
        currentSaved = result.saved;
        renderEligibility(result, animate);
    } catch (error) {
        if (error.status === 404 && error.data && error.data.message === "Farmer not found") {
            Session.clear();
            setupNavigation();
            return loadEligibility(false);
        }
        body.innerHTML = `<p class="muted">${escapeHTML(error.message)}</p>`;
    }

    renderActions();
    renderDocuments();
}

function reasonItem(kind, text) {
    const iconName = { ok: "check", fail: "cross", note: "info" }[kind];
    return `<li class="elig-${kind}">${icon(iconName, 16, 2.2)}<span>${escapeHTML(text)}</span></li>`;
}

function renderEligibility(result, animate) {
    currentStatus = result.status;
    const body = document.getElementById("eligibility-body");
    const items = [
        ...(result.reasons || []).map((text) => reasonItem("ok", text)),
        ...(result.failures || []).map((text) => reasonItem("fail", text)),
        ...(result.notes || []).map((text) => reasonItem("note", text)),
    ].join("");

    body.innerHTML = `
        ${stampHTML(result.status, `stamp--lg ${animate ? "stamp--press" : ""}`)}
        <p class="status-summary elig-status">${escapeHTML(t(`scheme.status_${result.status}`))}</p>
        ${items ? `<ul class="elig-list">${items}</ul>` : ""}
        ${result.missing_text ? `
            <div class="elig-missing">
                <span>${escapeHTML(result.missing_text)}</span>
                <a href="dashboard.html?edit=1" class="btn btn-haldi btn-sm">${escapeHTML(t("scheme.answer_questions"))}</a>
            </div>` : ""}
        <p class="small-note">${escapeHTML(t("scheme.final_note"))}</p>
    `;
}

function renderActions() {
    const loggedIn = Boolean(Session.userId) && currentScheme;
    const actions = document.getElementById("aside-actions");
    const saveBtn = document.getElementById("save-scheme-btn");
    const statusSelect = document.getElementById("scheme-status-select");
    const askLink = document.getElementById("ask-ai-link");

    actions.hidden = !loggedIn;
    askLink.hidden = !loggedIn;
    statusSelect.hidden = !(loggedIn && currentSaved);
    if (!loggedIn) return;

    const saved = Boolean(currentSaved);
    saveBtn.innerHTML = `${icon("star", 18)}<span>${escapeHTML(saved ? t("saved.saved") : t("saved.save"))}</span>`;
    saveBtn.classList.toggle("is-saved", saved);
    saveBtn.setAttribute("aria-pressed", String(saved));
    saveBtn.onclick = toggleSave;

    if (saved) {
        statusSelect.innerHTML = STATUSES.map(
            (s) => `<option value="${s}" ${s === currentSaved.status ? "selected" : ""}>${escapeHTML(t(`status.${s}`))}</option>`
        ).join("");
        statusSelect.className = `status-select status-${currentSaved.status}`;
        statusSelect.setAttribute("aria-label", t("saved.status_label"));
        statusSelect.onchange = () => updateSaved({ status: statusSelect.value });
    }

    askLink.href = `dashboard.html?ask=${encodeURIComponent(t("chat.ask_about", { name: currentScheme.scheme_name }))}`;
}

async function updateSaved(body) {
    if (busy) return null;
    busy = true;
    try {
        const result = await apiRequest(
            `/saved/${encodeURIComponent(Session.userId)}/${encodeURIComponent(currentScheme.scheme_name)}?lang=${currentLang()}`,
            { method: "PUT", body }
        );
        currentSaved = result.saved;
        return currentSaved;
    } catch (error) {
        showToast(error.message, "error");
        return null;
    } finally {
        busy = false;
        renderActions();
        renderDocuments();
    }
}

async function toggleSave() {
    if (busy) return;
    if (currentSaved) {
        busy = true;
        try {
            await apiRequest(
                `/saved/${encodeURIComponent(Session.userId)}/${encodeURIComponent(currentScheme.scheme_name)}`,
                { method: "DELETE" }
            );
            currentSaved = null;
            showToast(t("saved.removed"), "info");
        } catch (error) {
            showToast(error.message, "error");
        } finally {
            busy = false;
            renderActions();
            renderDocuments();
        }
    } else if (await updateSaved({})) {
        showToast(t("saved.added"), "success");
    }
}

async function toggleDocument(index, box) {
    const done = new Set((currentSaved && currentSaved.documents_done) || []);
    if (box.checked) done.add(index);
    else done.delete(index);
    // Ticking a document saves the scheme automatically.
    await updateSaved({ documents_done: [...done].sort((a, b) => a - b) });
}

// -------------------------------------------------------------------------
// Errors
// -------------------------------------------------------------------------

function renderErrorState(message) {
    document.title = `${t("scheme.error_title")} - Jeevandhara`;
    const loggedIn = Boolean(Session.userId);
    document.querySelector(".scheme-page").innerHTML = `
        <div class="panel error-panel scheme-detail-container">
            <h1>${escapeHTML(t("scheme.error_heading"))}</h1>
            <p>${escapeHTML(message)}</p>
            <a href="${loggedIn ? "dashboard.html" : "index.html"}" class="btn btn-primary">
                ${escapeHTML(loggedIn ? t("scheme.return_dashboard") : t("scheme.return_home"))}
            </a>
        </div>
    `;
}
