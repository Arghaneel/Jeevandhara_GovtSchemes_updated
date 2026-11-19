/*
 * Shared helpers for every Jeevandhara page.
 * Load this first, then i18n.js, then the page's own script.
 */

// Where the FastAPI backend lives.
// - Pages served by the backend itself (http://127.0.0.1:8000/app/...) use the same origin.
// - Pages opened from disk or another dev server (Live Server, etc.) use 127.0.0.1:8000.
// - Override with localStorage.setItem("api_base", "http://host:port") if needed.
const API_BASE = (() => {
    try {
        const override = localStorage.getItem("api_base");
        if (override) return override.replace(/\/+$/, "");
    } catch (error) {
        /* storage unavailable */
    }
    const { protocol, origin, pathname } = window.location;
    if (protocol.startsWith("http") && pathname.startsWith("/app")) return origin;
    return "http://127.0.0.1:8000";
})();

// Apply the saved theme as early as possible to avoid a light flash.
try {
    if (localStorage.getItem("theme") === "dark") document.documentElement.classList.add("theme-dark-pending");
} catch (error) {
    /* storage unavailable */
}

class ApiError extends Error {
    constructor(message, status, data) {
        super(message);
        this.status = status;
        this.data = data;
    }
}

// fetch() wrapper: sends/receives JSON and turns every failure into an ApiError
// whose message can be shown to the farmer as-is.
async function apiRequest(path, { method = "GET", body } = {}) {
    const options = { method, headers: {} };
    if (body !== undefined) {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(body);
    }

    let response;
    try {
        response = await fetch(`${API_BASE}${path}`, options);
    } catch (error) {
        throw new ApiError(translate("err.server", {}, "Cannot reach the Jeevandhara server. Please make sure the backend is running."), 0, null);
    }

    let data = null;
    try {
        data = await response.json();
    } catch (error) {
        /* empty or non-JSON body */
    }

    if (!response.ok) {
        let message =
            (data && (data.message || (typeof data.detail === "string" ? data.detail : ""))) ||
            translate("err.request", { status: response.status }, `Request failed (${response.status})`);
        if (data && data.code) message = translate(`err.${data.code}`, {}, message);
        throw new ApiError(message, response.status, data);
    }
    return data;
}

// t() lives in i18n.js; fall back to English if a page doesn't load it.
function translate(key, vars, fallback) {
    if (typeof t === "function") {
        const text = t(key, vars);
        if (text !== key) return text;
    }
    return fallback;
}

function currentLang() {
    return typeof getLang === "function" ? getLang() : "en";
}

// -------------------------------------------------------------------------
// Icons (drawn for Jeevandhara; 24px grid, stroked with currentColor)
// -------------------------------------------------------------------------

const ICONS = {
    // schemes
    coin: '<circle cx="12" cy="12" r="9"/><path d="M9 7.5h6M9 10.5h6M9.5 7.5h1.5a3 3 0 0 1 0 6H9.5l4.5 4"/>',
    card: '<rect x="3" y="5.5" width="18" height="13" rx="2.5"/><path d="M3 10h18M7 15h4"/>',
    umbrella: '<path d="M3 12a9 9 0 0 1 18 0z"/><path d="M12 12v6a2 2 0 0 1-4 0M12 3v0.5"/>',
    hourglass: '<path d="M7 3h10M7 21h10M8 3v3.5l4 4.5 4-4.5V3M8 21v-3.5l4-4.5 4 4.5V21"/>',
    bank: '<path d="M3 9.5 12 4l9 5.5M5 10v7.5M9.5 10v7.5M14.5 10v7.5M19 10v7.5M3 20.5h18"/>',
    sprout: '<path d="M12 21v-9"/><path d="M12 12C12 8 9 6 5 6c0 4 3 6 7 6zM12 10.5c0-3.2 2.4-5.5 6.5-5.5 0 3.2-2.4 5.5-6.5 5.5z"/>',
    warehouse: '<path d="M3 21V9.5L12 4l9 5.5V21"/><path d="M7 21v-7.5h10V21M7 17.25h10"/>',
    pin: '<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>',
    map: '<path d="M3 6.5 9 4l6 2.5L21 4v13.5L15 20l-6-2.5L3 20z"/><path d="M9 4v13.5M15 6.5V20"/>',
    document: '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M9.5 12h5M9.5 16h5"/>',
    flask: '<path d="M9 3h6M10 3v6.5L5.2 17.6A2.2 2.2 0 0 0 7.1 21h9.8a2.2 2.2 0 0 0 1.9-3.4L14 9.5V3"/><path d="M7.5 15h9"/>',
    drop: '<path d="M12 3.5s6 6.6 6 10.8a6 6 0 0 1-12 0c0-4.2 6-10.8 6-10.8z"/>',
    tractor: '<circle cx="7.5" cy="16.5" r="3.5"/><circle cx="18" cy="18" r="2"/><path d="M4 13V7.5h6.5l2 5.5H18a2 2 0 0 1 2 2v1M6 7.5V4.5h4M11 16.5h5"/>',
    scales: '<path d="M12 4v16M7.5 20h9M5 7h14"/><path d="M5 7 2.5 12.5a2.6 2.6 0 0 0 5 0zM19 7l-2.5 5.5a2.6 2.6 0 0 0 5 0z"/>',
    leaf: '<path d="M5 19C5 11 10.5 5 19 5c0 8.5-6 14-14 14z"/><path d="M5 19l7.5-7.5"/>',
    // interface
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    star: '<path d="m12 3.6 2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8z"/>',
    chat: '<path d="M4 5.5h16v10.5H9l-5 4z"/><path d="M8 9.5h8M8 12.5h5"/>',
    mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
    send: '<path d="M4 12 20 4l-6 16-2.5-6.5z"/><path d="m11.5 13.5 3-3"/>',
    speaker: '<path d="M4 9.5h3.5L12 6v12l-4.5-3.5H4z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>',
    stop: '<rect x="7" y="7" width="10" height="10" rx="1.5"/>',
    close: '<path d="M6 6l12 12M18 6 6 18"/>',
    trash: '<path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13"/>',
    moon: '<path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    cross: '<path d="M7 7l10 10M17 7 7 17"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.8v.2"/>',
    back: '<path d="M15 5 8 12l7 7"/>',
    external: '<path d="M14 4h6v6M20 4l-9 9M18 14v5H5V6h5"/>',
    edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
    phone: '<path d="M6 3.5h3l1.5 4.5-2 1.5a11 11 0 0 0 6 6l1.5-2 4.5 1.5v3a2 2 0 0 1-2 2A16.5 16.5 0 0 1 4 5.5a2 2 0 0 1 2-2z"/>',
};

const SCHEME_ICON = {
    "PM-KISAN": "coin",
    KCC: "card",
    PM_KMY: "hourglass",
    PMFBY: "umbrella",
    PMJDY: "bank",
    NMSA: "sprout",
    AIF: "warehouse",
    APY: "hourglass",
    BHU_AADHAAR_ULPIN: "pin",
    DILRMP: "document",
    ICAR: "flask",
    LAND_REFORMS: "map",
    NEERANCHAL: "drop",
    PGS_India_NCOF: "leaf",
    SNAM: "tractor",
    WDC_PMKSY: "drop",
    eNAM: "scales",
};

function icon(name, size = 20, strokeWidth = 1.8) {
    return `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${ICONS[name] || ""}</svg>`;
}

function schemeIcon(schemeName, size = 22) {
    return icon(SCHEME_ICON[schemeName] || "sprout", size);
}

// Fill <span data-icon="search" data-icon-size="18"></span> placeholders.
function hydrateIcons(root = document) {
    root.querySelectorAll("[data-icon]").forEach((el) => {
        el.innerHTML = icon(el.dataset.icon, Number(el.dataset.iconSize) || 20);
    });
}

// The status stamp shown on every scheme: eligible / maybe / not_eligible.
const STAMP_KEYS = { eligible: "stamp.eligible", maybe: "stamp.maybe", not_eligible: "stamp.not_eligible" };

function stampHTML(status, extraClass = "") {
    const key = STAMP_KEYS[status] || STAMP_KEYS.maybe;
    return `<span class="stamp stamp--${escapeHTML(status)} ${extraClass}">${escapeHTML(translate(key, {}, status))}</span>`;
}

// -------------------------------------------------------------------------
// Optional profile questions (shared by the register page and Edit profile)
// -------------------------------------------------------------------------

const YES_NO_OPTIONS = [["", "opt.not_sure"], ["true", "opt.yes"], ["false", "opt.no"]];

const PROFILE_QUESTION_DEFS = [
    {
        field: "land_ownership", label: "q.land_ownership",
        options: [["", "opt.not_sure"], ["owner", "q.land_owner"], ["tenant", "q.land_tenant"], ["landless", "q.land_landless"]],
    },
    { field: "income_tax_payer", label: "q.income_tax_payer", options: YES_NO_OPTIONS },
    { field: "govt_employee", label: "q.govt_employee", options: YES_NO_OPTIONS },
    { field: "social_security", label: "q.social_security", options: YES_NO_OPTIONS },
    { field: "has_bank_account", label: "q.has_bank_account", options: YES_NO_OPTIONS },
    {
        field: "social_category", label: "q.social_category",
        options: [["", "opt.prefer_not"], ["general", "q.cat_general"], ["obc", "q.cat_obc"], ["sc", "q.cat_sc"], ["st", "q.cat_st"]],
    },
    {
        field: "gender", label: "q.gender",
        options: [["", "opt.prefer_not"], ["male", "q.male"], ["female", "q.female"], ["other", "q.other"]],
    },
];

const PROFILE_QUESTION_FIELDS = PROFILE_QUESTION_DEFS.map((q) => q.field);

function buildProfileQuestions(container, prefix) {
    container.innerHTML = PROFILE_QUESTION_DEFS.map((q) => `
        <div class="field${q.field === "land_ownership" ? " span-2" : ""}">
            <label for="${prefix}${q.field}" data-i18n="${q.label}"></label>
            <select id="${prefix}${q.field}" class="input select">
                ${q.options.map(([value, key]) => `<option value="${value}" data-i18n="${key}"></option>`).join("")}
            </select>
        </div>
    `).join("");
    if (typeof applyTranslations === "function") applyTranslations(container);
}

function readProfileQuestions(prefix) {
    const answers = {};
    PROFILE_QUESTION_FIELDS.forEach((field) => {
        const el = document.getElementById(`${prefix}${field}`);
        if (!el) return;
        const value = el.value;
        answers[field] = value === "" ? null : value === "true" ? true : value === "false" ? false : value;
    });
    return answers;
}

function fillProfileQuestions(prefix, profile) {
    PROFILE_QUESTION_FIELDS.forEach((field) => {
        const el = document.getElementById(`${prefix}${field}`);
        if (!el) return;
        const value = profile ? profile[field] : null;
        el.value = value === null || value === undefined ? "" : String(value);
    });
}

// -------------------------------------------------------------------------
// Session, text, toasts
// -------------------------------------------------------------------------

// Logged-in farmer, kept in localStorage.
const Session = {
    get userId() {
        return localStorage.getItem("user_id");
    },
    get userName() {
        return localStorage.getItem("user_name") || "Farmer";
    },
    save(userId, name) {
        localStorage.setItem("user_id", String(userId));
        localStorage.setItem("user_name", name || "Farmer");
    },
    setName(name) {
        localStorage.setItem("user_name", name || "Farmer");
    },
    clear() {
        const userId = localStorage.getItem("user_id");
        localStorage.removeItem("user_id");
        localStorage.removeItem("user_name");
        if (userId) sessionStorage.removeItem(`jeevandhara_chat_${userId}`);
        sessionStorage.removeItem("jeevandhara_chat_history"); // older versions
    },
};

function escapeHTML(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const icons = { success: "check", error: "cross", info: "info" };
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.setAttribute("role", type === "error" ? "alert" : "status");

    const badge = document.createElement("span");
    badge.className = "toast-icon";
    badge.innerHTML = icon(icons[type] || icons.info, 14, 2.6);

    const text = document.createElement("span");
    text.className = "toast-message";
    text.textContent = message;

    toast.append(badge, text);
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.transition = "opacity 0.25s ease";
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 260);
    }, 3500);
}

// A toast that survives a page redirect (e.g. "Please log in first").
function flashMessage(message, type = "info") {
    sessionStorage.setItem("jeevandhara_flash", JSON.stringify({ message, type }));
}

function showPendingFlash() {
    const raw = sessionStorage.getItem("jeevandhara_flash");
    if (!raw) return;
    sessionStorage.removeItem("jeevandhara_flash");
    try {
        const { message, type } = JSON.parse(raw);
        if (message) showToast(message, type);
    } catch (error) {
        /* ignore malformed flash */
    }
}

function initTheme() {
    const theme = localStorage.getItem("theme") || "light";
    document.body.classList.toggle("dark-mode", theme === "dark");
    document.documentElement.classList.remove("theme-dark-pending");

    const themeBtn = document.getElementById("theme-btn");
    if (!themeBtn) return;
    const paint = (isDark) => {
        themeBtn.innerHTML = icon(isDark ? "sun" : "moon", 18);
    };
    paint(theme === "dark");

    themeBtn.addEventListener("click", () => {
        const isDark = document.body.classList.toggle("dark-mode");
        localStorage.setItem("theme", isDark ? "dark" : "light");
        paint(isDark);
    });
}

// "Show" / "Hide" buttons next to password fields: <button data-reveal="password">.
function initPasswordReveal() {
    document.querySelectorAll("[data-reveal]").forEach((button) => {
        const input = document.getElementById(button.dataset.reveal);
        if (!input) return;
        const paint = () => {
            const shown = input.type === "text";
            button.textContent = translate(shown ? "pw.hide" : "pw.show", {}, shown ? "Hide" : "Show");
            button.setAttribute("aria-label", translate(shown ? "pw.hide_label" : "pw.show_label", {}, button.textContent));
            button.setAttribute("aria-pressed", String(shown));
        };
        button.addEventListener("click", () => {
            input.type = input.type === "password" ? "text" : "password";
            paint();
            input.focus();
        });
        document.addEventListener("languagechange", paint);
        paint();
    });
}

function formatRupees(amount) {
    const value = Number(amount);
    if (!Number.isFinite(value)) return "-";
    return `₹${value.toLocaleString("en-IN")}`;
}

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    hydrateIcons();
    initPasswordReveal();
    showPendingFlash();
});
