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

    function getSelectedChatId() {
        const val = chatSelect ? String(chatSelect.value || '').trim() : '';
        return val;
    }

    function updateVenueState() {
        const chatId = getSelectedChatId();
        const isValid = chatId !== '';

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
        const chatId = getSelectedChatId();

        updateVenueState();

        if (!chatId) {
            venueSelect.value = '';
            venueSelect.innerHTML = '<option value="">-- Сначала выберите группу --</option>';
            return;
        }

        try {
            const url = `/api/venues?chat_id=${encodeURIComponent(chatId)}`;
            const venues = await apiFetch(url);
            venueSelect.innerHTML = '<option value="">-- Выберите площадку --</option>';
            (Array.isArray(venues) ? venues : []).forEach((v) => {
                const opt = document.createElement('option');
                opt.value = v.id;
                opt.textContent = v.name;
                opt.dataset.mapUrl = v.map_url || '';
                venueSelect.appendChild(opt);
            });
        } catch (e) {
            console.error('Failed to load venues:', e);
            venueSelect.innerHTML = '<option value="">Ошибка загрузки площадок</option>';
        }
    }

    updateVenueState();
    await loadVenues();

    window.addEventListener('activeChatChanged', async (event) => {
        const nextChatId = event?.detail?.chatId;
        if (chatSelect && nextChatId !== undefined && nextChatId !== null) {
            chatSelect.value = String(nextChatId);
        }
        await loadVenues();
    });

    if (chatSelect) {
        chatSelect.addEventListener('change', async () => {
            await loadVenues();
        });
    }

    if (openVenueModalBtn && venueModal) {
        openVenueModalBtn.onclick = () => {
            const chatId = getSelectedChatId();
            if (!chatId) {
                tg.showAlert('⚠️ Сначала выберите группу!');
                return;
            }
            venueModal.style.display = 'flex';
        };
    }

    if (closeVenueModalBtn && venueModal) {
        closeVenueModalBtn.onclick = () => {
            venueModal.style.display = 'none';
        };
    }

    if (venueForm) {
        let isSubmitting = false;
        const submitBtn = venueForm.querySelector('button[type="submit"]');

        venueForm.onsubmit = async (e) => {
            e.preventDefault();
            if (isSubmitting) return;

            const nameInput = document.getElementById('venueName');
            const mapUrlInput = document.getElementById('venueMapUrl');
            const name = (nameInput?.value || '').trim();
            const mapUrl = (mapUrlInput?.value || '').trim();
            const chatId = getSelectedChatId();

            if (!chatId) {
                tg.showAlert('⚠️ Сначала выберите группу!');
                return;
            }
            if (!name || !mapUrl) {
                tg.showAlert('⚠️ Заполните название и ссылку на карту');
                return;
            }

            isSubmitting = true;
            if (submitBtn) submitBtn.disabled = true;

            try {
                const res = await apiFetch('/api/venues', {
                    method: 'POST',
                    body: JSON.stringify({
                        chat_id: parseInt(chatId, 10),
                        name,
                        map_url: mapUrl,
                    }),
                });
                if (res?.success) {
                    tg.showAlert('✅ Площадка успешно добавлена!');
                    venueModal.style.display = 'none';
                    venueForm.reset();
                    await loadVenues();
                    if (res.venue && venueSelect) {
                        venueSelect.value = String(res.venue.id);
                    }
                }
            } catch (err) {
                tg.showAlert(`❌ Ошибка: ${err?.message || 'Failed to fetch'}`);
            } finally {
                isSubmitting = false;
                if (submitBtn) submitBtn.disabled = false;
            }
        };
    }
}