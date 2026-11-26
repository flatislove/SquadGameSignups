import { apiFetch } from '../core/api.js';
import { tg } from '../core/tg.js';

export async function initVenues() {
    const venueSelect = document.getElementById('venueSelect');
    const venueModal = document.getElementById('venueModal');
    const openVenueModalBtn = document.getElementById('open-venue-modal');
    const closeVenueModalBtn = document.getElementById('close-venue-modal');
    const venueForm = document.getElementById('venueForm');

    async function loadVenues() {
        if (!venueSelect) return;
        try {
            const venues = await apiFetch('/api/venues');
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

    await loadVenues();

    if (openVenueModalBtn && venueModal) {
        openVenueModalBtn.onclick = () => { venueModal.style.display = 'flex'; };
    }
    if (closeVenueModalBtn && venueModal) {
        closeVenueModalBtn.onclick = () => { venueModal.style.display = 'none'; };
    }

    if (venueForm) {
        venueForm.onsubmit = async (e) => {
            e.preventDefault();
            const name = document.getElementById('venueName').value;
            const mapUrl = document.getElementById('venueMapUrl').value;

            try {
                const res = await apiFetch('/api/venues', {
                    method: 'POST',
                    body: JSON.stringify({ name, map_url: mapUrl })
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
