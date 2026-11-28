import { initGameSection } from './game-settings.js';
import { apiFetch } from '../core/api.js';

export function openSection(sectionId) {
    document.querySelectorAll('.section-view').forEach(el => el.classList.remove('is-open'));
    const target = document.getElementById(sectionId);
    if (target) target.classList.add('is-open');
}

export function closeAllSections() {
    document.querySelectorAll('.section-view').forEach(el => el.classList.remove('is-open'));
}

export function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

export function initNavigation() {
    window.Telegram?.WebApp?.ready?.();
    window.Telegram?.WebApp?.expand?.();

    document.querySelectorAll('[data-open-section]').forEach(btn => {
        btn.addEventListener('click', () => {
            const sectionId = btn.getAttribute('data-open-section');
            if (sectionId) openSection(sectionId);
        });
    });

    document.querySelectorAll('[data-back-to-menu]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            closeAllSections();
        });
    });

    initGameSection();
    initMySignups();
}

function initMySignups() {
    const myList = document.getElementById('mySignupsList');
    document.getElementById('menu-my-signups')?.addEventListener('click', async () => {
        if (myList) {
            myList.className = 'empty-placeholder';
            myList.innerHTML = 'Загрузка ваших записей...';
        }

        try {
            const res = await apiFetch('/api/signups/my-games');
            const games = Array.isArray(res?.games) ? res.games : [];

            if (games.length === 0) {
                if (myList) {
                    myList.className = 'empty-placeholder';
                    myList.innerHTML = 'Вы пока не записаны ни на один матч.';
                }
                return;
            }

            if (myList) {
                myList.className = '';
                myList.innerHTML = games.map(item => {
                    const g = item.game || {};
                    const isReserve = item.signup_status === 'reserve';
                    const statusText = isReserve ? '⚠️ В резерве' : '✅ В основном составе';
                    const paidText = item.is_paid ? '💳 Оплачено' : '⏳ Не оплачено';
                    const dateStr = escapeHtml(g.date || 'Уточняется');
                    const timeStr = g.time_start ? escapeHtml(g.time_start) : '';
                    const locStr = escapeHtml(g.loc_name || g.venue_name || 'Площадка');
                    const gameId = encodeURIComponent(g.id ?? item.game_id ?? '');

                    return `
                        <a href="index.html?game_id=${gameId}" class="game-card">
                            <div style="font-weight: bold; margin-bottom: 4px; color: inherit;">📅 ${dateStr} ${timeStr}</div>
                            <div style="color: gray; margin-bottom: 6px;">📍 ${locStr}</div>
                            <div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: bold;">
                                <span style="color: ${isReserve ? '#e68a1e' : '#2e9e5b'}">${statusText}</span>
                                <span style="color: ${item.is_paid ? '#2e9e5b' : '#e68a1e'}">${paidText}</span>
                            </div>
                        </a>
                    `;
                }).join('');
            }
        } catch (err) {
            console.error('Failed to load my signups:', err);
            if (myList) {
                myList.className = 'empty-placeholder';
                myList.innerHTML = `
                    <p style="color: #d9534f; font-size: 14px; margin: 0 0 8px;">Не удалось загрузить ваши записи.</p>
                    <p style="color: gray; font-size: 12px; margin: 0;">${escapeHtml(err?.message || '')}</p>
                `;
            }
        }
    });
}
