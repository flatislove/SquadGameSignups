import { escapeHtml } from './navigation.js';
import { apiFetch } from '../core/api.js';
import { getCurrentSettingsGameId, loadGameSettings } from './game-settings.js';

export function getActionWeight(a) {
    if (a.weight != null) return a.weight;
    if (a.action_weight != null) return a.action_weight;
    if (a.points != null) return a.points;
    if (a.payload && a.payload.weight != null) return a.payload.weight;
    return null;
}

export function renderActions(container, actions) {
    if (!container) return;
    container.innerHTML = '';
    if (actions.length === 0) {
        container.innerHTML = '<div style="color: gray; font-size: 13px; text-align: center; padding: 16px;">Нет действий сообщества</div>';
        return;
    }

    actions.forEach(a => {
        const actionEl = document.createElement('div');
        actionEl.style.display = 'flex';
        actionEl.style.alignItems = 'center';
        actionEl.style.justifyContent = 'space-between';
        actionEl.style.padding = '8px 10px';
        actionEl.style.borderRadius = '8px';
        actionEl.style.background = 'var(--tg-theme-secondary-bg-color, #f5f5f5)';
        actionEl.style.border = '1px solid rgba(128,128,128,0.16)';

        const info = document.createElement('span');
        info.style.flex = '1';
        info.style.fontSize = '13px';
        info.style.color = 'inherit';
        const w = getActionWeight(a);

        // Coloring by sign of weight (> 0 green, < 0 red, 0/null neutral)
        let weightClass = 'match-log-weight-neu';
        if (w != null) {
            const numW = Number(w);
            if (numW > 0) weightClass = 'match-log-weight-pos';
            else if (numW < 0) weightClass = 'match-log-weight-neg';
        }

        info.innerHTML = `${escapeHtml(a.title || 'Действие')} (<span class="${weightClass}">вес: ${w != null ? w : '-'}</span>)`;

        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.textContent = 'Удалить';
        delBtn.style.padding = '4px 10px';
        delBtn.style.borderRadius = '6px';
        delBtn.style.border = 'none';
        delBtn.style.background = '#d9534f';
        delBtn.style.color = '#fff';
        delBtn.style.fontSize = '12px';
        delBtn.style.cursor = 'pointer';
        delBtn.dataset.actionId = a.id;
        delBtn.addEventListener('click', () => deleteCommunityAction(a.id));

        actionEl.appendChild(info);
        actionEl.appendChild(delBtn);
        container.appendChild(actionEl);
    });
}

export function wireAddActionButton(gameId) {
    const addBtn = document.getElementById('btnAddAction');
    if (addBtn) {
        const newBtn = addBtn.cloneNode(true);
        addBtn.parentNode.replaceChild(newBtn, addBtn);
        newBtn.addEventListener('click', () => addCommunityAction(gameId));
    }
}

async function addCommunityAction(gameId) {
    const titleInput = document.getElementById('newActionTitle');
    const weightInput = document.getElementById('newActionWeight');
    const errorEl = document.getElementById('gameSettingsError');
    const title = titleInput?.value?.trim();
    const weightVal = weightInput?.value ? parseFloat(weightInput.value) : 1.0;

    if (!title) {
        if (errorEl) {
            errorEl.textContent = 'Введите название действия';
            errorEl.style.display = 'block';
        }
        return;
    }
    try {
        const statusRes = await apiFetch(`/api/signups/status?game_id=${encodeURIComponent(gameId)}`);
        const game = statusRes.game || {};
        const chat_id = game.group_id || game.chat_id;
        if (!chat_id) throw new Error('Не удалось определить chat_id игры');
        await apiFetch('/api/match/community-actions', {
            method: 'POST',
            body: JSON.stringify({ chat_id: chat_id, title: title, description: null, is_active: true, weight: weightVal })
        });
        titleInput.value = '';
        if (weightInput) weightInput.value = '';
        loadGameSettings(gameId);
    } catch (err) {
        console.error('Failed to add community action:', err);
        if (errorEl) {
            errorEl.textContent = `Ошибка добавления действия: ${escapeHtml(err?.message || '')}`;
            errorEl.style.display = 'block';
        }
    }
}

async function deleteCommunityAction(actionId) {
    const errorEl = document.getElementById('gameSettingsError');
    if (!confirm('Отключить это действие сообщества?')) return;
    try {
        await apiFetch(`/api/match/community-actions/${encodeURIComponent(actionId)}`, { method: 'DELETE' });
        const currentId = getCurrentSettingsGameId();
        if (currentId) loadGameSettings(currentId);
    } catch (err) {
        console.error('Failed to delete community action:', err);
        if (errorEl) {
            errorEl.textContent = `Ошибка удаления: ${escapeHtml(err?.message || '')}`;
            errorEl.style.display = 'block';
        }
    }
}
