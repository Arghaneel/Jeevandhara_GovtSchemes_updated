// Registration page. Theme, language, toasts and API helpers come from common.js / i18n.js.

if (Session.userId) {
    window.location.replace("dashboard.html");
}

document.addEventListener("DOMContentLoaded", () => {
    buildProfileQuestions(document.getElementById("reg-questions"), "reg-");

    // Carry over the age, land and income typed into the home page check.
    try {
        const quick = JSON.parse(sessionStorage.getItem("jeevandhara_quickcheck") || "null");
        if (quick) {
            if (quick.age) document.getElementById("age").value = quick.age;
            if (quick.land_size !== undefined) document.getElementById("land_size").value = quick.land_size;
            if (quick.income !== undefined) document.getElementById("income").value = quick.income;
        }
    } catch (error) {
        /* ignore */
    }

    // Clear the error mark as soon as a field is edited.
    document.getElementById("register-form").addEventListener("input", (event) => {
        event.target.removeAttribute("aria-invalid");
    });
});

async function register() {
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    const name = document.getElementById("name").value.trim();
    const age = parseInt(document.getElementById("age").value, 10);
    const income = parseFloat(document.getElementById("income").value);
    const landSize = parseFloat(document.getElementById("land_size").value);
    const state = document.getElementById("state").value.trim();
    const district = document.getElementById("district").value.trim();
    const msgElement = document.getElementById("msg");
    const submitBtn = document.getElementById("submit-btn");

    msgElement.textContent = "";

    const fail = (message, fieldId) => {
        showToast(message, "error");
        msgElement.textContent = message;
        if (fieldId) {
            const field = document.getElementById(fieldId);
            field.setAttribute("aria-invalid", "true");
            field.focus();
        }
    };

    const required = { name, age: isNaN(age) ? "" : age, land_size: isNaN(landSize) ? "" : landSize,
                       income: isNaN(income) ? "" : income, state, district, username, password };
    const firstEmpty = Object.keys(required).find((id) => required[id] === "" || required[id] === undefined);
    if (firstEmpty) return fail(t("register.fill_all"), firstEmpty);
    if (age < 1 || age > 120) return fail(t("register.bad_age"), "age");
    if (landSize < 0) return fail(t("register.bad_land"), "land_size");
    if (income < 0) return fail(t("register.bad_income"), "income");
    if (username.length < 3) return fail(t("register.username_short"), "username");
    if (password.length < 6) return fail(t("register.password_short"), "password");

    submitBtn.disabled = true;
    const originalBtnHTML = submitBtn.innerHTML;
    submitBtn.innerHTML = `<span class="spinner"></span> <span>${escapeHTML(t("register.registering"))}</span>`;

    try {
        await apiRequest("/register", {
            method: "POST",
            body: {
                username,
                password,
                name,
                age,
                income,
                land_size: landSize,
                state,
                district,
                ...readProfileQuestions("reg-"),
            },
        });

        showToast(t("register.done"), "success");

        document.getElementById("register-form-panel").style.display = "none";
        const successOverlay = document.getElementById("success-overlay");
        successOverlay.style.display = "block";
        const path = successOverlay.querySelector("path");
        if (path) path.style.animation = "dash 0.8s ease-in-out forwards";

        sessionStorage.setItem("jeevandhara_prefill_username", username);
        sessionStorage.removeItem("jeevandhara_quickcheck");
        flashMessage(t("register.flash"), "success");

        setTimeout(() => {
            window.location.href = "login.html";
        }, 1800);
    } catch (error) {
        console.error("Registration error:", error);
        const message = error.status === 422 ? t("err.check_fields", { message: error.message }) : error.message;
        fail(message || t("register.failed"), error.status === 409 ? "username" : null);
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnHTML;
    }
}
