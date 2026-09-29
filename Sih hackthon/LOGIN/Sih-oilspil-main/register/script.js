const form = document.getElementById("registerForm");

const nameInput = document.getElementById("name");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const confirmPasswordInput = document.getElementById("confirmPassword");

const message = document.getElementById("message");
const spaceInfo = document.querySelector(".space-info");
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

form.addEventListener("submit", async (event) => {

    event.preventDefault();

    const name = nameInput.value.trim();
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;

    if (!name || !email || !password || !confirmPassword) {
        message.textContent = "Please complete all fields.";
        return;
    }

    if (password !== confirmPassword) {
        message.textContent = "Passwords do not match.";
        return;
    }

    if (password.length < 8) {
        message.textContent =
            "Password must contain at least 8 characters.";
        return;
    }

    const normalizedEmail = email.toLowerCase();
    const users = JSON.parse(localStorage.getItem("oceanovaUsers") || "[]");

    if (users.some((user) => user.email === normalizedEmail)) {
        message.textContent = "Email already registered.";
        return;
    }

    users.push({
        name: name,
        email: normalizedEmail,
        password: password
    });

    localStorage.setItem("oceanovaUsers", JSON.stringify(users));
    message.textContent = "ACCOUNT CREATED. REDIRECTING...";

    setTimeout(() => {
        window.location.href = "../Login/Index.html";
    }, 1000);

});