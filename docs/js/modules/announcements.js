import { tg } from '../core/tg.js';
import { apiFetch } from '../core/api.js';

function populateChatSelect(selectEl, groups) {
    if (!selectEl) return;
    selectEl.innerHTML = '';

    if (!Array.isArray(groups) || groups.length === 0) {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = 'Нет доступных групп';
        selectEl.appendChild(opt);
        return;
    }

    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Выберите группу...';
    selectEl.appendChild(placeholder);

    for (const g of groups) {
        const chatId = g.group_id ?? g.chat_id ?? g.id;
        const title = g.title ?? g.name ?? `Группа ${chatId}`;
        if (chatId === undefined || chatId === null) continue;

        const opt = document.createElement('option');
        opt.value = String(chatId);
        opt.textContent = title;
        selectEl.appendChild(opt);
    }
}

export async function loadGroupsForForm() {
    const chatSelect = document.getElementById('chatSelect');
    if (!chatSelect) return;

    chatSelect.innerHTML = '<option value="">Загрузка групп...</option>';

    try {
        let data;
        try {
            data = await apiFetch('/api/groups');
        } catch (err) {
            console.warn('[announcements] /api/groups failed, fallback to /api/me/context:', err);
            data = await apiFetch('/api/me/context');
        }

        const groups = Array.isArray(data)
            ? data
            : (data?.groups ?? data?.admin_groups ?? data?.chats ?? []);

        if (!Array.isArray(groups) || groups.length === 0) {
            console.warn('[announcements] Groups list is empty. Raw response:', data);
        }

        populateChatSelect(chatSelect, groups);
    } catch (err) {
        console.error('[announcements] Failed to load groups:', err);
        chatSelect.innerHTML = '<option value="">Ошибка загрузки групп</option>';
    }
}

export function initAnnouncements() {
    const form = document.getElementById('gameForm');
    if (!form) return;

    loadGroupsForForm();

    document.querySelectorAll('.tab-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            if (btn.textContent && btn.textContent.includes('Создать анонс')) {
                loadGroupsForForm();
            }
        });
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const chatSelect = document.getElementById('chatSelect');
        const venueSelect = document.getElementById('venueSelect');
        const selectedOption = venueSelect ? venueSelect.options[venueSelect.selectedIndex] : null;

        const chatId = parseInt(chatSelect ? chatSelect.value : '', 10);
        if (!Number.isFinite(chatId)) {
            tg.showAlert('⚠️ Выберите группу для публикации анонса.');
            return;
        }

        const payload = {
            chat_id: chatId,
            date: document.getElementById('gameDate')?.value,
            time: document.getElementById('startTime')?.value,
            end_time: document.getElementById('endTime')?.value,
            publish_time: document.getElementById('publishTime')?.value,
            venue_id: venueSelect ? venueSelect.value : null,
            loc_name: selectedOption ? selectedOption.textContent : null,
            loc_link: selectedOption ? selectedOption.dataset.mapUrl : null,
            cost: document.getElementById('cost')?.value,
            max_players: parseInt(document.getElementById('maxPlayers')?.value, 10),
            name: document.getElementById('orgName')?.value,
            phone: document.getElementById('orgPhone')?.value
        };

        try {
            const res = await apiFetch('/api/games/create', {
                method: 'POST',
                body: JSON.stringify(payload)
            });

            if (res?.success) {
                const gameId = res.game_id;
                const botUsername = window.BOT_USERNAME || 'squad_game_signups_bot';
                const deepLink = `https://t.me/${botUsername}?startapp=game_${gameId}`;

                const message = `✅ Анонс успешно создан и отправлен в группу!\n\nID игры: ${gameId}\nСсылка на карточку:\n${deepLink}`;

                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(deepLink).catch(() => {});
                }

                tg.showAlert(message, () => {});
            } else {
                console.error('[announcements] Unexpected create response:', res);
                tg.showAlert('❌ Ошибка при создании анонса.');
            }
        } catch (err) {
            console.error('[announcements] Error creating game:', err);
            tg.showAlert(`❌ Ошибка: ${err.message}`);
        }
    });
}