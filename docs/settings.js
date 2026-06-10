/* HamShack Dashboard — settings.js
   Stores operator info in localStorage and injects the settings modal.
   Include this script in every page. */

const HS = {
  get() {
    return {
      callsign: localStorage.getItem('hs_callsign') || '',
      lat:      parseFloat(localStorage.getItem('hs_lat')) || null,
      lon:      parseFloat(localStorage.getItem('hs_lon')) || null,
      grid:     localStorage.getItem('hs_grid') || '',
      city:     localStorage.getItem('hs_city') || '',
    };
  },
  save(data) {
    if (data.callsign) localStorage.setItem('hs_callsign', data.callsign.toUpperCase().trim());
    if (data.lat != null) localStorage.setItem('hs_lat', String(data.lat));
    if (data.lon != null) localStorage.setItem('hs_lon', String(data.lon));
    localStorage.setItem('hs_grid', (data.grid || HS.latLonToGrid(data.lat, data.lon)).toUpperCase().trim());
    if (data.city) localStorage.setItem('hs_city', data.city.trim());
  },
  configured() {
    return !!(localStorage.getItem('hs_callsign') && localStorage.getItem('hs_lat'));
  },
  latLonToGrid(lat, lon) {
    if (lat == null || lon == null) return '';
    lon += 180; lat += 90;
    const f = Math.floor, A = n => String.fromCharCode(65 + n);
    return A(f(lon / 20)) + A(f(lat / 10)) +
           String(f((lon % 20) / 2)) + String(f(lat % 10)) +
           A(f((lon % 2) / (2 / 24))) + A(f((lat % 1) / (10 / 24)));
  },
  updateNav() {
    const s = HS.get();
    const el = document.getElementById('navCallsign');
    if (el) el.textContent = s.callsign || '—';
  },
  openSettings() {
    const s = HS.get();
    document.getElementById('hsSetCallsign').value = s.callsign;
    document.getElementById('hsSetLat').value = s.lat || '';
    document.getElementById('hsSetLon').value = s.lon || '';
    document.getElementById('hsSetCity').value = s.city;
    document.getElementById('hsSetGrid').value = s.grid;
    document.getElementById('hsSetError').textContent = '';
    bootstrap.Modal.getOrCreateInstance(document.getElementById('hsSettingsModal')).show();
  },
  saveFromModal() {
    const call = document.getElementById('hsSetCallsign').value.trim().toUpperCase();
    const lat  = parseFloat(document.getElementById('hsSetLat').value);
    const lon  = parseFloat(document.getElementById('hsSetLon').value);
    const city = document.getElementById('hsSetCity').value.trim();
    const grid = document.getElementById('hsSetGrid').value.trim().toUpperCase();
    if (!call) { document.getElementById('hsSetError').textContent = 'Callsign is required.'; return; }
    if (isNaN(lat) || isNaN(lon)) { document.getElementById('hsSetError').textContent = 'Enter valid coordinates (or use GPS).'; return; }
    HS.save({ callsign: call, lat, lon, city, grid: grid || HS.latLonToGrid(lat, lon) });
    bootstrap.Modal.getInstance(document.getElementById('hsSettingsModal')).hide();
    HS.updateNav();
    if (typeof onSettingsSaved === 'function') onSettingsSaved();
  },
  useGPS() {
    if (!navigator.geolocation) { alert('Geolocation not supported.'); return; }
    document.getElementById('hsGpsBtn').innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
    navigator.geolocation.getCurrentPosition(p => {
      const lat = parseFloat(p.coords.latitude.toFixed(4));
      const lon = parseFloat(p.coords.longitude.toFixed(4));
      document.getElementById('hsSetLat').value = lat;
      document.getElementById('hsSetLon').value = lon;
      document.getElementById('hsSetGrid').value = HS.latLonToGrid(lat, lon);
      document.getElementById('hsGpsBtn').innerHTML = '<i class="fa-solid fa-location-dot"></i>';
      // Reverse geocode city
      fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`)
        .then(r => r.json())
        .then(d => {
          const a = d.address || {};
          const city = a.city || a.town || a.village || a.county || '';
          const state = a.state_code || a.state || '';
          if (city) document.getElementById('hsSetCity').value = [city, state].filter(Boolean).join(', ');
        }).catch(() => {});
    }, () => {
      document.getElementById('hsGpsBtn').innerHTML = '<i class="fa-solid fa-location-dot"></i>';
      alert('Location access denied.');
    });
  },
  injectModal() {
    const html = `
<div class="modal fade" id="hsSettingsModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content" style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius)">
      <div class="modal-header" style="border-bottom:1px solid var(--border)">
        <h5 class="modal-title" style="font-family:'JetBrains Mono',monospace;color:var(--cyan);font-size:1rem">
          <i class="fa-solid fa-tower-broadcast me-2"></i>Your Station Setup
        </h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" id="hsModalClose"></button>
      </div>
      <div class="modal-body">
        <p style="font-size:0.85rem;color:var(--text-faint);margin-bottom:1.25rem">
          Enter your info once — saved locally in your browser. No account required.
        </p>
        <div class="mb-3">
          <label style="font-size:0.75rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--text-faint);display:block;margin-bottom:4px">Callsign</label>
          <input type="text" id="hsSetCallsign" class="form-control tp-form-control"
                 placeholder="e.g. VA3CZT" autocapitalize="characters" autocomplete="off" spellcheck="false"
                 style="font-family:'JetBrains Mono',monospace;font-size:1.1rem;letter-spacing:2px;text-transform:uppercase">
        </div>
        <div class="mb-3">
          <label style="font-size:0.75rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--text-faint);display:block;margin-bottom:4px">Location (for weather &amp; repeater distance)</label>
          <div class="d-flex gap-2">
            <input type="number" id="hsSetLat" class="form-control tp-form-control" placeholder="Latitude" step="0.0001">
            <input type="number" id="hsSetLon" class="form-control tp-form-control" placeholder="Longitude" step="0.0001">
            <button class="btn btn-tp-outline" id="hsGpsBtn" onclick="HS.useGPS()" title="Use my GPS location" type="button">
              <i class="fa-solid fa-location-dot"></i>
            </button>
          </div>
        </div>
        <div class="row g-2 mb-3">
          <div class="col-7">
            <label style="font-size:0.75rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--text-faint);display:block;margin-bottom:4px">City / QTH</label>
            <input type="text" id="hsSetCity" class="form-control tp-form-control" placeholder="e.g. Toronto, ON">
          </div>
          <div class="col-5">
            <label style="font-size:0.75rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--text-faint);display:block;margin-bottom:4px">Grid Square</label>
            <input type="text" id="hsSetGrid" class="form-control tp-form-control" placeholder="e.g. FN03"
                   style="font-family:'JetBrains Mono',monospace" autocapitalize="characters" maxlength="6">
          </div>
        </div>
        <div id="hsSetError" style="color:var(--red);font-size:0.82rem;min-height:1.2em"></div>
      </div>
      <div class="modal-footer" style="border-top:1px solid var(--border)">
        <button type="button" class="btn btn-tp w-100" onclick="HS.saveFromModal()">
          <i class="fa-solid fa-floppy-disk me-2"></i>Save &amp; Continue
        </button>
      </div>
    </div>
  </div>
</div>`;
    document.body.insertAdjacentHTML('beforeend', html);
  },
};

document.addEventListener('DOMContentLoaded', () => {
  HS.injectModal();
  HS.updateNav();

  // Auto-compute grid when lat/lon change
  ['hsSetLat','hsSetLon'].forEach(id => {
    document.getElementById(id)?.addEventListener('input', () => {
      const lat = parseFloat(document.getElementById('hsSetLat').value);
      const lon = parseFloat(document.getElementById('hsSetLon').value);
      if (!isNaN(lat) && !isNaN(lon)) {
        document.getElementById('hsSetGrid').value = HS.latLonToGrid(lat, lon);
      }
    });
  });

  // Auto-uppercase callsign
  document.getElementById('hsSetCallsign')?.addEventListener('input', e => {
    const pos = e.target.selectionStart;
    e.target.value = e.target.value.toUpperCase();
    e.target.setSelectionRange(pos, pos);
  });

  // Disable close button on first-time setup
  const closeBtn = document.getElementById('hsModalClose');
  if (!HS.configured()) {
    if (closeBtn) closeBtn.style.display = 'none';
    bootstrap.Modal.getOrCreateInstance(document.getElementById('hsSettingsModal')).show();
  }
});
