// Login page. Theme, language, toasts and API helpers come from common.js / i18n.js.

if (Session.userId) {
    window.location.replace("dashboard.html");
}

document.addEventListener("DOMContentLoaded", () => {
    // Pre-fill the username right after registration.
    const prefill = sessionStorage.getItem("jeevandhara_prefill_username");
    if (prefill) {
        sessionStorage.removeItem("jeevandhara_prefill_username");
        document.getElementById("username").value = prefill;
        document.getElementById("password").focus();
    }
});

async function login() {
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    const msgElement = document.getElementById("msg");
    const submitBtn = document.getElementById("submit-btn");

    msgElement.textContent = "";

    if (!username || !password) {
        showToast(t("login.need_both"), "error");
        return;
    }

    submitBtn.disabled = true;
    const originalBtnHTML = submitBtn.innerHTML;
    submitBtn.innerHTML = `<span class="spinner"></span> <span>${escapeHTML(t("login.signing_in"))}</span>`;

    try {
        const result = await apiRequest("/login", {
            method: "POST",
            body: { username, password },
        });

        Session.save(result.user_id, result.name);
        showToast(t("login.welcome_back", { name: result.name }), "success");

        setTimeout(() => {
            window.location.href = "dashboard.html";
        }, 800);
    } catch (error) {
        console.error("Login error:", error);
        const message = error.status === 401 ? t("login.invalid") : error.message;
        showToast(message, "error");
        msgElement.textContent = message;
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnHTML;
    }
}
