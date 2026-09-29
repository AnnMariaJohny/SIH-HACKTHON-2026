const form = document.getElementById("loginForm");
const password = document.getElementById("password");
const togglePassword = document.getElementById("togglePassword");
const message = document.getElementById("message");
const spaceInfo = document.querySelector(".space-info");
const forgotLink = document.querySelector(".forgot");
const resetPanel = document.getElementById("resetPanel");
const resetForm = document.getElementById("resetForm");
const resetCancel = document.getElementById("resetCancel");
const resetMessage = document.getElementById("resetMessage");
let lastRippleTime = 0;

document.body.addEventListener("pointermove", (event) => {
    if (event.pointerType === "touch") return;

    const now = performance.now();
    if (now - lastRippleTime < 90) return;
    lastRippleTime = now;

    const ripple = document.createElement("span");
    ripple.className = "pointer-ripple";
    ripple.setAttribute("aria-hidden", "true");
    ripple.style.left = `${event.clientX}px`;
    ripple.style.top = `${event.clientY}px`;
    document.body.appendChild(ripple);
    ripple.addEventListener("animationend", () => ripple.remove(), { once: true });
});

if (spaceInfo) {

    spaceInfo.addEventListener("pointermove", (event) => {
        const bounds = spaceInfo.getBoundingClientRect();
        const offsetX = ((event.clientX - bounds.left) / bounds.width - .5) * 18;
        const offsetY = ((event.clientY - bounds.top) / bounds.height - .5) * 12;

        spaceInfo.style.setProperty("--scene-x", `${offsetX.toFixed(2)}px`);
        spaceInfo.style.setProperty("--scene-y", `${offsetY.toFixed(2)}px`);
    });

    spaceInfo.addEventListener("pointerleave", () => {
        spaceInfo.style.setProperty("--scene-x", "0px");
        spaceInfo.style.setProperty("--scene-y", "0px");
    });
}

forgotLink.addEventListener("click", (event) => {
    event.preventDefault();
    resetPanel.hidden = false;
    resetMessage.textContent = "";
    document.getElementById("resetEmail").focus();
});

resetCancel.addEventListener("click", () => {
    resetPanel.hidden = true;
    resetForm.reset();
});

resetForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const resetEmail = document.getElementById("resetEmail").value.trim().toLowerCase();
    const resetPassword = document.getElementById("resetPassword").value;
    const users = JSON.parse(localStorage.getItem("oceanovaUsers") || "[]");
    const registeredUser = users.find((user) => user.email === resetEmail);

    if (!registeredUser) {
        resetMessage.textContent = "Email not found. Register first.";
        return;
    }

    if (resetPassword.length < 8) {
        resetMessage.textContent = "Password must contain at least 8 characters.";
        return;
    }

    registeredUser.password = resetPassword;
    localStorage.setItem("oceanovaUsers", JSON.stringify(users));
    resetMessage.textContent = "PASSWORD UPDATED. YOU CAN LOG IN NOW.";
    resetForm.reset();
});

togglePassword.addEventListener("click", () => {

    const isPassword = password.type === "password";

    password.type = isPassword ? "text" : "password";

    togglePassword.textContent = isPassword ? "HIDE" : "SHOW";

});

form.addEventListener("submit", async (event) => {

    event.preventDefault();

    const email = document.getElementById("email").value.trim();
    const passwordValue = password.value;

    if (!email || !passwordValue) {
        message.textContent = "Please complete all fields.";
        return;
    }

    const normalizedEmail = email.toLowerCase();
    const users = JSON.parse(localStorage.getItem("oceanovaUsers") || "[]");
    const registeredUser = users.find((user) => user.email === normalizedEmail);

    if (!registeredUser) {
        message.textContent = "Email not found. Please register first.";
        return;
    }

    if (registeredUser.password !== passwordValue) {
        message.textContent = "Invalid password.";
        return;
    }

    message.textContent = "ACCESS GRANTED.";
    window.location.href = "/";

});