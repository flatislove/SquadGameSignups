import { tg } from './tg.js';

// Render backend URL configuration
export const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:10000'
    : 'https://squadgamesignups.onrender.com';

export async function apiFetch(url, options = {}) {
    const initData = tg.initData || "";
    const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
    
    const headers = {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': initData,
        ...(options.headers || {})
    };

    const response = await fetch(fullUrl, {
        ...options,
        headers
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    return await response.json();
}

