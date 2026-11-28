import { apiFetch } from '../core/api.js';

let matchState = {
    gameId: null,
    matchId: null,
    chatId: null,
    teams: [],
    lineups: [],
    actions: [],
    signups: [],
    scoreLeft: 0,
    scoreRight: 0,
    status: 'live',
    activeSide: null
};

export function getMatchState() {
    return matchState;
}

export async function initMatchView(gameId) {
    matchState.gameId = gameId;
    const titleEl = document.getElementById('matchGameTitle');
    if (titleEl) titleEl.textContent = 'Загрузка...';

    try {
        const [stateRes, statusRes] = await Promise.all([
            apiFetch(`/api/match/${encodeURIComponent(gameId)}/state`),
            apiFetch(`/api/signups/status?game_id=${encodeURIComponent(gameId)}`)
        ]);

        matchState.teams = Array.isArray(stateRes?.teams) ? stateRes.teams : [];
        matchState.lineups = Array.isArray(stateRes?.lineups) ? stateRes.lineups : [];
        matchState.actions = Array.isArray(stateRes?.actions) ? stateRes.actions : [];
        matchState.signups = Array.isArray(statusRes?.signups) ? statusRes.signups : [];
        matchState.chatId = (statusRes.game || {}).group_id || (statusRes.game || {}).chatId || (statusRes.game || {}).chat_id;

        const matches = Array.isArray(stateRes?.matches) ? stateRes.matches : [];
        const liveMatch = matches.find(m => m.status === 'live');
        if (liveMatch) {
            matchState.matchId = liveMatch.id;
            matchState.scoreLeft = liveMatch.left_score || 0;
            matchState.scoreRight = liveMatch.right_score || 0;
            matchState.status = liveMatch.status || 'live';
        } else {
            const leftTeam = matchState.teams[0] || {};
            const rightTeam = matchState.teams[1] || {};
            const createRes = await apiFetch('/api/match/matches', {
                method: 'POST',
                body: JSON.stringify({
                    game_id: gameId,
                    left_team_id: leftTeam.id || '',
                    right_team_id: rightTeam.id || ''
                })
            });
            matchState.matchId = createRes.match?.id || null;
            matchState.scoreLeft = 0;
            matchState.scoreRight = 0;
            matchState.status = 'live';
        }

        if (titleEl) {
            titleEl.textContent = (statusRes.game || {}).title || (statusRes.game || {}).name || 'Игра';
        }
        renderMatchUI();
    } catch (err) {
        console.error('Failed to init match view:', err);
        if (titleEl) titleEl.textContent = 'Ошибка загрузки матча';
    }
}

export function getLineupForTeam(teamId) {
    return matchState.lineups.filter(l => l.team_id === teamId).map(l => {
        const p = matchState.signups.find(s => s.user_id === l.player_id);
        const pName = p ? (p.first_name || p.username || (p.user && (p.user.first_name || p.user.username)) || `Игрок ${p.user_id}`) : `Игрок ${l.player_id}`;
        return { ...l, name: pName };
    });
}

export function renderMatchUI() {
    const leftTeam = matchState.teams[0] || { id: '', name: 'Команда слева' };
    const rightTeam = matchState.teams[1] || { id: '', name: 'Команда справа' };
    
    setElementText('btnTeamNameLeft', leftTeam.name || 'Команда слева');
    setElementText('btnTeamNameRight', rightTeam.name || 'Команда справа');
    setElementText('teamLeftLabel', leftTeam.name || 'Команда слева');
    setElementText('teamRightLabel', rightTeam.name || 'Команда справа');
    setElementText('scoreLeft', matchState.scoreLeft);
    setElementText('scoreRight', matchState.scoreRight);

    renderPlayersColumn('playersLeft', leftTeam.id);
    renderPlayersColumn('playersRight', rightTeam.id);
    renderLog();
}

function setElementText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function renderPlayersColumn(containerId, teamId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    const players = getLineupForTeam(teamId);
    if (players.length === 0) {
        container.innerHTML = '<div class="match-empty">Нет игроков</div>';
        return;
    }
    players.forEach(pl => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'match-player-btn';
        btn.textContent = pl.name;
        btn.dataset.playerId = pl.player_id;
        btn.addEventListener('click', () => {
            import('./match-controls.js').then(m => m.openActionModal(pl.player_id, pl.name));
        });
        container.appendChild(btn);
    });
}

function renderLog() {
    const container = document.getElementById('matchLogList');
    if (!container) return;
    container.innerHTML = '<div class="match-empty">Лог действий пуст</div>';
}
