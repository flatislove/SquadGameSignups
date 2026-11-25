import { tg } from '../core/tg.js';
import { apiFetch } from '../core/api.js';

document.getElementById('gameForm')?.addEventListener('submit', async (e) => {
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
            tg.showAlert("✅ Анонс успешно создан и отправлен в группу!");
        } else {
            tg.showAlert("❌ Ошибка при создании анонса.");
        }
    } catch (err) {
        console.error("Error creating game:", err);
        tg.showAlert(`❌ Ошибка: ${err.message}`);
    }
});
