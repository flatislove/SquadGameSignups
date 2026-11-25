import { tg } from './tg.js';
import { apiFetch } from './api.js';

export async function initRouter() {
    const urlParams = new URLSearchParams(window.location.search);
    // Telegram WebApp startapp parameter can be accessed via tg.initDataUnsafe?.start_param or url query
    const startParam = tg.initDataUnsafe?.start_param || urlParams.get('startapp');

    console.log("WebApp start_param:", startParam);

    if (startParam && startParam.startsWith('game_')) {
        const gameId = startParam.replace('game_', '');
        // Switch to signup view for specific game
        window.CURRENT_GAME_ID = gameId;
        document.getElementById('tabSwitcher').style.display = 'none';
        document.getElementById('signupSection').classList.add('active');
        document.getElementById('createSection').classList.remove('active');
    } else {
        // Default view: check if user is admin to show tabs
        try {
            const adminChats = await apiFetch('/api/groups/admin-chats');
            if (adminChats && adminChats.length > 0) {
                document.getElementById('tabSwitcher').style.display = 'flex';
                // Populate chat select
                const select = document.getElementById('chatSelect');
                if (select) {
                    select.innerHTML = '';
                    adminChats.forEach(chat => {
                        const opt = document.createElement('option');
                        opt.value = chat.id;
                        opt.textContent = chat.title;
                        select.appendChild(opt);
                    });
                }
            }
        } catch (e) {
            console.error("Failed to load admin chats:", e);
        }
    }
}
