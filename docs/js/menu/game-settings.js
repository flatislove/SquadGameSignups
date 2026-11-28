import { escapeHtml, openSection } from './navigation.js';
import { apiFetch } from '../core/api.js';

let selectedGameId = null;
let currentSettingsGameId = null;

function getPlayerDisplayName(player) {
    const nested = player?.user || {};
    return (
        player?.first_name ||
        player?.username ||
        nested.first_name ||
        nested.username ||
        `Игрок ${player?.user_id ?? ''}`
    );
}

export function initGameSection() {
    const gameSelect = document.getElementById('gameSelect');
    const btnGameStart = document.getElementById('btnGameStart');
    const btnGameSettings = document.getElementById('btnGameSettings');

    document.getElementById('menu-game')?.addEventListener('click', () => {
        loadGamesForDropdown();
        updateGameButtons(null);
    });

    gameSelect?.addEventListener('change', (e) => {
        updateGameButtons(e.target.value);
    });

    btnGameStart?.addEventListener('click', () => {
        if (!selectedGameId) return;
        window.location.href = `index.html?game_id=${encodeURIComponent(selectedGameId)}`;
    });

    btnGameSettings?.addEventListener('click', () => {
        if (!selectedGameId) return;
        currentSettingsGameId = selectedGameId;
        openSection('gameSettingsSection');
        loadGameSettings(selectedGameId);
    });

    document.querySelectorAll('[data-back-to-game]').forEach((btn) => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            document.querySelectorAll('.section-view').forEach((el) => el.classList.remove('is-open'));
            const target = document.getElementById('gameSection');
            if (target) target.classList.add('is-open');
        });
    });
}

async function loadGamesForDropdown() {
    const gameSelect = document.getElementById('gameSelect');
    if (!gameSelect) return;
    gameSelect.innerHTML = '<option value="">Загрузка игр...</option>';
    try {
        const res = await apiFetch('/api/signups/my-games');
        const games = Array.isArray(res?.games) ? res.games : [];
        gameSelect.innerHTML = '<option value="">— Выберите игру —</option>';
        games.forEach((item) => {
            const g = item.game || {};
            const dateStr = g.date || 'Уточняется';
            const timeStr = g.time_start ? ` ${g.time_start}` : '';
            const locStr = g.loc_name || g.venue_name || 'Площадка';
            const option = document.createElement('option');
            option.value = String(g.id ?? item.game_id ?? '');
            option.textContent = `${dateStr}${timeStr} — ${locStr}`;
            gameSelect.appendChild(option);
        });
        if (games.length === 0) {
            gameSelect.innerHTML = '<option value="">Нет доступных игр</option>';
        }
    } catch (err) {
        console.error('Failed to load games for dropdown:', err);
        gameSelect.innerHTML = '<option value="">Ошибка загрузки игр</option>';
    }
}

function updateGameButtons(gameId) {
    selectedGameId = gameId || null;
    const btnGameStart = document.getElementById('btnGameStart');
    const btnGameSettings = document.getElementById('btnGameSettings');
    const gameInfo = document.getElementById('gameInfo');

    if (!selectedGameId) {
        if (btnGameStart) btnGameStart.disabled = true;
        if (btnGameSettings) btnGameSettings.style.display = 'none';
        if (gameInfo) gameInfo.style.display = 'none';
        return;
    }
    if (btnGameStart) btnGameStart.disabled = false;
    checkAdminForGame(selectedGameId);
}

async function checkAdminForGame(gameId) {
    const btnGameSettings = document.getElementById('btnGameSettings');
    const gameInfo = document.getElementById('gameInfo');
    try {
        const res = await apiFetch(`/api/signups/status?game_id=${encodeURIComponent(gameId)}`);
        if (btnGameSettings) {
            btnGameSettings.style.display = res?.is_admin ? 'block' : 'none';
        }
        const g = res?.game || {};
        if (gameInfo) {
            const title = escapeHtml(g.title || g.name || 'Игра');
            const statusText = escapeHtml(res?.status || '-');
            gameInfo.innerHTML = `
                <div style="font-weight: bold; margin-bottom: 4px;">${title}</div>
                <div style="color: gray; font-size: 12px;">Статус: ${statusText}</div>
            `;
            gameInfo.style.display = 'block';
        }
    } catch (err) {
        console.error('Failed to check admin status:', err);
        if (btnGameSettings) btnGameSettings.style.display = 'none';
        if (gameInfo) gameInfo.style.display = 'none';
    }
}

export async function loadGameSettings(gameId) {
    currentSettingsGameId = gameId;
    const errorEl = document.getElementById('gameSettingsError');
    if (errorEl) errorEl.style.display = 'none';

    const playersList = document.getElementById('playersList');
    const teamsContainer = document.getElementById('teamsContainer');
    const actionsList = document.getElementById('actionsList');

    if (playersList) playersList.innerHTML = '<div style="color: gray; font-size: 13px;">Загрузка...</div>';
    if (teamsContainer) teamsContainer.innerHTML = '<div style="color: gray; font-size: 13px;">Загрузка...</div>';
    if (actionsList) actionsList.innerHTML = '<div style="color: gray; font-size: 13px;">Загрузка...</div>';

    try {
        const [stateRes, statusRes] = await Promise.all([
            apiFetch(`/api/match/${encodeURIComponent(gameId)}/state`),
            apiFetch(`/api/signups/status?game_id=${encodeURIComponent(gameId)}`),
        ]);

        const teams = Array.isArray(stateRes?.teams) ? stateRes.teams : [];
        const lineups = Array.isArray(stateRes?.lineups) ? stateRes.lineups : [];
        const actions = Array.isArray(stateRes?.actions) ? stateRes.actions : [];
        const signups = Array.isArray(statusRes?.signups) ? statusRes.signups : [];

        const playerTeamMap = {};
        lineups.forEach((l) => {
            if (l.player_id != null && l.team_id != null) {
                playerTeamMap[String(l.player_id)] = String(l.team_id);
            }
        });

        let teamsToRender = teams.slice();
        if (teamsToRender.length === 0) {
            teamsToRender = [
                { id: 'new_1', name: 'Команда 1', color: '#2481cc', _new: true },
                { id: 'new_2', name: 'Команда 2', color: '#e68a1e', _new: true },
                { id: 'new_3', name: 'Команда 3', color: '#2e9e5b', _new: true },
            ];
        }

        renderTeams(teamsContainer, teamsToRender, signups, playerTeamMap);
        renderPlayers(playersList, signups, playerTeamMap);

        const commActions = await import('./community-actions.js');
        commActions.renderActions(actionsList, actions);

        wireSaveButton(gameId, teamsToRender);
        commActions.wireAddActionButton(gameId);
    } catch (err) {
        console.error('Failed to load game settings:', err);
        if (errorEl) {
            errorEl.textContent = `Ошибка загрузки: ${escapeHtml(err?.message || 'Неизвестная ошибка')}`;
            errorEl.style.color = '#d9534f';
            errorEl.style.display = 'block';
        }
    }
}

function renderTeams(container, teams, signups, playerTeamMap) {
    if (!container) return;
    container.innerHTML = '';

    teams.forEach((team, idx) => {
        const teamIdStr = String(team.id);
        const teamEl = document.createElement('div');
        teamEl.style.border = '1px solid rgba(128,128,128,0.16)';
        teamEl.style.borderRadius = '10px';
        teamEl.style.padding = '10px';
        teamEl.style.background = 'var(--tg-theme-secondary-bg-color, #f5f5f5)';
        teamEl.style.display = 'flex';
        teamEl.style.flexDirection = 'column';
        teamEl.style.gap = '8px';

        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.value = team.name || `Команда ${idx + 1}`;
        nameInput.style.padding = '6px 8px';
        nameInput.style.borderRadius = '6px';
        nameInput.style.border = '1px solid rgba(128,128,128,0.16)';
        nameInput.style.fontSize = '14px';
        nameInput.style.color = 'inherit';
        nameInput.style.background = 'var(--tg-theme-bg-color, #fff)';
        nameInput.dataset.teamId = teamIdStr;
        teamEl.appendChild(nameInput);

        const zone = document.createElement('div');
        zone.style.border = '2px dashed rgba(128,128,128,0.3)';
        zone.style.borderRadius = '8px';
        zone.style.padding = '8px';
        zone.style.minHeight = '60px';
        zone.style.background = 'var(--tg-theme-bg-color, #fff)';
        zone.dataset.teamId = teamIdStr;
        zone.dataset.dropZone = 'true';
        zone.classList.add('drop-zone');

        const teamPlayers = signups.filter((s) => {
            const sUid = s.user_id != null ? String(s.user_id) : null;
            return sUid && playerTeamMap[sUid] === teamIdStr;
        });
        teamPlayers.forEach((p) => {
            zone.appendChild(createPlayerCard(p.user_id, getPlayerDisplayName(p), teamIdStr));
        });

        teamEl.appendChild(zone);
        container.appendChild(teamEl);
    });

    setupDropZones();
}

function renderPlayers(container, signups, playerTeamMap) {
    if (!container) return;
    container.innerHTML = '';

    const assignedPlayerIds = new Set(Object.keys(playerTeamMap));
    const unassigned = signups.filter((s) => {
        const sUid = s.user_id != null ? String(s.user_id) : null;
        return sUid && !assignedPlayerIds.has(sUid);
    });

    if (unassigned.length === 0) {
        container.innerHTML =
            '<div style="color: gray; font-size: 13px; text-align: center; padding: 16px;">Все игроки распределены по командам</div>';
        return;
    }

    const label = document.createElement('div');
    label.style.fontWeight = 'bold';
    label.style.marginBottom = '4px';
    label.textContent = 'Без команды:';
    container.appendChild(label);

    unassigned.forEach((p) => {
        container.appendChild(createPlayerCard(p.user_id, getPlayerDisplayName(p), ''));
    });
}

function createPlayerCard(playerId, name, teamId) {
    const pidStr = String(playerId);
    const tidStr = teamId ? String(teamId) : '';

    const card = document.createElement('div');
    card.style.padding = '8px 10px';
    card.style.borderRadius = '8px';
    card.style.background = 'var(--tg-theme-bg-color, #fff)';
    card.style.border = '1px solid rgba(128,128,128,0.16)';
    card.style.display = 'flex';
    card.style.alignItems = 'center';
    card.style.gap = '8px';
    card.dataset.playerId = pidStr;
    card.dataset.teamId = tidStr;

    const dot = document.createElement('span');
    dot.style.width = '8px';
    dot.style.height = '8px';
    dot.style.borderRadius = '50%';
    dot.style.background = tidStr ? '#2e9e5b' : '#e68a1e';
    card.appendChild(dot);

    const label = document.createElement('span');
    label.style.flex = '1';
    label.style.fontSize = '13px';
    label.style.color = 'inherit';
    label.textContent = name;
    card.appendChild(label);

    const teamSelect = document.createElement('select');
    teamSelect.style.fontSize = '12px';
    teamSelect.style.padding = '4px 6px';
    teamSelect.style.borderRadius = '6px';
    teamSelect.style.border = '1px solid rgba(128,128,128,0.16)';
    teamSelect.style.background = 'var(--tg-theme-secondary-bg-color, #f5f5f5)';
    teamSelect.style.color = 'inherit';
    teamSelect.dataset.playerId = pidStr;

    const noneOpt = document.createElement('option');
    noneOpt.value = '';
    noneOpt.textContent = '— Без команды —';
    teamSelect.appendChild(noneOpt);

    const teamInputs = document.querySelectorAll('input[data-team-id]');
    teamInputs.forEach((input) => {
        const tid = String(input.dataset.teamId || '');
        const tname = input.value || 'Команда';
        const opt = document.createElement('option');
        opt.value = tid;
        opt.textContent = tname;
        if (tid === tidStr) opt.selected = true;
        teamSelect.appendChild(opt);
    });

    teamSelect.addEventListener('change', (e) => {
        const newTid = String(e.target.value || '');
        card.dataset.teamId = newTid;
        dot.style.background = newTid ? '#2e9e5b' : '#e68a1e';
        if (newTid) {
            const targetZone = document.querySelector(`[data-drop-zone="true"][data-team-id="${newTid}"]`);
            if (targetZone) targetZone.appendChild(card);
        } else {
            const playersList = document.getElementById('playersList');
            if (playersList) playersList.appendChild(card);
        }
    });
    card.appendChild(teamSelect);

    card.draggable = true;
    card.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('text/plain', pidStr);
        e.dataTransfer.effectAllowed = 'move';
        card.style.opacity = '0.5';
    });
    card.addEventListener('dragend', () => {
        card.style.opacity = '1';
    });

    return card;
}

function setupDropZones() {
    document.querySelectorAll('[data-drop-zone]').forEach((zone) => {
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.style.borderColor = '#2481cc';
        });
        zone.addEventListener('dragleave', () => {
            zone.style.borderColor = 'rgba(128,128,128,0.3)';
        });
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            const playerId = e.dataTransfer.getData('text/plain');
            const playerCard = document.querySelector(`[data-player-id="${playerId}"]`);
            if (playerCard) {
                const newTid = String(zone.dataset.teamId || '');
                playerCard.dataset.teamId = newTid;
                const dotEl = playerCard.querySelector('span');
                if (dotEl) dotEl.style.background = newTid ? '#2e9e5b' : '#e68a1e';
                const sel = playerCard.querySelector('select');
                if (sel) sel.value = newTid;
                zone.appendChild(playerCard);
            }
            zone.style.borderColor = 'rgba(128,128,128,0.3)';
        });
    });
}

function wireSaveButton(gameId, teamsToRender) {
    const saveBtn = document.getElementById('btnSaveTeams');
    if (saveBtn) {
        const newBtn = saveBtn.cloneNode(true);
        saveBtn.parentNode.replaceChild(newBtn, saveBtn);
        newBtn.addEventListener('click', () => saveTeamsAndLineups(gameId, teamsToRender));
    }
}

async function saveTeamsAndLineups(gameId, teamsToRender) {
    const errorEl = document.getElementById('gameSettingsError');
    if (errorEl) errorEl.style.display = 'none';

    if (!gameId) {
        if (errorEl) {
            errorEl.textContent = 'Ошибка: не указан ID игры для сохранения';
            errorEl.style.color = '#d9534f';
            errorEl.style.display = 'block';
        }
        return;
    }

    try {
        const idRemap = new Map();

        for (const team of teamsToRender) {
            const oldId = String(team.id);
            const input = document.querySelector(`input[data-team-id="${oldId}"]`);
            const newName = (input ? input.value.trim() : '') || team.name || 'Команда';
            const query = !team._new && team.id ? `?team_id=${encodeURIComponent(team.id)}` : '';

            const res = await apiFetch(`/api/match/teams${query}`, {
                method: 'POST',
                body: JSON.stringify({
                    game_id: String(gameId),
                    name: newName,
                    color: team.color || '#2481cc',
                }),
            });

            if (res?.team?.id) {
                const realId = String(res.team.id);
                idRemap.set(oldId, realId);
                team.id = realId;
                team._new = false;
            } else {
                idRemap.set(oldId, oldId);
            }
        }

        const updatedMap = {};
        document.querySelectorAll('[data-player-id]').forEach((card) => {
            const rawTid = card.dataset.teamId ? String(card.dataset.teamId) : '';
            const pid = card.dataset.playerId ? String(card.playerId) : '';
            if (pid && rawTid) {
                updatedMap[pid] = idRemap.get(rawTid) || rawTid;
            }
        });

        for (const [playerId, teamId] of Object.entries(updatedMap)) {
            await apiFetch('/api/match/lineups', {
                method: 'POST',
                body: JSON.stringify({
                    game_id: String(gameId),
                    team_id: String(teamId),
                    player_id: String(playerId),
                }),
            });
        }

        if (errorEl) {
            errorEl.textContent = '✅ Сохранено успешно';
            errorEl.style.color = '#2e9e5b';
            errorEl.style.display = 'block';
        }
        setTimeout(() => loadGameSettings(gameId), 800);
    } catch (err) {
        console.error('Failed to save teams/lineups:', err);
        if (errorEl) {
            errorEl.textContent = `Ошибка сохранения: ${escapeHtml(err?.message || 'Неизвестная ошибка')}`;
            errorEl.style.color = '#d9534f';
            errorEl.style.display = 'block';
        }
    }
}

export function getCurrentSettingsGameId() {
    return currentSettingsGameId;
}