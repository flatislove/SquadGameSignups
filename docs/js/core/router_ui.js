import { tg, getStartParam } from './tg.js';
import { apiFetch } from './api.js';

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function resolveGameId(urlParams) {
    const fromQuery = (urlParams.get('game_id') || '').trim();
    if (fromQuery) return fromQuery;

    const startParam = getStartParam() || (urlParams.get('startapp') || '').trim();
    if (startParam.startsWith('game_')) {
        const gameId = startParam.slice('game_'.length).trim();
        if (gameId) return gameId;
    }

    if (typeof window.CURRENT_GAME_ID === 'string' && window.CURRENT_GAME_ID.trim()) {
        return window.CURRENT_GAME_ID.trim();
    }

    return null;
}

export async function initRouter(options = {}) {
    const urlParams = new URLSearchParams(window.location.search);
    const gameId = options.gameId || resolveGameId(urlParams);
    const viewParam = options.view || (urlParams.get('view') || '').trim();

    const tabSwitcher = document.getElementById('tabSwitcher');
    if (tabSwitcher) {
        tabSwitcher.style.display = 'none';
    }

    const signupSection = document.getElementById('signupSection');
    const createSection = document.getElementById('createSection');

    if (gameId) {
        window.CURRENT_GAME_ID = gameId;
        signupSection?.classList.add('active');
        createSection?.classList.remove('active');
        return { mode: 'signup', gameId };
    }

    delete window.CURRENT_GAME_ID;

    const targetMode = viewParam === 'signup' ? 'signup' : 'create';
    signupSection?.classList.toggle('active', targetMode === 'signup');
    createSection?.classList.toggle('active', targetMode === 'create');

    if (targetMode === 'create') {
        const select = document.getElementById('chatSelect');
        try {
            const adminChats = await apiFetch('/api/groups/admin-chats');
            if (select) {
                if (Array.isArray(adminChats) && adminChats.length > 0) {
                    select.innerHTML = adminChats
                        .map(c => `<option value="${escapeHtml(c.id)}">${escapeHtml(c.title)}</option>`)
                        .join('');

                    const savedChatId = localStorage.getItem('activeChatId');
                    if (savedChatId && adminChats.some(c => String(c.id) === String(savedChatId))) {
                        select.value = savedChatId;
                    } else if (select.value) {
                        localStorage.setItem('activeChatId', select.value);
                    }

                    select.onchange = () => {
                        if (select.value) {
                            localStorage.setItem('activeChatId', select.value);
                        } else {
                            localStorage.removeItem('activeChatId');
                        }
                        window.dispatchEvent(new CustomEvent('activeChatChanged', { detail: { chatId: select.value } }));
                    };
                } else {
                    select.innerHTML = '<option value="">Нет групп</option>';
                    localStorage.removeItem('activeChatId');
                }
            }
        } catch (e) {
            console.error('Failed to load admin chats:', e);
            if (select) select.innerHTML = '<option value="">Ошибка загрузки</option>';
        }
    }

    return { mode: targetMode, gameId: null };
}