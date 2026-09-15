const tg = window.Telegram.WebApp;
tg.expand();

const user = tg.initDataUnsafe?.user;
const userId = user ? user.id : null;

document.addEventListener("DOMContentLoaded", () => {
    if (!userId) {
        document.getElementById("user-info").innerText = "Ошибка: не удалось определить пользователя.";
        return;
    }

    document.getElementById("user-info").innerText = `Привет, ${user.first_name || 'Игрок'}!`;
    fetchStatus(userId);
});

async function fetchStatus(userId) {
    try {
        const response = await fetch(`https://squadgamesignups.onrender.com/api/user-status?user_id=${userId}`);
        const data = await response.json();

        const statusContainer = document.getElementById("status-container");
        const statusText = document.getElementById("status-text");
        const paymentText = document.getElementById("payment-text");
        const actionBtn = document.getElementById("action-btn");

        statusContainer.style.display = "block";
        statusText.innerText = data.message;
        paymentText.innerText = data.payment_text || "";

        if (data.status === "not_registered") {
            actionBtn.style.display = "block";
            actionBtn.innerText = "Записаться";
            actionBtn.onclick = () => registerUser(userId);
        } else {
            actionBtn.style.display = "none";
        }

    } catch (e) {
        console.error("Ошибка загрузки статуса:", e);
        document.getElementById("user-info").innerText = "Не удалось связаться с сервером.";
    }
}

async function registerUser(userId) {
    try {
        await fetch(`https://squadgamesignups.onrender.com/api/signup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId })
        });
        fetchStatus(userId);
    } catch (e) {
        alert("Ошибка записи.");
    }
}