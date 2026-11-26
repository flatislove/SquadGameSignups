import { tg } from '../core/tg.js';
import { apiFetch } from '../core/api.js';

export async function initSignups() {
    const gameId = window.CURRENT_GAME_ID;
    const gameDetailsEl = document.getElementById('game-details');
    const statusContainer = document.getElementById('status-container');
    const statusText = document.getElementById('status-text');
    const paymentText = document.getElementById('payment-text');
    const actionBtn = document.getElementById('action-btn');
    const cancelBtn = document.getElementById('cancel-btn');
    const copyLinkBtn = document.getElementById('copy-link-btn');
    const refreshBtn = document.getElementById('refresh-btn');
    const playersContainer = document.getElementById('players-container');
    const totalCountEl = document.getElementById('total-count');
    const maxCountEl = document.getElementById('max-count');
    const adminPanelContainer = document.getElementById('admin-panel-container');
    const openAddPlayerModalBtn = document.getElementById('open-add-player-modal');
    
    const playerModal = document.getElementById('playerModal');
    const closePlayerModalBtn = document.getElementById('close-player-modal');
    const playerForm = document.getElementById('playerForm');
    const modalTitle = document.getElementById('modal-title');
    const modalUserId = document.getElementById('modalUserId');
    const modalUserName = document.getElementById('modalUserName');
    const modalUserPhone = document.getElementById('modalUserPhone');

    if (!gameId) {
        if (gameDetailsEl) gameDetailsEl.innerHTML = "⚠️ Не указан ID игры в ссылке startapp.";
        return;
    }

    try {
        const data = await apiFetch(`/api/signups/status?game_id=${gameId}`);
        
        if (statusContainer) statusContainer.style.display = 'block';
        if (statusText) statusText.innerText = data.message;
        if (paymentText) paymentText.innerText = `Основной состав: ${data.main_count}/${data.max_players} | Резерв: ${data.reserve_count}`;

        if (actionBtn) {
            if (data.status === 'not_registered') {
                actionBtn.style.display = 'block';
                actionBtn.innerText = 'Записаться';
                actionBtn.onclick = async () => {
                    try {
                        const res = await apiFetch('/api/signups', {
                            method: 'POST',
                            body: JSON.stringify({ game_id: gameId })
                        });
                        if (res.success) {
                            tg.showAlert(`✅ Вы успешно записаны (${res.status === 'main' ? 'Основной состав' : 'Резерв'})!`);
                            initSignups();
                        }
                    } catch (err) {
                        tg.showAlert(`❌ Ошибка записи: ${err.message}`);
                    }
                };
            } else {
                actionBtn.style.display = 'none';
            }
        }
    } catch (e) {
        console.error("Error fetching signup status:", e);
        if (userInfoEl) userInfoEl.innerText = "❌ Ошибка загрузки данных игры.";
    }
}
