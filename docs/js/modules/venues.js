import { apiFetch } from '../core/api.js';
import { tg } from '../core/tg.js';

import { apiFetch } from '../core/api.js';
import { tg } from '../core/tg.js';

export async function initVenues() {
    const venueSelect = document.getElementById('venueSelect');
    const venueModal = document.getElementById('venueModal');
    const openVenueModalBtn = document.getElementById('open-venue-modal');
    const closeVenueModalBtn = document.getElementById('close-venue-modal');
    const venueForm = document.getElementById('venueForm');
    const chatSelect = document.getElementById('chatSelect');
    const venueHelperText = document.getElementById('venueHelperText');

    function getActiveChatId() {
        if (chatSelect && chatSelect.value) {
            return chatSelect.value;
        }
        return localStorage.getItem('activeChatId') || '';
    }

    function updateVenueState() {
        const chatId = getActiveChatId();
        const isValid = Boolean(chatId && String(chatId).trim() !== '');

        if (venueSelect) {
            venueSelect.disabled = !isValid;
        }
        if (openVenueModalBtn) {
            openVenueModalBtn.disabled = !isValid;
            openVenueModalBtn.style.opacity = isValid ? '1' : '0.6';
            openVenueModalBtn.style.cursor = isValid ? 'pointer' : 'not-allowed';
        }
        if (venueHelperText) {
            if (isValid) {
                venueHelperText.style.display = 'none';
            } else {
                venueHelperText.style.display = 'block';
                venueHelperText.textContent = '⚠️ Сначала выберите группу';
            }
        }
    }

    async function loadVenues() {
        if (!venueSelect) return;
        const chatId = getActiveChatId();
        
        updateVenueState();

        if (!chatId) {
            venueSelect.innerHTML = '<option value="">-- Сначала выберите группу --</option>';
            return;
        }

        try {
            const url = `/api/venues?chat_id=${encodeURIComponent(chatId)}`;
            const venues = await apiFetch(url);
            venueSelect.innerHTML = '<option value="">-- Выберите площадку --</option>';
            venues.forEach(v => {
                const opt = document.createElement('option');
                opt.value = v.id;
                opt.textContent = v.name;
                opt.dataset.mapUrl = v.map_url;
                venueSelect.appendChild(opt);
            });
        } catch (e) {
            console.error("Failed to load venues:", e);
            venueSelect.innerHTML = '<option value="">Ошибка загрузки площадок</option>';
        }
    }

    updateVenueState();
    await loadVenues();

    window.addEventListener('activeChatChanged', async () => {
        await loadVenues();
    });

    if (chatSelect) {
        chatSelect.addEventListener('change', async () => {
            await loadVenues();
        });
    }

    if (openVenueModalBtn && venueModal) {
        openVenueModalBtn.onclick = () => {
            const chatId = getActiveChatId();
            if (!chatId) {
                tg.showAlert('⚠️ Сначала выберите группу!');
                return;
            }
            venueModal.style.display = 'flex';
        };
    }
    if (closeVenueModalBtn && venueModal) {
        closeVenueModalBtn.onclick = () => { venueModal.style.display = 'none'; };
    }

    if (venueForm) {
        venueForm.onsubmit = async (e) => {
            e.preventDefault();
            const name = document.getElementById('venueName').value;
            const mapUrl = document.getElementById('venueMapUrl').value;
            const chatId = getActiveChatId();

            if (!chatId) {
                tg.showAlert('⚠️ Сначала выберите группу!');
                return;
            }

            try {
                const res = await apiFetch('/api/venues', {
                    method: 'POST',
                    body: JSON.stringify({ chat_id: parseInt(chatId, 10), name, map_url: mapUrl })
                });
                if (res.success) {
                    tg.showAlert("✅ Площадка успешно добавлена!");
                    venueModal.style.display = 'none';
                    venueForm.reset();
                    await loadVenues();
                    if (res.venue && venueSelect) {
                        venueSelect.value = res.venue.id;
                    }
                }
            } catch (err) {
                tg.showAlert(`❌ Ошибка: ${err.message}`);
            }
        };
    }
}


