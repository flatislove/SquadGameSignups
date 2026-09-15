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
    
    // Загружаем статус записи на игру
    fetchStatus(userId);
    
    // Проверяем, является ли пользователь админом, чтобы показать вкладку создания анонса
    loadAdminChats();
});

// --- ПЕРЕКЛЮЧЕНИЕ ВКЛАДОК ---
function switchTab(tab) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    
    if (tab === 'signup') {
        document.getElementById('signupSection').classList.add('active');
        event.target.classList.add('active');
    } else {
        document.getElementById('createSection').classList.add('active');
        event.target.classList.add('active');
        loadAdminChats();
    }
}

// --- ЛОГИКА ЗАПИСИ НА ИГРУ ---
async function fetchStatus(userId) {
    try {
        const response = await fetch(`/api/user-status?user_id=${userId}`);
        const data = await response.json();

        const statusContainer = document.getElementById("status-container");
        const statusText = document.getElementById("status-text");
        const paymentText = document.getElementById("payment-text");
        const actionBtn = document.getElementById("action-btn");

        if (!statusContainer) return;

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
        const userInfo = document.getElementById("user-info");
        if (userInfo) userInfo.innerText = "Не удалось связаться с сервером.";
    }
}

async function registerUser(userId) {
    try {
        const response = await fetch(`/api/signup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId })
        });
        const result = await response.json();
        if (result.success) {
            tg.showAlert("Вы успешно добавлены в список!");
            fetchStatus(userId);
        } else {
            tg.showAlert("Не удалось записаться.");
        }
    } catch (e) {
        console.error("Ошибка записи:", e);
        tg.showAlert("Ошибка соединения с сервером.");
    }
}

// --- ЛОГИКА СОЗДАНИЯ АНОНСА (ДЛЯ АДМИНОВ) ---
async function loadAdminChats() {
    try {
        const response = await fetch(`/api/admin-chats?user_id=${userId}`);
        const chats = await response.json();
        const select = document.getElementById('chatSelect');
        
        if (!select) return;
        select.innerHTML = '';

        if (!chats || chats.length === 0) {
            select.innerHTML = '<option value="">Нет доступных групп (нужны права админа)</option>';
            return;
        }

        chats.forEach(chat => {
            const opt = document.createElement('option');
            opt.value = chat.id;
            opt.textContent = chat.title;
            select.appendChild(opt);
        });

        // Показываем переключатель вкладок, если есть админ-чаты
        const tabSwitcher = document.getElementById('tabSwitcher');
        if (tabSwitcher) tabSwitcher.style.display = 'flex';
    } catch (e) {
        console.error("Не удалось загрузить админ-чаты:", e);
    }
}

// Обработка отправки формы создания игры
document.addEventListener("DOMContentLoaded", () => {
    const gameForm = document.getElementById('gameForm');
    if (gameForm) {
        gameForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const payload = {
                chat_id: document.getElementById('chatSelect').value,
                date: document.getElementById('gameDate').value,
                time: document.getElementById('startTime').value,
                end_time: document.getElementById('endTime').value,
                loc_name: document.getElementById('locName').value,
                loc_link: document.getElementById('locLink').value,
                cost: document.getElementById('cost').value,
                max_players: document.getElementById('maxPlayers').value,
                name: document.getElementById('orgName').value,
                phone: document.getElementById('orgPhone').value
            };

            try {
                const response = await fetch('/api/create-game', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await response.json();
                
                if (result.success) {
                    tg.showAlert("✅ Анонс успешно опубликован в группу!");
                    tg.close();
                } else {
                    tg.showAlert("❌ Ошибка при создании анонса.");
                }
            } catch (e) {
                console.error("Ошибка создания игры:", e);
                tg.showAlert("❌ Ошибка соединения с сервером.");
            }
        });
    }
});