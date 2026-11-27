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

function formatUsername(rawUsername) {
    const cleaned = String(rawUsername ?? '').trim().replace(/^@+/, '');
    return cleaned ? `@${cleaned}` : 'Не указан';
}

function resolveAnnouncementGameId() {
    if (window.CURRENT_GAME_ID) {
        return String(window.CURRENT_GAME_ID).trim();
    }

    const searchParams = new URLSearchParams(window.location.search);
    const queryGameId = searchParams.get('game_id')?.trim();
    if (queryGameId) {
        window.CURRENT_GAME_ID = queryGameId;
        return queryGameId;
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

function ensurePlayerInfoModal() {
    let modal = document.getElementById('playerInfoPopup');
    if (modal) return modal;

    modal = document.createElement('div');
    modal.id = 'playerInfoPopup';
    modal.className = 'modal';
    modal.style.display = 'none';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 340px;">
            <h3 style="margin-top: 0; margin-bottom: 12px;">Информация об игроке</h3>
            <div style="font-size: 14px; line-height: 1.6; margin-bottom: 14px;">
                <div><b>Имя:</b> <span id="popupPlayerName">—</span></div>
                <div><b>Telegram:</b> <span id="popupPlayerUsername">—</span></div>
            </div>
            <button type="button" id="closePlayerInfoPopup" class="btn-secondary" style="margin-top: 0;">Закрыть</button>
        </div>
    `;

    document.body.appendChild(modal);

    modal.addEventListener('click', (e) => {
        if (e.target === modal || e.target.id === 'closePlayerInfoPopup') {
            modal.style.display = 'none';
        }
    });

    return modal;
}

function openPlayerInfoPopup(player) {
    const modal = ensurePlayerInfoModal();
    const nameEl = modal.querySelector('#popupPlayerName');
    const unameEl = modal.querySelector('#popupPlayerUsername');

    if (nameEl) nameEl.textContent = formatPlayerDisplayName(player.user_name || player.name);
    if (unameEl) unameEl.textContent = formatUsername(player.telegram_username || player.username);

    modal.style.display = 'flex';
}

function normalizeRoster(signupsList, maxPlayers) {
    const rawList = Array.isArray(signupsList) ? [...signupsList] : [];
    const limit = Number.isFinite(Number(maxPlayers)) && Number(maxPlayers) > 0
        ? Number(maxPlayers)
        : rawList.length;

    const explicitlyMain = rawList.filter((item) => item.status === 'main');
    const explicitlyReserve = rawList.filter((item) => item.status === 'reserve');
    const otherItems = rawList.filter((item) => item.status !== 'main' && item.status !== 'reserve');

    const mainList = [...explicitlyMain];
    const reserveList = [...explicitlyReserve];

    for (const item of otherItems) {
        if (mainList.length < limit) {
            mainList.push({ ...item, status: 'main' });
        } else {
            reserveList.push({ ...item, status: 'reserve' });
        }
    }

    while (mainList.length < limit && reserveList.length > 0) {
        const promoted = reserveList.shift();
        mainList.push({ ...promoted, status: 'main' });
    }

    return {
        main: mainList.map((p) => ({ ...p, status: 'main' })),
        reserve: reserveList.map((p) => ({ ...p, status: 'reserve' }))
    };
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
        receiptModal: document.getElementById('receiptModal'),
        receiptFileInput: document.getElementById('receiptFileInput'),
        submitReceiptBtn: document.getElementById('submit-receipt-btn'),
        closeReceiptModalBtn: document.getElementById('close-receipt-modal')
    };

    if (refs.confirmPaymentBtn) {
        refs.confirmPaymentBtn.style.display = 'none';
    }
    if (refs.adminPanel) {
        refs.adminPanel.style.display = 'none';
    }

    let gameId = resolveAnnouncementGameId();
    let currentGameId = gameId;
    let currentUserState = {
        status: 'not_registered',
        isPaid: false,
        signupId: null
    };

    let paymentIconBtn = document.getElementById('header-payment-icon-btn');
    if (!paymentIconBtn && refs.cancel?.parentElement) {
        paymentIconBtn = document.createElement('button');
        paymentIconBtn.type = 'button';
        paymentIconBtn.id = 'header-payment-icon-btn';
        paymentIconBtn.title = 'Статус оплаты';
        paymentIconBtn.style.cssText = [
            'flex: 0 0 46px',
            'width: 46px',
            'height: 42px',
            'padding: 0',
            'margin-top: 0',
            'display: inline-flex',
            'align-items: center',
            'justify-content: center',
            'font-size: 18px',
            'border-radius: 8px'
        ].join(';');
        refs.cancel.parentElement.appendChild(paymentIconBtn);
    }

    function syncPaymentIcon() {
        if (!paymentIconBtn) return;

        const isRegistered = currentUserState.status !== 'not_registered';
        const isPaid = Boolean(currentUserState.isPaid);

        paymentIconBtn.style.display = 'inline-flex';
        paymentIconBtn.textContent = '💳';

        if (!isRegistered) {
            paymentIconBtn.disabled = true;
            paymentIconBtn.style.backgroundColor = '#555b64';
            paymentIconBtn.style.color = '#d0d5dd';
            paymentIconBtn.style.opacity = '0.55';
            paymentIconBtn.style.cursor = 'not-allowed';
            paymentIconBtn.title = 'Сначала запишитесь на матч';
            return;
        }

        if (isPaid) {
            paymentIconBtn.disabled = true;
            paymentIconBtn.style.backgroundColor = '#2e9e5b';
            paymentIconBtn.style.color = '#ffffff';
            paymentIconBtn.style.opacity = '1';
            paymentIconBtn.style.cursor = 'default';
            paymentIconBtn.title = 'Оплачено';
        } else {
            paymentIconBtn.disabled = false;
            paymentIconBtn.style.backgroundColor = '#e68a1e';
            paymentIconBtn.style.color = '#ffffff';
            paymentIconBtn.style.opacity = '1';
            paymentIconBtn.style.cursor = 'pointer';
            paymentIconBtn.title = 'Подтвердить оплату';
        }
    }

    function syncUserStatusAndActions(data) {
        const maxPlayers = Number(data?.max_players ?? data?.game?.max_players ?? 18);
        const roster = normalizeRoster(data?.signups, maxPlayers);
        const totalSigned = roster.main.length + roster.reserve.length;
        const freeSlots = Math.max(0, maxPlayers - totalSigned);

        const rawStatus = data?.status || 'not_registered';
        const isRegistered = rawStatus !== 'not_registered';

        const currentUserId = tg?.initDataUnsafe?.user?.id;
        const currentUsername = String(tg?.initDataUnsafe?.user?.username || '').replace(/^@+/, '').toLowerCase();

        const matchedPlayer = [...roster.main, ...roster.reserve].find((p) => {
            if (currentUserId && p.telegram_id && String(p.telegram_id) === String(currentUserId)) {
                return true;
            }
            const pUname = String(p.telegram_username || '').replace(/^@+/, '').toLowerCase();
            if (currentUsername && pUname && pUname === currentUsername) {
                return true;
            }
            return Boolean(p.is_current_user);
        });

        const resolvedStatus = matchedPlayer?.status || (rawStatus === 'reserve' ? 'reserve' : (isRegistered ? 'main' : 'not_registered'));
        const resolvedIsPaid = Boolean(matchedPlayer?.is_paid ?? data?.is_paid ?? false);

        currentUserState = {
            status: isRegistered ? resolvedStatus : 'not_registered',
            isPaid: isRegistered ? resolvedIsPaid : false,
            signupId: matchedPlayer?.id || data?.signup_id || null
        };

        if (refs.status) refs.status.style.display = 'block';

        if (!isRegistered) {
            if (refs.statusText) {
                refs.statusText.textContent = `Количество свободных слотов: ${freeSlots}`;
            }
            if (refs.payment) {
                refs.payment.innerHTML = '';
                refs.payment.style.display = 'none';
            }
        } else {
            const listLabel = currentUserState.status === 'reserve' ? 'Резерв' : 'Основной список';
            const badgeText = currentUserState.isPaid ? 'Оплачено' : 'Не оплачено';
            const badgeBg = currentUserState.isPaid ? '#2e9e5b' : '#e68a1e';

            if (refs.statusText) {
                refs.statusText.textContent = `Вы записаны: ${listLabel}`;
            }
            if (refs.payment) {
                refs.payment.style.display = 'inline-block';
                refs.payment.innerHTML = `<span style="display:inline-block;padding:3px 9px;border-radius:999px;font-size:12px;font-weight:700;color:#fff;background:${badgeBg};">${escapeHtml(badgeText)}</span>`;
            }
        }

        if (refs.action) {
            refs.action.style.display = isRegistered ? 'none' : 'block';
            refs.action.textContent = 'Записаться';
        }
        if (refs.cancel) {
            refs.cancel.style.display = isRegistered ? 'block' : 'none';
            refs.cancel.textContent = 'Отменить запись';
        }

        syncPaymentIcon();
    }

    if (paymentIconBtn) {
        paymentIconBtn.onclick = async () => {
            if (paymentIconBtn.disabled || currentUserState.status === 'not_registered' || currentUserState.isPaid) {
                return;
            }
            paymentIconBtn.disabled = true;
            try {
                if (currentUserState.signupId) {
                    await apiFetch(`/api/signups/${encodeURIComponent(currentUserState.signupId)}/pay`, {
                        method: 'PATCH',
                        body: JSON.stringify({ is_paid: true })
                    });
                } else if (currentGameId) {
                    await apiFetch('/api/signups/pay', {
                        method: 'POST',
                        body: JSON.stringify({ game_id: currentGameId, is_paid: true })
                    });
                }
                await loadData();
            } catch (err) {
                console.error('Ошибка подтверждения оплаты:', err);
                if (tg?.showAlert) tg.showAlert(`❌ Не удалось подтвердить оплату: ${err.message}`);
                syncPaymentIcon();
            }
        };
    }

    if (refs.action) {
        refs.action.onclick = async () => {
            if (!currentGameId || refs.action.disabled) return;
            refs.action.disabled = true;
            try {
                const res = await apiFetch('/api/signups', {
                    method: 'POST',
                    body: JSON.stringify({ game_id: currentGameId })
                });
                if (res?.success && tg?.showAlert) {
                    tg.showAlert(`✅ Вы записаны (${res.status === 'reserve' ? 'Резерв' : 'Основной список'})!`);
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
        refs.cancel.onclick = async () => {
            if (!currentGameId || refs.cancel.disabled) return;
            refs.cancel.disabled = true;
            try {
                await apiFetch(`/api/signups?game_id=${encodeURIComponent(currentGameId)}`, { method: 'DELETE' });
                await loadData();
            } catch (err) {
                console.error('Ошибка отмены записи:', err);
                if (tg?.showAlert) tg.showAlert(`❌ Ошибка отмены: ${err.message}`);
            } finally {
                refs.cancel.disabled = false;
            }
        };
    }

    function renderPlayers(data) {
        if (!refs.players) return;
        refs.players.innerHTML = '';

        const maxPlayers = Number(data?.max_players ?? data?.game?.max_players ?? 18);
        const roster = normalizeRoster(data?.signups, maxPlayers);

        if (roster.main.length === 0 && roster.reserve.length === 0) {
            refs.players.innerHTML = '<div style="color: gray; font-size: 13px;">Пока никто не записался.</div>';
            return;
        }

        const createRow = (player, indexLabel) => {
            const item = document.createElement('div');
            item.className = 'player-item';

            const displayName = formatPlayerDisplayName(player.user_name || player.name);
            const paidClass = player.is_paid ? 'player-name-paid' : 'player-name-unpaid';

            const adminHtml = data.is_admin
                ? `<div style="display: flex; gap: 4px; flex-shrink: 0;">
                    <button type="button" class="btn-secondary btn-sm toggle-pay" data-id="${escapeHtml(player.id)}" data-paid="${!player.is_paid}" title="Подтвердить / снять оплату">${player.is_paid ? '↩️' : '💳'}</button>
                    <button type="button" class="btn-danger btn-sm remove-signup" data-id="${escapeHtml(player.id)}" title="Удалить из списка">🗑</button>
                </div>`
                : '';

            item.innerHTML = `
                <div class="player-info">
                    <span style="min-width: 28px; color: gray;">${escapeHtml(indexLabel)}</span>
                    <button type="button" class="player-name-trigger ${paidClass}" style="background: none; border: none; padding: 0; margin: 0; width: auto; text-align: left; font-size: 14px; cursor: pointer; text-decoration: none;">
                        ${escapeHtml(displayName)}
                    </button>
                </div>
                ${adminHtml}
            `;

            const nameBtn = item.querySelector('.player-name-trigger');
            if (nameBtn) {
                nameBtn.onclick = () => openPlayerInfoPopup(player);
            }

            return item;
        };

        if (roster.main.length > 0) {
            const mainTitle = document.createElement('div');
            mainTitle.style.cssText = 'font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; color: gray; margin: 6px 0 8px;';
            mainTitle.textContent = 'Основной состав';
            refs.players.appendChild(mainTitle);

            roster.main.forEach((player, idx) => {
                refs.players.appendChild(createRow(player, `#${idx + 1}`));
            });
        }

        if (roster.reserve.length > 0) {
            const divider = document.createElement('div');
            divider.style.cssText = 'display: flex; align-items: center; gap: 10px; margin: 14px 0 10px; color: gray; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px;';
            divider.innerHTML = `
                <span style="flex: 1; height: 1px; background: rgba(128, 128, 128, 0.35);"></span>
                <span>Резерв</span>
                <span style="flex: 1; height: 1px; background: rgba(128, 128, 128, 0.35);"></span>
            `;
            refs.players.appendChild(divider);

            roster.reserve.forEach((player, idx) => {
                refs.players.appendChild(createRow(player, `Р${idx + 1}`));
            });
        }

        refs.players.querySelectorAll('.toggle-pay').forEach((btn) => {
            btn.onclick = async () => {
                if (btn.disabled) return;
                const targetIsPaid = btn.dataset.paid === 'true';
                btn.disabled = true;
                try {
                    await apiFetch(`/api/signups/${encodeURIComponent(btn.dataset.id)}/pay`, {
                        method: 'PATCH',
                        body: JSON.stringify({ is_paid: targetIsPaid })
                    });
                    await loadData();
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

    async function loadData() {
        gameId = resolveAnnouncementGameId();
        currentGameId = gameId;

        if (!gameId) {
            if (refs.details) {
                refs.details.textContent = 'ℹ️ Чтобы открыть матч, нажмите кнопку «Запись» под анонсом в группе.';
            }
            if (refs.status) refs.status.style.display = 'none';
            if (refs.action) refs.action.style.display = 'none';
            if (refs.cancel) refs.cancel.style.display = 'none';
            if (paymentIconBtn) paymentIconBtn.style.display = 'none';
            if (refs.players) refs.players.innerHTML = '';
            if (refs.totalCount) refs.totalCount.textContent = '0';
            if (refs.maxCount) refs.maxCount.textContent = '0';
            return;
        }

        try {
            const data = await apiFetch(`/api/signups/status?game_id=${encodeURIComponent(gameId)}`);
            const game = data.game || {};
            const link = safeUrl(game.loc_link);
            const locName = escapeHtml(game.loc_name || 'Площадка');
            const maxPlayers = Number(data.max_players ?? game.max_players ?? 18);
            const roster = normalizeRoster(data.signups, maxPlayers);

            if (refs.details) {
                const locationHtml = link
                    ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer" style="color: inherit; text-decoration: none; border-bottom: 1px dotted currentColor; padding-bottom: 1px;">${locName} ↗</a>`
                    : locName;

                refs.details.innerHTML = `
                    <div style="margin-bottom: 4px;"><b>📅</b> ${escapeHtml(game.date || '—')} (${escapeHtml(game.time_start || '—')}–${escapeHtml(game.time_end || '—')})</div>
                    <div style="margin-bottom: 4px;"><b>📍</b> ${locationHtml}</div>
                    <div><b>💰</b> ${escapeHtml(game.cost || '—')} &nbsp;•&nbsp; <b>👤</b> ${escapeHtml(game.org_name || '—')}</div>
                `;
            }

            if (refs.totalCount) {
                refs.totalCount.textContent = String(roster.main.length + roster.reserve.length);
            }
            if (refs.maxCount) {
                refs.maxCount.textContent = String(maxPlayers);
            }

            syncUserStatusAndActions(data);
            renderPlayers(data);
        } catch (e) {
            console.error('Ошибка загрузки статуса записи:', e);
            if (refs.details) {
                refs.details.textContent = `❌ Ошибка загрузки состава: ${e?.message || 'неизвестная ошибка'}`;
            }
            if (refs.players) refs.players.innerHTML = '';
        }
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
                ? `Чек «${fileName}» выбран.`
                : 'Окно загрузки чека закрыто.';
            if (tg?.showAlert) {
                tg.showAlert(msg);
            } else {
                alert(msg);
            }
        };
    }

    await loadData();
}