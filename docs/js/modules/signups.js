import { tg } from '../core/tg.js';
import { apiFetch } from '../core/api.js';

export async function initSignups() {
    const gameId = window.CURRENT_GAME_ID;
    const userInfoEl = document.getElementById('user-info');
    const statusContainer = document.getElementById('status-container');
    const statusText = document.getElementById('status-text');
    const paymentText = document.getElementById('payment-text');
    const actionBtn = document.getElementById('action-btn');

    if (!gameId) {
        if (userInfoEl) userInfoEl.innerText = "⚠️ Не указан ID игры в ссылке startapp.";
        return;
    }

    const user = tg.initDataUnsafe?.user || { first_name: "Игрок" };
    if (userInfoEl) userInfoEl.innerText = `Привет, ${user.first_name || 'Игрок'}!`;

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
