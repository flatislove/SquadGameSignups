const tg = window.Telegram?.WebApp ?? null;

if (tg) {
    try {
        tg.ready?.();
        tg.expand?.();
    } catch (_) {
    }
}

export function getStartParam() {
    const value = tg?.initDataUnsafe?.start_param;
    return typeof value === 'string' ? value.trim() : '';
}

export function getStartGameId() {
    const startParam = getStartParam();
    if (startParam.startsWith('game_')) {
        return startParam.slice('game_'.length).trim() || null;
    }
    return null;
}

export { tg };