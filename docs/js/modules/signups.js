import { tg } from '../core/tg.js';
import { apiFetch } from '../core/api.js';

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function safeUrl(url) {
    const raw = String(url ?? '').trim();
    return /^https?:\/\//i.test(raw) ? raw : '';
}

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
        form: document.getElementById('playerForm'),
        refreshBtn: document.getElementById('refresh-btn'),
        openModalBtn: document.getElementById('open-add-player-modal'),
        closeModalBtn: document.getElementById('close-player-modal'),
        modalUserName: document.getElementById('modalUserName'),
        modalUserPhone: document.getElementById('modalUserPhone')
    };

    let gameId = window.CURRENT_GAME_ID;

    async function loadData() {
        if (!gameId) {
            try {
                const latest = await apiFetch('/api/games/latest');
                if (!latest || !latest.id) {
                    if (refs.details) refs.details.textContent = '📅 Пока нет активных игр.';
                    if (refs.status) refs.status.style.display = 'none';
                    if (refs.players) refs.players.innerHTML = '';
                    return;
                }
                gameId = latest.id;
                window.CURRENT_GAME_ID = gameId;
            } catch (e) {
                console.error('Ошибка получения активной игры:', e);
                if (refs.details) {
                    refs.details.textContent = e?.status === 404
                        ? '📅 Пока нет активных игр.'
                        : `❌ Не удалось загрузить игру: ${e?.message || 'ошибка сети'}`;
                }
                if (refs.status) refs.status.style.display = 'none';
                return;
            }
        }

        try {
            const data = await apiFetch(`/api/signups/status?game_id=${encodeURIComponent(gameId)}`);
            const game = data.game || {};
            const link = safeUrl(game.loc_link);
            const locName = escapeHtml(game.loc_name || 'Площадка');

            if (refs.details) {
                const locationHtml = link
                    ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">${locName}</a>`
                    : locName;

                refs.details.innerHTML = `
                    <b>📅:</b> ${escapeHtml(game.date || '—')} (${escapeHtml(game.time_start || '—')}-${escapeHtml(game.time_end || '—')})<br>
                    <b>📍:</b> ${locationHtml}<br>
                    <b>💰:</b> ${escapeHtml(game.cost || '—')} | <b>👤:</b> ${escapeHtml(game.org_name || '—')}
                `;
            }

            if (refs.status) refs.status.style.display = 'block';
            if (refs.statusText) refs.statusText.innerText = data.message || '';
            if (refs.payment) {
                refs.payment.innerText = `Основной: ${data.main_count ?? 0}/${data.max_players ?? 0} | Резерв: ${data.reserve_count ?? 0}`;
            }

            if (refs.action) {
                refs.action.style.display = data.status === 'not_registered' ? 'block' : 'none';
                refs.action.onclick = async () => {
                    try {
                        const res = await apiFetch('/api/signups', {
                            method: 'POST',
                            body: JSON.stringify({ game_id: gameId })
                        });
                        if (res?.success && tg?.showAlert) {
                            tg.showAlert(`✅ Вы записаны (${res.status === 'main' ? 'Основной состав' : 'Резерв'})!`);
                        }
                        await loadData();
                    } catch (err) {
                        console.error('Ошибка записи:', err);
                        if (tg?.showAlert) tg.showAlert(`❌ Ошибка записи: ${err.message}`);
                    }
                };
            }

            if (refs.cancel) {
                refs.cancel.style.display = data.status !== 'not_registered' ? 'block' : 'none';
                refs.cancel.onclick = async () => {
                    try {
                        await apiFetch(`/api/signups?game_id=${encodeURIComponent(gameId)}`, { method: 'DELETE' });
                        await loadData();
                    } catch (err) {
                        console.error('Ошибка отмены записи:', err);
                        if (tg?.showAlert) tg.showAlert(`❌ Ошибка отмены: ${err.message}`);
                    }
                };
            }

            if (refs.adminPanel) {
                refs.adminPanel.style.display = data.is_admin ? 'block' : 'none';
            }

            renderPlayers(data);
        } catch (e) {
            console.error('Ошибка загрузки статуса записи:', e);
            if (refs.details) {
                refs.details.textContent = `❌ Ошибка загрузки состава: ${e?.message || 'неизвестная ошибка'}`;
            }
            if (refs.players) refs.players.innerHTML = '';
        }
    }

    function renderPlayers(data) {
        if (!refs.players) return;
        refs.players.innerHTML = '';

        let mainIndex = 0;
        (data.signups || []).forEach((s) => {
            const item = document.createElement('div');
            item.className = 'player-item';
            const badge = s.status === 'main' ? `#${++mainIndex}` : 'Рез';
            const adminHtml = data.is_admin
                ? `<div style="display: flex; gap: 4px;">
                    <button class="btn-secondary btn-sm toggle-pay" data-id="${escapeHtml(s.id)}" data-paid="${!s.is_paid}">${s.is_paid ? '❌' : '💰'}</button>
                    <button class="btn-danger btn-sm remove-signup" data-id="${escapeHtml(s.id)}">🗑</button>
                </div>`
                : '';

            item.innerHTML = `<div>${badge} <b>${escapeHtml(s.user_name)}</b> ${s.is_paid ? '✅' : ''}</div> ${adminHtml}`;
            refs.players.appendChild(item);
        });

        refs.players.querySelectorAll('.toggle-pay').forEach((btn) => {
            btn.onclick = async () => {
                try {
                    await apiFetch(`/api/signups/${encodeURIComponent(btn.dataset.id)}/pay`, {
                        method: 'PATCH',
                        body: JSON.stringify({ is_paid: btn.dataset.paid === 'true' })
                    });
                    await loadData();
                } catch (err) {
                    console.error('Ошибка смены статуса оплаты:', err);
                }
            };
        });

        refs.players.querySelectorAll('.remove-signup').forEach((btn) => {
            btn.onclick = async () => {
                try {
                    await apiFetch(`/api/signups/${encodeURIComponent(btn.dataset.id)}/admin-remove`, {
                        method: 'DELETE'
                    });
                    await loadData();
                } catch (err) {
                    console.error('Ошибка удаления игрока:', err);
                }
            };
        });
    }

    if (refs.refreshBtn) refs.refreshBtn.onclick = loadData;
    if (refs.openModalBtn && refs.modal) {
        refs.openModalBtn.onclick = () => { refs.modal.style.display = 'flex'; };
    }
    if (refs.closeModalBtn && refs.modal) {
        refs.closeModalBtn.onclick = () => { refs.modal.style.display = 'none'; };
    }

    if (refs.form) {
        refs.form.onsubmit = async (e) => {
            e.preventDefault();
            try {
                await apiFetch('/api/signups/admin-add', {
                    method: 'POST',
                    body: JSON.stringify({
                        game_id: gameId,
                        user_id: Date.now(),
                        user_name: refs.modalUserName ? refs.modalUserName.value : '',
                        user_phone: refs.modalUserPhone ? refs.modalUserPhone.value : ''
                    })
                });
                if (refs.modal) refs.modal.style.display = 'none';
                await loadData();
            } catch (err) {
                console.error('Ошибка добавления игрока:', err);
                if (tg?.showAlert) tg.showAlert(`❌ Не удалось добавить игрока: ${err.message}`);
            }
        };
    }

    await loadData();
}