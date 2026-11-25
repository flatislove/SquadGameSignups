import { tg } from './tg.js';
import { apiFetch } from './api.js';

export async function initRouter() {
    const urlParams = new URLSearchParams(window.location.search);
    const startParam = tg.initDataUnsafe?.start_param || urlParams.get('startapp');

    console.log("WebApp start_param:", startParam);

    if (startParam && startParam.startsWith('game_')) {
        const gameId = startParam.replace('game_', '');
        window.CURRENT_GAME_ID = gameId;
        document.getElementById('tabSwitcher').style.display = 'none';
        document.getElementById('signupSection').classList.add('active');
        document.getElementById('createSection').classList.remove('active');
    } else {
        // Default view (no startapp): Open organizer creation panel & check admin chats
        document.getElementById('tabSwitcher').style.display = 'flex';
        document.getElementById('signupSection').classList.remove('active');
        document.getElementById('createSection').classList.add('active');

        const select = document.getElementById('chatSelect');
        try {
            const adminChats = await apiFetch('/api/groups/admin-chats');
            if (adminChats && adminChats.length > 0) {
                if (select) {
                    select.innerHTML = '';
                    adminChats.forEach(chat => {
                        const opt = document.createElement('option');
                        opt.value = chat.id;
                        opt.textContent = chat.title;
                        select.appendChild(opt);
                    });
                }
            } else {
                if (select) {
                    select.innerHTML = '<option value="">Нет групп, где вы админ и бот добавлен</option>';
                }
                console.warn("User has no admin chats where bot is active.");
            }
        } catch (e) {
            console.error("Failed to load admin chats:", e);
            if (select) {
                select.innerHTML = `<option value="">Ошибка загрузки групп (${e.message})</option>`;
            }
        }
    }
}
