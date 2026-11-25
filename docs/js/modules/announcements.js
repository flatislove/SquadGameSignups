import { tg } from '../core/tg.js';
import { apiFetch } from '../core/api.js';

export function initAnnouncements() {
    const form = document.getElementById('gameForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const payload = {
            chat_id: parseInt(document.getElementById('chatSelect').value),
            date: document.getElementById('gameDate').value,
            time: document.getElementById('startTime').value,
            end_time: document.getElementById('endTime').value,
            publish_time: document.getElementById('publishTime').value,
            loc_name: document.getElementById('locName').value,
            loc_link: document.getElementById('locLink').value,
            cost: document.getElementById('cost').value,
            max_players: parseInt(document.getElementById('maxPlayers').value),
            name: document.getElementById('orgName').value,
            phone: document.getElementById('orgPhone').value
        };

        try {
            const res = await apiFetch('/api/games/create', {
                method: 'POST',
                body: JSON.stringify(payload)
            });

            if (res.success) {
                const gameId = res.game_id;
                const botUsername = window.BOT_USERNAME || "squad_game_signups_bot";
                const deepLink = `https://t.me/${botUsername}?startapp=game_${gameId}`;
                
                const message = `✅ Анонс успешно создан и отправлен в группу!\n\nID игры: ${gameId}\nСсылка на карточку:\n${deepLink}`;
                
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(deepLink).catch(() => {});
                }

                tg.showAlert(message, () => {
                    // Optional callback after alert closed
                });
            } else {
                tg.showAlert("❌ Ошибка при создании анонса.");
            }
        } catch (err) {
            console.error("Error creating game:", err);
            tg.showAlert(`❌ Ошибка: ${err.message}`);
        }
    });
}

