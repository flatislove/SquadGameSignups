import { tg } from '../core/tg.js';
import { apiFetch } from '../core/api.js';

export async function initSignups() {
    const refs = {
        details: document.getElementById('game-details'),
        status: document.getElementById('status-container'),
        statusText: document.getElementById('status-text'),
        payment: document.getElementById('payment-text'),
        action: document.getElementById('action-btn'),
        cancel: document.getElementById('cancel-btn'),
        players: document.getElementById('players-container'),
        adminPanel: document.getElementById('admin-panel-container'),
        modal: document.getElementById('playerModal'),
        form: document.getElementById('playerForm')
    };

    let gameId = window.CURRENT_GAME_ID;

    async function loadData() {
        if (!gameId) {
            try {
                const latest = await apiFetch('/api/games/latest');
                gameId = latest.id;
                window.CURRENT_GAME_ID = gameId;
            } catch (e) {
                if (refs.details) refs.details.innerHTML = "📅 Пока нет активных игр.";
                if (refs.status) refs.status.style.display = 'none';
                return;
            }
        }

        try {
            const data = await apiFetch(`/api/signups/status?game_id=${gameId}`);
            const game = data.game || {};
            
            if (refs.details) {
                refs.details.innerHTML = `
                    <b>📅:</b> ${game.date} (${game.time_start}-${game.time_end})<br>
                    <b>📍:</b> <a href="${game.loc_link}">${game.loc_name}</a><br>
                    <b>💰:</b> ${game.cost} | <b>👤:</b> ${game.org_name}
                `;
            }
            if (refs.status) refs.status.style.display = 'block';
            if (refs.statusText) refs.statusText.innerText = data.message;
            if (refs.payment) refs.payment.innerText = `Основной: ${data.main_count}/${data.max_players} | Резерв: ${data.reserve_count}`;

            // Buttons
            refs.action.style.display = data.status === 'not_registered' ? 'block' : 'none';
            refs.cancel.style.display = data.status !== 'not_registered' ? 'block' : 'none';
            refs.action.onclick = async () => {
                await apiFetch('/api/signups', { method: 'POST', body: JSON.stringify({ game_id: gameId }) });
                loadData();
            };
            refs.cancel.onclick = async () => {
                await apiFetch(`/api/signups?game_id=${gameId}`, { method: 'DELETE' });
                loadData();
            };

            // Admin
            refs.adminPanel.style.display = data.is_admin ? 'block' : 'none';
            renderPlayers(data);
        } catch (e) { console.error(e); }
    }

    function renderPlayers(data) {
        refs.players.innerHTML = '';
        (data.signups || []).forEach((s, index) => {
            const item = document.createElement('div');
            item.className = 'player-item';
            let adminHtml = data.is_admin ? `<div style="display: flex; gap: 4px;">
                <button class="btn-secondary btn-sm toggle-pay" data-id="${s.id}" data-paid="${!s.is_paid}">${s.is_paid ? '❌' : '💰'}</button>
                <button class="btn-danger btn-sm remove-signup" data-id="${s.id}">🗑</button>
            </div>` : '';
            item.innerHTML = `<div>${s.status === 'main' ? '#' + (index + 1) : 'Рез'} <b>${s.user_name}</b> ${s.is_paid ? '✅' : ''}</div> ${adminHtml}`;
            refs.players.appendChild(item);
        });

        refs.players.querySelectorAll('.toggle-pay').forEach(btn => btn.onclick = async () => {
            await apiFetch(`/api/signups/${btn.dataset.id}/pay`, { method: 'PATCH', body: JSON.stringify({ is_paid: btn.dataset.paid === 'true' }) });
            loadData();
        });
        refs.players.querySelectorAll('.remove-signup').forEach(btn => btn.onclick = async () => {
            await apiFetch(`/api/signups/${btn.dataset.id}/admin-remove`, { method: 'DELETE' });
            loadData();
        });
    }

    document.getElementById('refresh-btn').onclick = loadData;
    document.getElementById('open-add-player-modal').onclick = () => refs.modal.style.display = 'flex';
    document.getElementById('close-player-modal').onclick = () => refs.modal.style.display = 'none';
    
    refs.form.onsubmit = async (e) => {
        e.preventDefault();
        await apiFetch('/api/signups/admin-add', { method: 'POST', body: JSON.stringify({ game_id: gameId, user_id: Date.now(), user_name: document.getElementById('modalUserName').value, user_phone: document.getElementById('modalUserPhone').value }) });
        refs.modal.style.display = 'none';
        loadData();
    };

    await loadData();
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
