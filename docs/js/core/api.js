import { tg } from './tg.js';

export const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:10000'
    : 'https://volleyballrender.onrender.com';

export async function apiFetch(url, options = {}) {
    const initData = tg.initData || "";
    const method = options.method || 'GET';
    const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;

    const headers = {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': initData,
        ...(options.headers || {})
    };

    try {
        const response = await fetch(fullUrl, {
            ...options,
            headers
        });

        if (!response.ok) {
            const rawText = await response.text().catch(() => '');
            let errorData = {};
            try {
                errorData = rawText ? JSON.parse(rawText) : {};
            } catch (_) {
                errorData = { detail: rawText };
            }

            const message = errorData.detail || `HTTP error! status: ${response.status}`;
            console.error(`[apiFetch] ${method} ${fullUrl} failed:`, {
                status: response.status,
                hasInitData: Boolean(initData),
                detail: message,
                raw: rawText.slice(0, 500)
            });
            throw new Error(message);
        }

        return await response.json();
    } catch (err) {
        if (!err.message?.startsWith('HTTP error!') && !err.detail) {
            console.error(`[apiFetch] Network/parse error on ${method} ${fullUrl}:`, err);
        }
        throw err;
    }
}