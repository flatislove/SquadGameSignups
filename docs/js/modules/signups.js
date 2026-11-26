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

function formatPlayerDisplayName(rawName) {
    const cleaned = String(rawName ?? '').trim();
    if (!cleaned || /^\d+$/.test(cleaned)) {
        return 'Участник';
    }
    return cleaned;
}

function resolveAnnouncementGameId() {
    if (window.CURRENT_GAME_ID) {
        return String(window.CURRENT_GAME_ID);
    }

    const startParam = tg?.initDataUnsafe?.start_param;
    if (typeof startParam === 'string' && startParam.startsWith('game_')) {
        const parsedId = startParam.slice('game_'.length).trim();
        if (parsedId) {
            window.CURRENT_GAME_ID = parsedId;
            return parsedId;
        }
    }

    return null;
}

export async function initSignups() {
    const refs = {
        details: document.getElementById('game-details'),
        status: document.getElementById('status-container'),
        statusText: document.getElementById('status-text'),
        payment: document.getElementById('payment-text'),
        action: document.getElementById('action-btn'),
        cancel: document.getElementById('cancel-btn'),
        confirmPaymentBtn: document.getElementById('confirm-payment-btn'),
        totalCount: document.getElementById('total-count'),
        maxCount: document.getElementById('max-count'),
        players: document.getElementById('players-container'),
        adminPanel: document.getElementById('admin-panel-container'),
        modal: document.getElementById('playerModal'),
        modalTitle: document.getElementById('playerModalTitle'),
        tabDbPlayers: document.getElementById('tab-db-players'),
        tabNewPlayer: document.getElementById('tab-new-player'),
        dbPlayersPane: document.getElementById('dbPlayersPane'),
        newPlayerPane: document.getElementById('newPlayerPane'),
        playerSearchInput: document.getElementById('playerSearchInput'),
        dbSelectIsPaid: document.getElementById('dbSelectIsPaid'),
        dbPlayersList: document.getElementById('dbPlayersList'),
        closeModalDbBtn: document.getElementById('close-player-modal-db'),
        form: document.getElementById('playerForm'),
        openModalBtn: document.getElementById('open-add-player-modal'),
        closeModalBtn: document.getElementById('close-player-modal'),
        editPlayerId: document.getElementById('editPlayerId'),
        modalUserName: document.getElementById('modalUserName'),
        modalUserGender: document.getElementById('modalUserGender'),
        modalTelegramId: document.getElementById('modalTelegramId'),
        modalTelegramUsername: document.getElementById('modalTelegramUsername'),
        addToMatchOptionGroup: document.getElementById('addToMatchOptionGroup'),
        modalAddToMatch: document.getElementById('modalAddToMatch'),
        modalIsPaidGroup: document.getElementById('modalIsPaidGroup'),
        modalIsPaid: document.getElementById('modalIsPaid'),
        receiptModal: document.getElementById('receiptModal'),
        receiptFileInput: document.getElementById('receiptFileInput'),
        submitReceiptBtn: document.getElementById('submit-receipt-btn'),
        closeReceiptModalBtn: document.getElementById('close-receipt-modal')
    };

    let gameId = resolveAnnouncementGameId();
    let cachedDbPlayers = [];
    let currentGameMeta = { mainCount: 0, reserveCount: 0, maxPlayers: 0 };

    function updatePaymentSummaryText() {
        if (!refs.payment || !refs.players) return;
        const paidCount = refs.players.querySelectorAll('.player-name-paid').length;
        refs.payment.innerText = `Основной: ${currentGameMeta.mainCount}/${currentGameMeta.maxPlayers} | Резерв: ${currentGameMeta.reserveCount} | Оплатили: ${paidCount}`;
    }

    function applyRowPaymentState(btn, isPaid) {
        const nextIsPaid = Boolean(isPaid);
        btn.dataset.paid = String(!nextIsPaid);
        btn.textContent = nextIsPaid ? '↩️' : '💳';

        const row = btn.closest('.player-item');
        const nameEl = row?.querySelector('.player-info > span:last-child');
        if (nameEl) {
            nameEl.classList.toggle('player-name-paid', nextIsPaid);
            nameEl.classList.toggle('player-name-unpaid', !nextIsPaid);
        }

        updatePaymentSummaryText();
    }

    function switchModalMode(mode) {
        const isDb = mode === 'db';
        if (refs.tabDbPlayers) refs.tabDbPlayers.classList.toggle('active', isDb);
        if (refs.tabNewPlayer) refs.tabNewPlayer.classList.toggle('active', !isDb);
        if (refs.dbPlayersPane) refs.dbPlayersPane.style.display = isDb ? 'block' : 'none';
        if (refs.newPlayerPane) refs.newPlayerPane.style.display = isDb ? 'none' : 'block';
    }

    function openNewPlayerForm(playerToEdit = null) {
        switchModalMode('new');
        if (playerToEdit) {
            if (refs.modalTitle) refs.modalTitle.textContent = 'Редактировать игрока';
            if (refs.editPlayerId) refs.editPlayerId.value = playerToEdit.id || '';
            if (refs.modalUserName) refs.modalUserName.value = playerToEdit.name || '';
            if (refs.modalUserGender) refs.modalUserGender.value = playerToEdit.gender || 'male';
            if (refs.modalTelegramId) refs.modalTelegramId.value = playerToEdit.telegram_id ?? '';
            if (refs.modalTelegramUsername) {
                refs.modalTelegramUsername.value = playerToEdit.telegram_username
                    ? `@${String(playerToEdit.telegram_username).replace(/^@/, '')}`
                    : '';
            }
            if (refs.addToMatchOptionGroup) refs.addToMatchOptionGroup.style.display = 'none';
            if (refs.modalIsPaidGroup) refs.modalIsPaidGroup.style.display = 'none';
        } else {
            if (refs.modalTitle) refs.modalTitle.textContent = 'Новый игрок';
            if (refs.editPlayerId) refs.editPlayerId.value = '';
            if (refs.modalUserName) refs.modalUserName.value = '';
            if (refs.modalUserGender) refs.modalUserGender.value = 'male';
            if (refs.modalTelegramId) refs.modalTelegramId.value = '';
            if (refs.modalTelegramUsername) refs.modalTelegramUsername.value = '';
            if (refs.addToMatchOptionGroup) refs.addToMatchOptionGroup.style.display = 'block';
            if (refs.modalAddToMatch) refs.modalAddToMatch.checked = true;
            if (refs.modalIsPaidGroup) refs.modalIsPaidGroup.style.display = 'block';
            if (refs.modalIsPaid) refs.modalIsPaid.value = 'false';
        }
    }

    function renderDbPlayersList(query = '') {
        if (!refs.dbPlayersList) return;
        const q = query.trim().toLowerCase();

        const sorted = [...cachedDbPlayers].sort((a, b) =>
            String(a.name || '').localeCompare(String(b.name || ''), 'ru', { sensitivity: 'base' })
        );

        const filtered = q
            ? sorted.filter((p) => {
                  const name = String(p.name || '').toLowerCase();
                  const uname = String(p.telegram_username || '').toLowerCase();
                  const tgId = String(p.telegram_id || '');
                  return name.includes(q) || uname.includes(q) || tgId.includes(q);
              })
            : sorted;

        if (filtered.length === 0) {
            refs.dbPlayersList.innerHTML =
                '<div style="color: gray; font-size: 13px; padding: 10px; text-align: center;">Игроки не найдены. Создайте нового во вкладке «Новый игрок».</div>';
            return;
        }

        refs.dbPlayersList.innerHTML = '';
        filtered.forEach((p) => {
            const row = document.createElement('div');
            row.className = 'db-player-row';

            const genderIcon = p.gender === 'female' ? '👩' : '👨';
            const metaParts = [];
            if (p.telegram_username) metaParts.push(`@${escapeHtml(p.telegram_username)}`);
            if (p.telegram_id) metaParts.push(`ID: ${escapeHtml(p.telegram_id)}`);
            if (metaParts.length === 0) metaParts.push('TG не привязан');

            row.innerHTML = `
                <div style="overflow: hidden;">
                    <div style="font-weight: 600;">${genderIcon} ${escapeHtml(p.name)}</div>
                    <div class="db-player-meta">${metaParts.join(' • ')}</div>
                </div>
                <div style="display: flex; gap: 4px; flex-shrink: 0;">
                    <button type="button" class="btn-secondary btn-sm edit-db-player" data-id="${escapeHtml(p.id)}" title="Редактировать">✏️</button>
                    <button type="button" class="btn-sm add-db-player" data-id="${escapeHtml(p.id)}">➕</button>
                </div>
            `;
            refs.dbPlayersList.appendChild(row);
        });

        refs.dbPlayersList.querySelectorAll('.edit-db-player').forEach((btn) => {
            btn.onclick = () => {
                const target = cachedDbPlayers.find((item) => String(item.id) === String(btn.dataset.id));
                if (target) openNewPlayerForm(target);
            };
        });

        refs.dbPlayersList.querySelectorAll('.add-db-player').forEach((btn) => {
            btn.onclick = async () => {
                if (!gameId) return;
                btn.disabled = true;
                try {
                    await apiFetch('/api/signups/admin-add', {
                        method: 'POST',
                        body: JSON.stringify({
                            game_id: gameId,
                            player_id: btn.dataset.id,
                            is_paid: Boolean(refs.dbSelectIsPaid?.checked)
                        })
                    });
                    if (refs.modal) refs.modal.style.display = 'none';
                    await loadData();
                } catch (err) {
                    console.error('Ошибка добавления игрока из базы:', err);
                    if (tg?.showAlert) tg.showAlert(`❌ ${err.message}`);
                } finally {
                    btn.disabled = false;
                }
            };
        });
    }

    async function loadDbPlayers() {
        if (!refs.dbPlayersList) return;
        refs.dbPlayersList.innerHTML = '<div style="color: gray; font-size: 13px; padding: 10px;">Загрузка...</div>';
        try {
            const res = await apiFetch('/api/signups/players');
            cachedDbPlayers = Array.isArray(res?.players) ? res.players : [];
            renderDbPlayersList(refs.playerSearchInput?.value || '');
        } catch (err) {
            console.error('Ошибка загрузки базы игроков:', err);
            refs.dbPlayersList.innerHTML = `<div style="color: #d9534f; font-size: 13px; padding: 10px;">Ошибка загрузки базы: ${escapeHtml(err.message)}</div>`;
        }
    }

    async function loadData() {
        gameId = resolveAnnouncementGameId();

        if (!gameId) {
            if (refs.details) {
                refs.details.textContent = 'ℹ️ Чтобы открыть матч, нажмите кнопку «Запись» под анонсом в группе.';
            }
            if (refs.status) refs.status.style.display = 'none';
            if (refs.action) refs.action.style.display = 'none';
            if (refs.cancel) refs.cancel.style.display = 'none';
            if (refs.confirmPaymentBtn) refs.confirmPaymentBtn.style.display = 'none';
            if (refs.adminPanel) refs.adminPanel.style.display = 'none';
            if (refs.players) refs.players.innerHTML = '';
            if (refs.totalCount) refs.totalCount.textContent = '0';
            if (refs.maxCount) refs.maxCount.textContent = '0';
            return;
        }

        if (refs.confirmPaymentBtn) refs.confirmPaymentBtn.style.display = 'block';

        try {
            const data = await apiFetch(`/api/signups/status?game_id=${encodeURIComponent(gameId)}`);
            const game = data.game || {};
            const link = safeUrl(game.loc_link);
            const locName = escapeHtml(game.loc_name || 'Площадка');

            currentGameMeta = {
                mainCount: data.main_count ?? 0,
                reserveCount: data.reserve_count ?? 0,
                maxPlayers: data.max_players ?? 0
            };

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

            const signupsList = Array.isArray(data.signups) ? data.signups : [];
            const paidCount = signupsList.filter((s) => Boolean(s.is_paid)).length;
            if (refs.payment) {
                refs.payment.innerText = `Основной: ${currentGameMeta.mainCount}/${currentGameMeta.maxPlayers} | Резерв: ${currentGameMeta.reserveCount} | Оплатили: ${paidCount}`;
            }

            if (refs.totalCount) {
                refs.totalCount.textContent = String(signupsList.length);
            }
            if (refs.maxCount) {
                refs.maxCount.textContent = String(currentGameMeta.maxPlayers);
            }

            if (refs.action) {
                refs.action.style.display = data.status === 'not_registered' ? 'block' : 'none';
                refs.action.onclick = async () => {
                    refs.action.disabled = true;
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
                    } finally {
                        refs.action.disabled = false;
                    }
                };
            }

            if (refs.cancel) {
                refs.cancel.style.display = data.status !== 'not_registered' ? 'block' : 'none';
                refs.cancel.onclick = async () => {
                    refs.cancel.disabled = true;
                    try {
                        await apiFetch(`/api/signups?game_id=${encodeURIComponent(gameId)}`, { method: 'DELETE' });
                        await loadData();
                    } catch (err) {
                        console.error('Ошибка отмены записи:', err);
                        if (tg?.showAlert) tg.showAlert(`❌ Ошибка отмены: ${err.message}`);
                    } finally {
                        refs.cancel.disabled = false;
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

        const list = Array.isArray(data.signups) ? data.signups : [];
        if (list.length === 0) {
            refs.players.innerHTML = '<div style="color: gray; font-size: 13px;">Пока никто не записался.</div>';
            return;
        }

        let mainIndex = 0;
        list.forEach((s) => {
            const item = document.createElement('div');
            item.className = 'player-item';
            const badge = s.status === 'main' ? `#${++mainIndex}` : 'Рез';
            const displayName = formatPlayerDisplayName(s.user_name);
            const paidClass = s.is_paid ? 'player-name-paid' : 'player-name-unpaid';

            const adminHtml = data.is_admin
                ? `<div style="display: flex; gap: 4px; flex-shrink: 0;">
                    <button class="btn-secondary btn-sm toggle-pay" data-id="${escapeHtml(s.id)}" data-paid="${!s.is_paid}" title="Подтвердить / снять оплату">${s.is_paid ? '↩️' : '💳'}</button>
                    <button class="btn-danger btn-sm remove-signup" data-id="${escapeHtml(s.id)}" title="Удалить из списка">🗑</button>
                </div>`
                : '';

            item.innerHTML = `
                <div class="player-info">
                    <span>${badge}</span>
                    <span class="${paidClass}">${escapeHtml(displayName)}</span>
                </div>
                ${adminHtml}
            `;
            refs.players.appendChild(item);
        });

        refs.players.querySelectorAll('.toggle-pay').forEach((btn) => {
            btn.onclick = async () => {
                if (btn.disabled) return;
                const targetIsPaid = btn.dataset.paid === 'true';
                btn.disabled = true;
                try {
                    const res = await apiFetch(`/api/signups/${encodeURIComponent(btn.dataset.id)}/pay`, {
                        method: 'PATCH',
                        body: JSON.stringify({ is_paid: targetIsPaid })
                    });
                    const confirmedIsPaid = typeof res?.is_paid === 'boolean' ? res.is_paid : targetIsPaid;
                    applyRowPaymentState(btn, confirmedIsPaid);
                } catch (err) {
                    console.error('Ошибка смены статуса оплаты:', err);
                    if (tg?.showAlert) tg.showAlert(`❌ Не удалось обновить оплату: ${err.message}`);
                } finally {
                    btn.disabled = false;
                }
            };
        });

        refs.players.querySelectorAll('.remove-signup').forEach((btn) => {
            btn.onclick = async () => {
                if (btn.disabled) return;
                btn.disabled = true;
                try {
                    await apiFetch(`/api/signups/${encodeURIComponent(btn.dataset.id)}/admin-remove`, {
                        method: 'DELETE'
                    });
                    await loadData();
                } catch (err) {
                    console.error('Ошибка удаления игрока:', err);
                    if (tg?.showAlert) tg.showAlert(`❌ Не удалось удалить игрока: ${err.message}`);
                } finally {
                    btn.disabled = false;
                }
            };
        });
    }

    if (refs.confirmPaymentBtn && refs.receiptModal) {
        refs.confirmPaymentBtn.onclick = () => {
            if (refs.receiptFileInput) refs.receiptFileInput.value = '';
            refs.receiptModal.style.display = 'flex';
        };
    }

    if (refs.closeReceiptModalBtn && refs.receiptModal) {
        refs.closeReceiptModalBtn.onclick = () => {
            refs.receiptModal.style.display = 'none';
        };
    }

    if (refs.submitReceiptBtn && refs.receiptModal) {
        refs.submitReceiptBtn.onclick = () => {
            const fileName = refs.receiptFileInput?.files?.[0]?.name;
            refs.receiptModal.style.display = 'none';
            const msg = fileName
                ? `Чек «${fileName}» выбран (загрузка пока без действий).`
                : 'Окно загрузки чека закрыто (загрузка пока без действий).';
            if (tg?.showAlert) {
                tg.showAlert(msg);
            } else {
                alert(msg);
            }
        };
    }

    if (refs.openModalBtn && refs.modal) {
        refs.openModalBtn.onclick = async () => {
            if (refs.modalTitle) refs.modalTitle.textContent = 'Добавить игрока';
            if (refs.playerSearchInput) refs.playerSearchInput.value = '';
            if (refs.dbSelectIsPaid) refs.dbSelectIsPaid.checked = false;
            switchModalMode('db');
            refs.modal.style.display = 'flex';
            await loadDbPlayers();
        };
    }

    if (refs.tabDbPlayers) {
        refs.tabDbPlayers.onclick = async () => {
            if (refs.modalTitle) refs.modalTitle.textContent = 'Добавить игрока';
            switchModalMode('db');
            await loadDbPlayers();
        };
    }

    if (refs.tabNewPlayer) {
        refs.tabNewPlayer.onclick = () => {
            openNewPlayerForm(null);
        };
    }

    if (refs.playerSearchInput) {
        refs.playerSearchInput.oninput = (e) => {
            renderDbPlayersList(e.target.value || '');
        };
    }

    if (refs.closeModalDbBtn && refs.modal) {
        refs.closeModalDbBtn.onclick = () => {
            refs.modal.style.display = 'none';
        };
    }

    if (refs.closeModalBtn && refs.modal) {
        refs.closeModalBtn.onclick = () => {
            refs.modal.style.display = 'none';
        };
    }

    if (refs.form) {
        refs.form.onsubmit = async (e) => {
            e.preventDefault();
            const editingId = refs.editPlayerId?.value?.trim();
            const rawTgId = refs.modalTelegramId?.value?.trim();
            const parsedTgId = rawTgId ? Number(rawTgId) : null;

            const playerPayload = {
                name: refs.modalUserName ? refs.modalUserName.value.trim() : '',
                gender: refs.modalUserGender ? refs.modalUserGender.value : 'male',
                telegram_id: Number.isFinite(parsedTgId) ? parsedTgId : null,
                telegram_username: refs.modalTelegramUsername ? refs.modalTelegramUsername.value.trim() : ''
            };

            try {
                if (editingId) {
                    await apiFetch(
                        `/api/signups/players/${encodeURIComponent(editingId)}?game_id=${encodeURIComponent(gameId || '')}`,
                        {
                            method: 'PATCH',
                            body: JSON.stringify(playerPayload)
                        }
                    );
                    if (tg?.showAlert) tg.showAlert('✅ Данные игрока обновлены!');
                    switchModalMode('db');
                    if (refs.modalTitle) refs.modalTitle.textContent = 'Добавить игрока';
                    await loadDbPlayers();
                    await loadData();
                    return;
                }

                const addToMatch = Boolean(refs.modalAddToMatch?.checked);
                if (addToMatch && gameId) {
                    await apiFetch('/api/signups/admin-add', {
                        method: 'POST',
                        body: JSON.stringify({
                            game_id: gameId,
                            ...playerPayload,
                            is_paid: refs.modalIsPaid ? refs.modalIsPaid.value === 'true' : false
                        })
                    });
                    if (refs.modal) refs.modal.style.display = 'none';
                    await loadData();
                } else {
                    await apiFetch('/api/signups/players', {
                        method: 'POST',
                        body: JSON.stringify(playerPayload)
                    });
                    if (tg?.showAlert) tg.showAlert('✅ Игрок сохранён в базу!');
                    switchModalMode('db');
                    if (refs.modalTitle) refs.modalTitle.textContent = 'Добавить игрока';
                    await loadDbPlayers();
                }
            } catch (err) {
                console.error('Ошибка сохранения/добавления игрока:', err);
                if (tg?.showAlert) tg.showAlert(`❌ ${err.message}`);
            }
        };
    }

    await loadData();
}