// Farmer dashboard: profile, "My applications" (saved schemes), one scheme list
// sorted by status (Eligible / Check / Not eligible / All), profile editing and
// the assistant (text + voice). Shared helpers: common.js, i18n.js, voice.js.

const userId = Session.userId;

if (!userId) {
    flashMessage(translate("session.login_first", {}, "Please log in to open your dashboard."), "info");
    window.location.replace("login.html");
}

const CHAT_KEY = `jeevandhara_chat_${userId}`;
const STATUSES = ["interested", "collecting", "applied", "approved", "rejected"];
const FILTERS = ["eligible", "maybe", "not_eligible", "all"];

let currentProfile = null;
let recommendations = null;
let savedByName = {};
let activeFilter = null; // chosen automatically on first load
let chatMessages = [];
let chatBusy = false;
let renderedMessageCount = 0; // only new chat bubbles animate in
let openEditAfterLoad = false;

document.addEventListener("DOMContentLoaded", () => {
    if (!userId) return;

    setHeaderName(Session.userName);
    setupTabs();
    setupProfileModal();
    setupVoiceButton();
    document.getElementById("search-schemes-input").addEventListener("input", renderSchemeList);

    const params = new URLSearchParams(window.location.search);
    openEditAfterLoad = params.get("edit") === "1";

    loadDashboardData();
    initializeChatbot().then(() => {
        const question = params.get("ask");
        if (question) {
            toggleChatWindow(true);
            processAndSendChatMessage(question);
        }
    });

    if (params.has("ask") || params.has("edit")) {
        window.history.replaceState(null, "", window.location.pathname);
    }
});

document.addEventListener("languagechange", () => {
    if (!userId) return;
    setHeaderName(Session.userName);
    loadDashboardData();
    if (!chatMessages.some((msg) => msg.sender === "user")) {
        chatMessages = greetingMessages();
        renderedMessageCount = 0;
        saveChat();
    }
    renderChatMessages();
});

// -------------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------------

function setHeaderName(name) {
    const safeName = name || "Farmer";
    const initial = safeName.charAt(0).toUpperCase();
    document.getElementById("header-avatar").textContent = initial;
    document.getElementById("profile-avatar").textContent = initial;
    document.getElementById("header-user-name").textContent = safeName;
    document.getElementById("farmer-title").textContent = t("dash.hello", { name: safeName.split(" ")[0] });
}

function schemeUrl(name, hash = "") {
    return `scheme.html?id=${encodeURIComponent(name)}${hash}`;
}

function profileCompletion(profile) {
    const fields = ["name", "age", "income", "land_size", "state", "district", ...PROFILE_QUESTION_FIELDS];
    const filled = fields.filter((field) => {
        const value = profile[field];
        return value !== undefined && value !== null && String(value).trim() !== "";
    }).length;
    return Math.round((filled / fields.length) * 100);
}

// The stored user no longer exists (e.g. the database was reset): log out cleanly.
function handleMissingAccount(error) {
    if (error && error.status === 404) {
        Session.clear();
        flashMessage(t("session.missing"), "error");
        window.location.replace("login.html");
        return true;
    }
    return false;
}

function saveButtonHTML(scheme) {
    const saved = Boolean(savedByName[scheme.scheme_name]);
    const name = localized(scheme, "title") || scheme.scheme_name;
    const label = saved ? t("saved.unsave_scheme", { name }) : t("saved.save_scheme", { name });
    return `<button type="button" class="save-star ${saved ? "is-saved" : ""}" data-scheme="${escapeHTML(scheme.scheme_name)}"
                title="${escapeHTML(label)}" aria-label="${escapeHTML(label)}" aria-pressed="${saved}">${icon("star", 20)}</button>`;
}

// -------------------------------------------------------------------------
// Data
// -------------------------------------------------------------------------

async function loadDashboardData() {
    try {
        const data = await apiRequest(`/dashboard/${encodeURIComponent(userId)}?lang=${currentLang()}`);
        recommendations = data.recommendations;
        savedByName = {};
        (data.saved || []).forEach((item) => {
            savedByName[item.scheme_name] = item;
        });

        renderProfile(data.profile);
        renderPrompt(data.profile, recommendations);
        renderSaved(data.saved || []);
        renderCounts();
        renderSchemeList();

        if (openEditAfterLoad) {
            openEditAfterLoad = false;
            openProfileModal(true);
        }
    } catch (error) {
        if (handleMissingAccount(error)) return;
        console.error("Dashboard load error:", error);
        showToast(error.message, "error");
        document.getElementById("scheme-list").innerHTML = `
            <div class="list-empty-state">
                <p>${escapeHTML(t("rec.failed"))} ${escapeHTML(error.message)}</p>
                <button type="button" class="btn btn-quiet" onclick="loadDashboardData()">${escapeHTML(t("rec.retry"))}</button>
            </div>`;
    }
}

function renderProfile(profile) {
    currentProfile = profile;
    Session.setName(profile.name);
    setHeaderName(profile.name);

    const has = (value) => value !== null && value !== undefined && value !== "";
    document.getElementById("farmer-age").textContent = has(profile.age) ? t("fact.age_value", { n: profile.age }) : "-";
    document.getElementById("farmer-land").textContent = has(profile.land_size) ? `${profile.land_size} ${t("acres")}` : "-";
    document.getElementById("farmer-income").textContent = has(profile.income) ? formatRupees(profile.income) : "-";
    document.getElementById("farmer-place").textContent = [profile.district, profile.state].filter(has).join(", ") || "-";
}

// "Answer N questions to confirm M more schemes", with how complete the profile is.
function renderPrompt(profile, rec) {
    const missing = rec.profile_missing || [];
    const maybeCount = (rec.maybe_schemes || []).length;
    const banner = document.getElementById("profile-complete-banner");

    if (!missing.length) {
        banner.hidden = true;
        return;
    }
    const percent = profileCompletion(profile);
    document.getElementById("profile-complete-text").textContent = maybeCount
        ? t("dash.complete", { n: missing.length, m: maybeCount })
        : t("dash.complete_any", { n: missing.length });
    document.getElementById("profile-progress-bar").style.width = `${percent}%`;
    document.getElementById("profile-progress-text").textContent = t("dash.profile_done", { p: percent });
    banner.hidden = false;
}

// -------------------------------------------------------------------------
// Scheme list with status tabs
// -------------------------------------------------------------------------

function schemesFor(filter) {
    if (!recommendations) return [];
    const eligible = recommendations.eligible_schemes || [];
    const maybe = recommendations.maybe_schemes || [];
    const notEligible = recommendations.not_eligible_schemes || [];
    if (filter === "eligible") return eligible;
    if (filter === "maybe") return maybe;
    if (filter === "not_eligible") return notEligible;
    return [...eligible, ...maybe, ...notEligible];
}

function setupTabs() {
    const tabs = [...document.querySelectorAll(".tab")];
    tabs.forEach((tab) => {
        tab.addEventListener("click", () => selectTab(tab.dataset.filter, true));
        tab.addEventListener("keydown", (event) => {
            const index = tabs.indexOf(tab);
            let next = null;
            if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];
            if (event.key === "ArrowLeft") next = tabs[(index - 1 + tabs.length) % tabs.length];
            if (event.key === "Home") next = tabs[0];
            if (event.key === "End") next = tabs[tabs.length - 1];
            if (next) {
                event.preventDefault();
                selectTab(next.dataset.filter, true);
            }
        });
    });
}

function selectTab(filter, focus = false) {
    activeFilter = filter;
    document.querySelectorAll(".tab").forEach((tab) => {
        const selected = tab.dataset.filter === filter;
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
        if (selected && focus) tab.focus();
    });
    document.getElementById("scheme-list").setAttribute("aria-labelledby", `tab-${filter}`);
    renderSchemeList();
}

function renderCounts() {
    FILTERS.forEach((filter) => {
        document.getElementById(`count-${filter}`).textContent = schemesFor(filter).length;
    });

    // First load: open the most useful tab.
    if (!activeFilter) {
        const first = ["eligible", "maybe"].find((f) => schemesFor(f).length) || "all";
        selectTab(first);
    }
}

function renderTabHint(filter) {
    const hint = document.getElementById("tab-hint");
    const text = filter === "all" ? t("hint.all", { n: schemesFor("all").length }) : t(`hint.${filter}`);
    const action = filter === "maybe" && (recommendations.profile_missing || []).length
        ? `<button type="button" class="btn btn-haldi btn-sm" onclick="openProfileModal(true)">${escapeHTML(t("dash.complete_btn"))}</button>`
        : "";
    hint.innerHTML = `<span>${escapeHTML(text)}</span>${action}`;
}

function matchesSearch(scheme, query) {
    if (!query) return true;
    return [scheme.scheme_name, scheme.title, scheme.title_hi, scheme.tagline, scheme.tagline_hi]
        .filter(Boolean)
        .some((text) => String(text).toLowerCase().includes(query));
}

function schemeRowHTML(scheme) {
    const status = scheme.status || "eligible";
    // Eligible: say what the scheme gives. Check / not eligible: say why.
    const reason = status === "eligible"
        ? localized(scheme, "tagline")
        : (status === "not_eligible" ? scheme.reasons || [] : scheme.why_recommended || [])[0] || localized(scheme, "tagline");
    const title = localized(scheme, "title") || scheme.scheme_name;

    return `
        <article class="scheme-row scheme-item-card status-${escapeHTML(status)}" data-scheme="${escapeHTML(scheme.scheme_name)}">
            <div class="scheme-icon">${schemeIcon(scheme.scheme_name)}</div>
            <div class="scheme-body">
                <h3 class="scheme-name">
                    <a class="row-link" href="${schemeUrl(scheme.scheme_name)}">${escapeHTML(title)}</a>
                    <span class="scheme-code">${escapeHTML(scheme.scheme_name)}</span>
                </h3>
                ${reason ? `<p class="scheme-reason">${escapeHTML(reason)}</p>` : ""}
            </div>
            <div class="scheme-side">
                ${stampHTML(status)}
                ${saveButtonHTML(scheme)}
            </div>
        </article>`;
}

function renderSchemeList() {
    if (!recommendations || !activeFilter) return;
    const list = document.getElementById("scheme-list");
    const query = document.getElementById("search-schemes-input").value.toLowerCase().trim();
    const schemes = schemesFor(activeFilter).filter((scheme) => matchesSearch(scheme, query));

    renderTabHint(activeFilter);

    if (!schemes.length) {
        const searchingElsewhere = query && activeFilter !== "all";
        list.innerHTML = `
            <div class="list-empty-state">
                <p>${escapeHTML(query ? t("list.empty_search", { q: query }) : t("list.empty_tab"))}</p>
                ${searchingElsewhere ? `<button type="button" class="btn btn-quiet" onclick="selectTab('all')">${escapeHTML(t("list.search_all"))}</button>` : ""}
            </div>`;
        return;
    }

    list.innerHTML = schemes.map(schemeRowHTML).join("");
    list.querySelectorAll(".save-star").forEach((button) => {
        button.addEventListener("click", () => toggleSave(button.dataset.scheme));
    });
}

// -------------------------------------------------------------------------
// My applications (saved schemes)
// -------------------------------------------------------------------------

function renderSaved(items) {
    const container = document.getElementById("saved-container");
    document.getElementById("stat-saved-count").textContent = items.length;

    if (!items.length) {
        container.innerHTML = `<p class="saved-empty">${escapeHTML(t("saved.empty"))}</p>`;
        return;
    }

    container.innerHTML = "";
    items.forEach((item) => {
        const total = item.documents_total || 0;
        const done = (item.documents_done || []).length;
        const percent = total ? Math.round((done / total) * 100) : 0;

        const row = document.createElement("div");
        row.className = "saved-item";
        row.dataset.scheme = item.scheme_name;
        row.innerHTML = `
            <div class="saved-head">
                <span class="scheme-icon">${schemeIcon(item.scheme_name, 18)}</span>
                <div>
                    <a class="saved-title" href="${schemeUrl(item.scheme_name)}">${escapeHTML(localized(item, "title"))}</a>
                    <span class="saved-code">${escapeHTML(item.scheme_name)}</span>
                </div>
            </div>
            <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${done}"
                 aria-label="${escapeHTML(total ? t("saved.docs", { done, total }) : t("saved.no_docs"))}">
                <div class="progress-bar" style="width: ${percent}%"></div>
            </div>
            <div class="saved-docs">
                <span>${escapeHTML(total ? t("saved.docs", { done, total }) : t("saved.no_docs"))}</span>
                ${total ? `<a class="btn-small saved-checklist" href="${schemeUrl(item.scheme_name, "#documents")}">${escapeHTML(t("saved.checklist"))}</a>` : ""}
            </div>
            <div class="saved-actions">
                <select class="status-select status-${escapeHTML(item.status)}" aria-label="${escapeHTML(t("saved.status_label"))}">
                    ${STATUSES.map((s) => `<option value="${s}" ${s === item.status ? "selected" : ""}>${escapeHTML(t(`status.${s}`))}</option>`).join("")}
                </select>
                <button type="button" class="btn-link-danger">${escapeHTML(t("saved.remove"))}</button>
            </div>
        `;

        row.querySelector(".status-select").addEventListener("change", (event) => updateSavedStatus(item.scheme_name, event.target));
        row.querySelector(".btn-link-danger").addEventListener("click", () => toggleSave(item.scheme_name));
        container.appendChild(row);
    });
}

async function toggleSave(schemeName) {
    const wasSaved = Boolean(savedByName[schemeName]);
    try {
        if (wasSaved) {
            await apiRequest(`/saved/${encodeURIComponent(userId)}/${encodeURIComponent(schemeName)}`, { method: "DELETE" });
            showToast(t("saved.removed"), "info");
        } else {
            await apiRequest(`/saved/${encodeURIComponent(userId)}/${encodeURIComponent(schemeName)}`, { method: "PUT", body: {} });
            showToast(t("saved.added"), "success");
        }
        await loadDashboardData();
    } catch (error) {
        if (handleMissingAccount(error)) return;
        showToast(error.message, "error");
    }
}

async function updateSavedStatus(schemeName, select) {
    const status = select.value;
    select.className = `status-select status-${status}`;
    try {
        const result = await apiRequest(
            `/saved/${encodeURIComponent(userId)}/${encodeURIComponent(schemeName)}?lang=${currentLang()}`,
            { method: "PUT", body: { status } }
        );
        savedByName[schemeName] = result.saved;
    } catch (error) {
        if (handleMissingAccount(error)) return;
        showToast(error.message, "error");
    }
}

// -------------------------------------------------------------------------
// Edit profile
// -------------------------------------------------------------------------

const PROFILE_INPUTS = {
    name: "edit-name",
    age: "edit-age",
    income: "edit-income",
    land_size: "edit-land",
    state: "edit-state",
    district: "edit-district",
};

let lastFocusBeforeModal = null;

function setupProfileModal() {
    const overlay = document.getElementById("profile-modal");
    if (!overlay) return;

    buildProfileQuestions(document.getElementById("edit-questions"), "edit-");

    overlay.addEventListener("click", (event) => {
        if (event.target === overlay) closeProfileModal();
    });
    document.addEventListener("keydown", (event) => {
        if (overlay.hidden) return;
        if (event.key === "Escape") closeProfileModal();
        // Keep keyboard focus inside the dialog.
        if (event.key === "Tab") {
            const focusable = [...overlay.querySelectorAll("button, input, select, summary, [tabindex]:not([tabindex='-1'])")]
                .filter((el) => !el.disabled && el.offsetParent !== null);
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
    });
}

function openProfileModal(focusQuestions = false) {
    if (!currentProfile) {
        showToast(t("modal.loading"), "info");
        return;
    }

    Object.entries(PROFILE_INPUTS).forEach(([field, inputId]) => {
        const value = currentProfile[field];
        document.getElementById(inputId).value = value === null || value === undefined ? "" : value;
    });
    fillProfileQuestions("edit-", currentProfile);
    document.getElementById("profile-form-msg").textContent = "";

    lastFocusBeforeModal = document.activeElement;
    document.getElementById("profile-modal").hidden = false;
    document.body.style.overflow = "hidden";

    if (focusQuestions) {
        document.getElementById("edit-questions-block").open = true;
        const firstUnanswered = PROFILE_QUESTION_FIELDS.find((field) => currentProfile[field] === null);
        const target = document.getElementById(`edit-${firstUnanswered || PROFILE_QUESTION_FIELDS[0]}`);
        target.scrollIntoView({ block: "center" });
        target.focus();
    } else {
        document.getElementById("edit-name").focus();
    }
}

function closeProfileModal() {
    document.getElementById("profile-modal").hidden = true;
    document.body.style.overflow = "";
    if (lastFocusBeforeModal && typeof lastFocusBeforeModal.focus === "function") lastFocusBeforeModal.focus();
}

async function saveProfile() {
    const msg = document.getElementById("profile-form-msg");
    const saveBtn = document.getElementById("profile-save-btn");
    const value = (id) => document.getElementById(id).value.trim();

    const body = {
        name: value("edit-name"),
        age: parseInt(value("edit-age"), 10),
        income: parseFloat(value("edit-income")),
        land_size: parseFloat(value("edit-land")),
        state: value("edit-state"),
        district: value("edit-district"),
        ...readProfileQuestions("edit-"),
    };

    msg.textContent = "";
    if (!body.name || !body.state || !body.district || [body.age, body.income, body.land_size].some(Number.isNaN)) {
        msg.textContent = t("modal.fill_all");
        return;
    }
    if (body.age < 1 || body.age > 120) {
        msg.textContent = t("modal.bad_age");
        return;
    }
    if (body.income < 0 || body.land_size < 0) {
        msg.textContent = t("modal.negative");
        return;
    }

    saveBtn.disabled = true;
    const originalHTML = saveBtn.innerHTML;
    saveBtn.innerHTML = `<span class="spinner"></span> <span>${escapeHTML(t("modal.saving"))}</span>`;

    try {
        await apiRequest(`/profile/${encodeURIComponent(userId)}`, { method: "PUT", body });
        closeProfileModal();
        showToast(t("modal.updated"), "success");
        await loadDashboardData();
    } catch (error) {
        if (handleMissingAccount(error)) return;
        msg.textContent = error.status === 422 ? t("err.check_fields", { message: error.message }) : error.message;
    } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalHTML;
    }
}

// -------------------------------------------------------------------------
// Chatbot
// -------------------------------------------------------------------------

function getFormattedTime(date = new Date()) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatServerTime(value) {
    if (!value) return "";
    // SQLite CURRENT_TIMESTAMP is UTC in "YYYY-MM-DD HH:MM:SS" form.
    const date = new Date(String(value).replace(" ", "T") + "Z");
    return Number.isNaN(date.getTime()) ? "" : getFormattedTime(date);
}

function firstName() {
    return (Session.userName || "Farmer").split(" ")[0];
}

function defaultChips() {
    return [t("chat.chip1"), t("chat.chip2"), t("chat.chip3")];
}

function greetingMessages() {
    const timestamp = getFormattedTime();
    return [
        { sender: "bot", text: t("chat.hello", { name: firstName() }), timestamp },
        { sender: "bot", text: t("chat.intro"), timestamp, chips: defaultChips() },
    ];
}

function saveChat() {
    try {
        sessionStorage.setItem(CHAT_KEY, JSON.stringify(chatMessages));
    } catch (error) {
        /* storage full or unavailable */
    }
}

async function initializeChatbot() {
    try {
        chatMessages = JSON.parse(sessionStorage.getItem(CHAT_KEY) || "[]");
    } catch (error) {
        chatMessages = [];
    }

    if (!Array.isArray(chatMessages) || chatMessages.length === 0) {
        chatMessages = greetingMessages();

        // New browser session: bring back the last few questions from the server.
        try {
            const history = await apiRequest(`/chat-history/${encodeURIComponent(userId)}?limit=5`);
            if (history.length) {
                const restored = [];
                history.reverse().forEach((item) => {
                    const timestamp = formatServerTime(item.created_at);
                    restored.push({ sender: "user", text: item.question, timestamp });
                    restored.push({ sender: "bot", text: item.answer, timestamp });
                });
                restored.push({
                    sender: "bot",
                    text: t("chat.welcome_back", { name: firstName() }),
                    timestamp: getFormattedTime(),
                    chips: defaultChips(),
                });
                chatMessages = restored;
            }
        } catch (error) {
            /* history is optional */
        }
        saveChat();
    }

    renderChatMessages();
}

function renderChatMessages() {
    const container = document.getElementById("chatbot-messages");
    if (!container) return;
    container.innerHTML = "";

    chatMessages.forEach((msg, idx) => {
        const bubble = document.createElement("div");
        bubble.className = `message-bubble ${msg.sender === "user" ? "user" : "bot"}${msg.error ? " error" : ""}`;
        if (idx < renderedMessageCount) bubble.style.animation = "none";

        const text = document.createElement("div");
        text.className = "message-text";
        text.textContent = msg.text;
        bubble.appendChild(text);

        const footer = document.createElement("div");
        footer.className = "message-footer";

        if (msg.sender !== "user" && Voice.canSpeak) {
            const speakBtn = document.createElement("button");
            speakBtn.type = "button";
            speakBtn.className = "speak-btn";
            speakBtn.dataset.index = String(idx);
            const isSpeaking = Voice.speakingId() === `msg-${idx}`;
            speakBtn.innerHTML = icon(isSpeaking ? "stop" : "speaker", 16);
            speakBtn.title = isSpeaking ? t("chat.stop") : t("chat.speak");
            speakBtn.setAttribute("aria-label", speakBtn.title);
            speakBtn.addEventListener("click", () => speakMessage(idx));
            footer.appendChild(speakBtn);
        }

        if (msg.timestamp) {
            const time = document.createElement("span");
            time.className = "message-timestamp";
            time.textContent = msg.timestamp;
            footer.appendChild(time);
        }
        bubble.appendChild(footer);
        container.appendChild(bubble);

        // Follow-up chips only under the latest bot message.
        const isLast = idx === chatMessages.length - 1;
        if (msg.sender === "bot" && isLast && Array.isArray(msg.chips) && msg.chips.length && !chatBusy) {
            const chipsWrapper = document.createElement("div");
            chipsWrapper.className = "chips-wrapper";
            msg.chips.forEach((chipText) => {
                const chip = document.createElement("button");
                chip.type = "button";
                chip.className = "chat-chip";
                chip.textContent = chipText;
                chip.addEventListener("click", () => processAndSendChatMessage(chipText));
                chipsWrapper.appendChild(chip);
            });
            container.appendChild(chipsWrapper);
        }
    });

    renderedMessageCount = chatMessages.length;
    scrollToBottom();
}

function speakMessage(idx) {
    const msg = chatMessages[idx];
    if (!msg) return;
    const id = `msg-${idx}`;
    const update = () => {
        document.querySelectorAll(".speak-btn").forEach((button) => {
            const speaking = Voice.speakingId() === `msg-${button.dataset.index}`;
            button.innerHTML = icon(speaking ? "stop" : "speaker", 16);
            button.title = speaking ? t("chat.stop") : t("chat.speak");
            button.setAttribute("aria-label", button.title);
            button.classList.toggle("speaking", speaking);
        });
    };
    Voice.speak(id, msg.text, speechLangFor(msg.text), { onStart: update, onEnd: update });
}

function getFollowUpChips(question) {
    const query = question.toLowerCase();
    if (query.includes("eligib") || query.includes("who can") || query.includes("पात्र")) {
        return [t("chat.f_documents"), t("chat.f_apply"), t("chat.f_benefits")];
    }
    if (query.includes("document") || query.includes("paper") || query.includes("दस्तावेज")) {
        return [t("chat.f_eligible"), t("chat.f_apply"), t("chat.f_benefits")];
    }
    if (query.includes("apply") || query.includes("process") || query.includes("आवेदन")) {
        return [t("chat.f_eligible"), t("chat.f_documents"), t("chat.f_benefits")];
    }
    return [t("chat.f_eligible"), t("chat.f_documents"), t("chat.f_apply")];
}

function setChatBusy(busy) {
    chatBusy = busy;
    const sendBtn = document.querySelector(".chatbot-send-btn");
    if (sendBtn) sendBtn.disabled = busy;
}

async function processAndSendChatMessage(questionText) {
    const question = (questionText || "").trim();
    if (!question || chatBusy) return;

    Voice.stopSpeaking();
    chatMessages.forEach((msg) => delete msg.chips);
    chatMessages.push({ sender: "user", text: question, timestamp: getFormattedTime() });
    setChatBusy(true);
    saveChat();
    renderChatMessages();

    const typingIndicator = appendTypingIndicator();
    scrollToBottom();

    try {
        const result = await apiRequest(`/ask/${encodeURIComponent(userId)}`, {
            method: "POST",
            body: { question, lang: currentLang() },
        });

        const chips =
            Array.isArray(result.suggestions) && result.suggestions.length
                ? result.suggestions.slice(0, 3)
                : getFollowUpChips(question);

        chatMessages.push({
            sender: "bot",
            text: result.answer || t("chat.not_understood"),
            timestamp: getFormattedTime(),
            chips,
        });
    } catch (error) {
        console.error("Chat error:", error);
        if (handleMissingAccount(error)) return;
        chatMessages.push({
            sender: "bot",
            text: error.status === 0 ? t("chat.connection") : error.message,
            timestamp: getFormattedTime(),
            chips: [question],
            error: true,
        });
    } finally {
        typingIndicator.remove();
        setChatBusy(false);
        saveChat();
        renderChatMessages();
        const input = document.getElementById("chatbot-input-field");
        if (input) input.focus();
    }
}

async function sendChatMessage() {
    const input = document.getElementById("chatbot-input-field");
    if (!input || chatBusy) return;
    const questionText = input.value.trim();
    if (!questionText) return;

    input.value = "";
    await processAndSendChatMessage(questionText);
}

async function clearChat() {
    if (chatBusy) return;
    try {
        await apiRequest(`/chat-history/${encodeURIComponent(userId)}`, { method: "DELETE" });
    } catch (error) {
        if (handleMissingAccount(error)) return;
        showToast(error.message, "error");
        return;
    }
    Voice.stopSpeaking();
    chatMessages = greetingMessages();
    renderedMessageCount = 0;
    saveChat();
    renderChatMessages();
    showToast(t("chat.cleared"), "success");
}

function toggleChatWindow(isOpen) {
    const launcher = document.getElementById("chatbot-collapsed");
    const windowEl = document.getElementById("chatbot-window");
    const input = document.getElementById("chatbot-input-field");

    if (isOpen) {
        launcher.hidden = true;
        launcher.setAttribute("aria-expanded", "true");
        windowEl.style.display = "flex";
        windowEl.style.animation = "sheetUp 0.25s cubic-bezier(0.2, 0.7, 0.2, 1) both";
        renderChatMessages();
        setTimeout(() => input && input.focus(), 50);
    } else {
        Voice.stopSpeaking();
        if (Voice.isListening()) Voice.stopListening();
        windowEl.style.display = "none";
        launcher.hidden = false;
        launcher.setAttribute("aria-expanded", "false");
        launcher.focus();
    }
}

// Escape closes the assistant.
document.addEventListener("keydown", (event) => {
    const windowEl = document.getElementById("chatbot-window");
    const modal = document.getElementById("profile-modal");
    if (event.key === "Escape" && windowEl && windowEl.style.display === "flex" && (!modal || modal.hidden)) {
        toggleChatWindow(false);
    }
});

function scrollToBottom() {
    const messages = document.getElementById("chatbot-messages");
    if (messages) messages.scrollTop = messages.scrollHeight;
}

function appendTypingIndicator() {
    const container = document.getElementById("chatbot-messages");
    const indicator = document.createElement("div");
    indicator.className = "message-bubble bot typing-indicator-bubble";
    indicator.innerHTML = `
        <span class="typing-text">${escapeHTML(t("chat.typing"))}</span>
        <div class="typing-indicator">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
        </div>
    `;
    container.appendChild(indicator);
    return indicator;
}

// -------------------------------------------------------------------------
// Voice input
// -------------------------------------------------------------------------

function setupVoiceButton() {
    const mic = document.getElementById("chatbot-mic-btn");
    if (mic) mic.hidden = !Voice.canListen;
}

function toggleVoiceInput() {
    const mic = document.getElementById("chatbot-mic-btn");
    const input = document.getElementById("chatbot-input-field");

    if (!Voice.canListen) {
        showToast(t("voice.unsupported"), "error");
        return;
    }
    if (Voice.isListening()) {
        Voice.stopListening();
        return;
    }
    if (chatBusy) return;

    Voice.stopSpeaking();
    mic.classList.add("listening");
    input.value = "";
    input.placeholder = t("chat.listening");

    Voice.listen({
        lang: currentLang() === "hi" ? "hi-IN" : "en-IN",
        onInterim: (text) => {
            input.value = text;
        },
        onResult: (text) => {
            input.value = text;
            sendChatMessage();
        },
        onError: (code) => {
            if (code === "not-allowed" || code === "service-not-allowed") showToast(t("voice.denied"), "error");
            else if (code === "no-speech") showToast(t("voice.no_speech"), "info");
            else if (code !== "aborted") showToast(t("voice.no_speech"), "info");
        },
        onEnd: () => {
            mic.classList.remove("listening");
            input.placeholder = t("chat.placeholder");
        },
    });
}

// -------------------------------------------------------------------------
// Logout
// -------------------------------------------------------------------------

function logout() {
    Voice.stopSpeaking();
    Session.clear();
    flashMessage(t("session.logged_out"), "info");
    window.location.href = "index.html";
}
