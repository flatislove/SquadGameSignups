import { tg } from './tg.js';
import { apiFetch } from './api.js';

export async function initRouter() {
    const urlParams = new URLSearchParams(window.location.search);
    const startParam = tg.initDataUnsafe?.start_param || urlParams.get('startapp');

    // Always keep tabSwitcher visible
    const tabSwitcher = document.getElementById('tabSwitcher');
    if (tabSwitcher) {
        tabSwitcher.style.display = 'flex';
    }

    const hasGameParam = Boolean(startParam && startParam.startsWith('game_'));
    if (hasGameParam) {
        window.CURRENT_GAME_ID = startParam.slice('game_'.length).trim();
    } else {
        delete window.CURRENT_GAME_ID;
    }

    const signupSection = document.getElementById('signupSection');
    const createSection = document.getElementById('createSection');
    const tabButtons = document.querySelectorAll('#tabSwitcher .tab-btn');

    if (hasGameParam && window.CURRENT_GAME_ID) {
        signupSection?.classList.add('active');
        createSection?.classList.remove('active');
        tabButtons[0]?.classList.add('active');
        tabButtons[1]?.classList.remove('active');
    } else {
        signupSection?.classList.remove('active');
        createSection?.classList.add('active');
        tabButtons[0]?.classList.remove('active');
        tabButtons[1]?.classList.add('active');
    }

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