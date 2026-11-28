import { getMatchState, renderMatchUI, getLineupForTeam, loadMatchState } from './match-view.js';
import { apiFetch } from '../core/api.js';

function getPlayerLabel(signup) {
    const u = signup?.user || {};
    return (
        signup?.first_name ||
        signup?.username ||
        u.first_name ||
        u.username ||
        `Игрок ${signup?.user_id ?? ''}`
    );
}

export function initMatchControls(setActiveView) {
    document.getElementById('matchBackBtn')?.addEventListener('click', (e) => {
        e.preventDefault();
        setActiveView('signup');
    });

    ['Left', 'Right'].forEach((side) => {
        const btn = document.getElementById(`btnTeamName${side}`);
        btn?.addEventListener('click', () => {
            const matchState = getMatchState();
            matchState.activeSide = side;
            const select = document.getElementById('teamChangeSelect');
            if (select) {
                select.innerHTML = '';
                const currentTeam = side === 'Left' ? matchState.teams?.[0] : matchState.teams?.[1];
                (matchState.teams || []).forEach((t) => {
                    const opt = document.createElement('option');
                    opt.value = String(t.id);
                    opt.textContent = t.name || 'Команда';
                    if (currentTeam && String(t.id) === String(currentTeam.id)) {
                        opt.selected = true;
                    }
                    select.appendChild(opt);
                });
            }
            openModal('teamChangeModal');
        });
    });

    document.getElementById('teamChangeConfirm')?.addEventListener('click', async () => {
        const select = document.getElementById('teamChangeSelect');
        const newTeamId = select?.value;
        const matchState = getMatchState();
        if (!newTeamId || !matchState.activeSide) return;

        const team = (matchState.teams || []).find((t) => String(t.id) === String(newTeamId));
        if (!team) return;

        if (matchState.activeSide === 'Left') {
            matchState.teams[0] = team;
        } else {
            matchState.teams[1] = team;
        }

        renderMatchUI();
        closeModal('teamChangeModal');

        if (matchState.matchId) {
            try {
                await apiFetch(`/api/match/matches/${encodeURIComponent(matchState.matchId)}/score`, {
                    method: 'PATCH',
                    body: JSON.stringify({
                        left_score: matchState.scoreLeft ?? 0,
                        right_score: matchState.scoreRight ?? 0,
                    }),
                });
            } catch (err) {
                console.error('Team side sync failed:', err);
            }
        }
    });

    document.getElementById('btnSwapTeamLeft')?.addEventListener('click', () => openReplaceModal('Left'));
    document.getElementById('btnSwapTeamRight')?.addEventListener('click', () => openReplaceModal('Right'));

    document.getElementById('btnUndoAction')?.addEventListener('click', async () => {
        const matchState = getMatchState();
        if (!matchState.gameId) return;
        try {
            await apiFetch(`/api/match/logs/undo?game_id=${encodeURIComponent(matchState.gameId)}`, {
                method: 'POST',
            });
            if (typeof loadMatchState === 'function') {
                await loadMatchState(matchState.gameId);
            } else {
                renderMatchUI();
            }
        } catch (err) {
            console.error('Undo failed:', err);
        }
    });

    document.getElementById('btnFinishMatch')?.addEventListener('click', () => {
        const matchState = getMatchState();
        const leftInput = document.getElementById('finishScoreLeft');
        const rightInput = document.getElementById('finishScoreRight');
        if (leftInput) leftInput.value = matchState.scoreLeft ?? 0;
        if (rightInput) rightInput.value = matchState.scoreRight ?? 0;
        openModal('finishMatchModal');
    });

    document.getElementById('finishConfirm')?.addEventListener('click', async () => {
        const leftScore = parseInt(document.getElementById('finishScoreLeft')?.value, 10) || 0;
        const rightScore = parseInt(document.getElementById('finishScoreRight')?.value, 10) || 0;
        const status = document.getElementById('finishStatus')?.value || 'finished';
        const matchState = getMatchState();

        try {
            if (matchState.matchId) {
                await apiFetch(`/api/match/matches/${encodeURIComponent(matchState.matchId)}/score`, {
                    method: 'PATCH',
                    body: JSON.stringify({
                        left_score: leftScore,
                        right_score: rightScore,
                        status,
                    }),
                });
            }
            matchState.scoreLeft = leftScore;
            matchState.scoreRight = rightScore;
            matchState.status = status;
            renderMatchUI();
            closeModal('finishMatchModal');
        } catch (err) {
            console.error('Finish failed:', err);
        }
    });
}

export function initMatchSwipeAndModals() {
    document.getElementById('replacePlayerConfirm')?.addEventListener('click', async () => {
        const outSelect = document.getElementById('replaceOutSelect');
        const inSelect = document.getElementById('replaceInSelect');
        const outId = outSelect?.value;
        const inId = inSelect?.value;
        const matchState = getMatchState();
        if (!outId || !inId || !matchState.gameId) return;

        try {
            const teamId =
                matchState.activeSide === 'Left' ? matchState.teams?.[0]?.id : matchState.teams?.[1]?.id;
            await apiFetch('/api/match/lineups/replace', {
                method: 'POST',
                body: JSON.stringify({
                    game_id: String(matchState.gameId),
                    old_player_id: String(outId),
                    new_player_id: String(inId),
                    team_id: teamId ? String(teamId) : null,
                }),
            });
            const res = await apiFetch(`/api/match/${encodeURIComponent(matchState.gameId)}/state`);
            matchState.lineups = Array.isArray(res?.lineups) ? res.lineups : [];
            renderMatchUI();
            closeModal('replacePlayerModal');
        } catch (err) {
            console.error('Replace failed:', err);
        }
    });

    let touchStartY = 0;
    ['scoreLeft', 'scoreRight'].forEach((id) => {
        const el = document.getElementById(id);
        el?.addEventListener(
            'touchstart',
            (e) => {
                if (e.touches && e.touches[0]) {
                    touchStartY = e.touches[0].clientY;
                }
            },
            { passive: true }
        );
        el?.addEventListener('touchend', (e) => {
            if (!e.changedTouches || !e.changedTouches[0]) return;
            const touchEndY = e.changedTouches[0].clientY;
            const diff = touchStartY - touchEndY;
            const isLeft = id === 'scoreLeft';
            if (Math.abs(diff) > 30) {
                const delta = diff > 0 ? 1 : -1;
                el.classList.add('swipe-anim');
                setTimeout(() => el.classList.remove('swipe-anim'), 300);
                updateScore(isLeft, delta);
            }
        });
    });

    document.querySelectorAll('.modal .btn-secondary').forEach((btn) => {
        btn.addEventListener('click', () => {
            const modal = btn.closest('.modal');
            if (modal) modal.style.display = 'none';
        });
    });

    document.querySelectorAll('.modal').forEach((modal) => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.style.display = 'none';
        });
    });
}

export function openActionModal(playerId, playerName) {
    const nameEl = document.getElementById('actionPlayerName');
    if (nameEl) nameEl.textContent = playerName;
    const list = document.getElementById('actionList');
    if (!list) return;
    list.innerHTML = '';

    const matchState = getMatchState();
    (matchState.actions || []).forEach((a) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.style.display = 'block';
        btn.style.width = '100%';
        btn.style.textAlign = 'left';
        btn.style.padding = '8px';
        btn.style.borderRadius = '6px';
        btn.style.border = '1px solid rgba(128,128,128,0.16)';
        btn.style.background = 'var(--tg-theme-bg-color, #fff)';
        btn.style.color = 'inherit';
        btn.style.fontSize = '13px';
        btn.style.cursor = 'pointer';

        const rawW = a.weight ?? a.action_weight ?? a.points ?? a.payload?.weight;
        const hasWeight = rawW !== undefined && rawW !== null && rawW !== '';
        const numW = hasWeight ? Number(rawW) : null;

        let weightClass = 'match-log-weight-neu';
        if (numW !== null && !Number.isNaN(numW)) {
            if (numW > 0) weightClass = 'match-log-weight-pos';
            else if (numW < 0) weightClass = 'match-log-weight-neg';
        }

        const weightText = numW !== null && !Number.isNaN(numW) ? numW : '-';
        btn.innerHTML = `${a.title || 'Действие'} (<span class="${weightClass}">вес: ${weightText}</span>)`;
        btn.addEventListener('click', () => {
            logAction(playerId, a.action_type || a.title, numW);
            closeModal('actionModal');
        });
        list.appendChild(btn);
    });
    openModal('actionModal');
}

async function logAction(playerId, actionType, weight) {
    const matchState = getMatchState();
    if (!matchState.gameId) return;
    try {
        await apiFetch('/api/match/logs', {
            method: 'POST',
            body: JSON.stringify({
                game_id: String(matchState.gameId),
                match_id: matchState.matchId || null,
                action_type: actionType,
                actor_id: playerId != null ? Number(playerId) || null : null,
                payload: { weight },
            }),
        });
        renderMatchUI();
    } catch (err) {
        console.error('Log action failed:', err);
    }
}

export function openReplaceModal(side) {
    const matchState = getMatchState();
    const teamId = side === 'Left' ? matchState.teams?.[0]?.id : matchState.teams?.[1]?.id;
    const players = typeof getLineupForTeam === 'function' ? getLineupForTeam(teamId) : [];
    const outSelect = document.getElementById('replaceOutSelect');
    const inSelect = document.getElementById('replaceInSelect');
    if (outSelect) outSelect.innerHTML = '';
    if (inSelect) inSelect.innerHTML = '';

    players.forEach((pl) => {
        const opt = document.createElement('option');
        opt.value = String(pl.player_id);
        opt.textContent = pl.name;
        outSelect?.appendChild(opt);
    });

    const assignedIds = new Set((matchState.lineups || []).map((l) => String(l.player_id)));
    (matchState.signups || []).forEach((s) => {
        const uid = String(s.user_id);
        if (!assignedIds.has(uid)) {
            const opt = document.createElement('option');
            opt.value = uid;
            opt.textContent = getPlayerLabel(s);
            inSelect?.appendChild(opt);
        }
    });

    if (inSelect && inSelect.children.length === 0) {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = '(нет свободных игроков)';
        opt.disabled = true;
        inSelect.appendChild(opt);
    }

    matchState.activeSide = side;
    openModal('replacePlayerModal');
}

function openModal(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'flex';
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
}

async function updateScore(isLeft, delta) {
    const matchState = getMatchState();
    if (isLeft) matchState.scoreLeft = Math.max(0, (matchState.scoreLeft ?? 0) + delta);
    else matchState.scoreRight = Math.max(0, (matchState.scoreRight ?? 0) + delta);
    renderMatchUI();

    if (!matchState.matchId) return;
    try {
        await apiFetch(`/api/match/matches/${encodeURIComponent(matchState.matchId)}/score`, {
            method: 'PATCH',
            body: JSON.stringify({
                left_score: matchState.scoreLeft,
                right_score: matchState.scoreRight,
            }),
        });
    } catch (err) {
        console.error('Score update failed:', err);
    }
}