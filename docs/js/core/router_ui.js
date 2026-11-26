import { tg } from './tg.js';
import { apiFetch } from './api.js';

export async function initRouter() {
    const urlParams = new URLSearchParams(window.location.search);
    const startParam = tg.initDataUnsafe?.start_param || urlParams.get('startapp');

    // Always keep tabSwitcher visible
    document.getElementById('tabSwitcher').style.display = 'flex';

    if (startParam && startParam.startsWith('game_')) {
        window.CURRENT_GAME_ID = startParam.replace('game_', '');
    }
    
    // Default to signup section if no specific game or create tab requested
    document.getElementById('signupSection').classList.add('active');
    document.getElementById('createSection').classList.remove('active');

    // Load admin chats in background for the create tab
    const select = document.getElementById('chatSelect');
    try {
        const adminChats = await apiFetch('/api/groups/admin-chats');
        if (select) {
            if (adminChats && adminChats.length > 0) {
                select.innerHTML = adminChats.map(c => `<option value="${c.id}">${c.title}</option>`).join('');
            } else {
                select.innerHTML = '<option value="">Нет групп</option>';
            }
        }
    } catch (e) {
        console.error("Failed to load admin chats:", e);
        if (select) select.innerHTML = `<option value="">Ошибка загрузки</option>`;
    }
}
