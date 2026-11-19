// Home page: a live, no-account eligibility check.
// Logged-in farmers go straight to their dashboard.

if (Session.userId) {
    window.location.replace("dashboard.html");
}

const QC_STORAGE_KEY = "jeevandhara_quickcheck";
let qcTimer = null;
let qcRequest = 0;
let qcLast = null;

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("quick-check");
    form.addEventListener("submit", (event) => event.preventDefault());
    ["qc-age", "qc-land", "qc-income"].forEach((id) => {
        document.getElementById(id).addEventListener("input", scheduleQuickCheck);
    });

    // Restore values typed earlier in this visit.
    try {
        const saved = JSON.parse(sessionStorage.getItem(QC_STORAGE_KEY) || "null");
        if (saved) {
            document.getElementById("qc-age").value = saved.age ?? "";
            document.getElementById("qc-land").value = saved.land_size ?? "";
            document.getElementById("qc-income").value = saved.income ?? "";
            runQuickCheck();
        }
    } catch (error) {
        /* ignore */
    }
});

document.addEventListener("languagechange", () => {
    if (qcLast) runQuickCheck();
    else renderEmpty();
});

function readQuickCheck() {
    const raw = {
        age: document.getElementById("qc-age").value.trim(),
        land_size: document.getElementById("qc-land").value.trim(),
        income: document.getElementById("qc-income").value.trim(),
    };
    if (!raw.age || !raw.land_size || !raw.income) return { complete: false };

    const values = { age: Number(raw.age), land_size: Number(raw.land_size), income: Number(raw.income) };
    const valid =
        Number.isInteger(values.age) && values.age >= 1 && values.age <= 120 &&
        Number.isFinite(values.land_size) && values.land_size >= 0 &&
        Number.isFinite(values.income) && values.income >= 0;
    return { complete: true, valid, values };
}

function scheduleQuickCheck() {
    clearTimeout(qcTimer);
    qcTimer = setTimeout(runQuickCheck, 350);
}

function renderEmpty() {
    document.getElementById("qc-result").innerHTML = `<p class="qc-empty">${escapeHTML(t("qc.empty"))}</p>`;
}

async function runQuickCheck() {
    const result = document.getElementById("qc-result");
    const input = readQuickCheck();

    if (!input.complete) {
        qcLast = null;
        renderEmpty();
        return;
    }
    if (!input.valid) {
        qcLast = null;
        result.innerHTML = `<p class="form-error">${escapeHTML(t("qc.invalid"))}</p>`;
        return;
    }

    sessionStorage.setItem(QC_STORAGE_KEY, JSON.stringify(input.values));
    const requestId = ++qcRequest;
    if (!qcLast) result.innerHTML = `<p class="qc-empty">${escapeHTML(t("qc.checking"))}</p>`;

    try {
        const data = await apiRequest(`/quick-check?lang=${currentLang()}`, { method: "POST", body: input.values });
        if (requestId !== qcRequest) return; // a newer check is on its way
        qcLast = data;
        renderResult(data);
    } catch (error) {
        if (requestId !== qcRequest) return;
        result.innerHTML = `<p class="form-error">${escapeHTML(error.message)}</p>`;
    }
}

function renderResult(data) {
    const rows = [
        ["eligible", data.eligible.length, "qc.r_eligible"],
        ["maybe", data.maybe.length, "qc.r_maybe"],
        ["not_eligible", data.not_eligible.length, "qc.r_not"],
    ];

    document.getElementById("qc-result").innerHTML = `
        <ul class="qc-rows">
            ${rows.map(([status, count, key]) => `
                <li class="qc-row">
                    <span class="qc-num">${count}</span>
                    <span class="qc-label">${escapeHTML(t(count === 1 ? `${key}_one` : key))}</span>
                    ${stampHTML(status)}
                </li>`).join("")}
        </ul>
        <a class="btn btn-primary btn-block" href="register.html">${escapeHTML(t("qc.cta"))}</a>
    `;
}
