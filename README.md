# HamShack Dashboard

A self-hosted web dashboard for amateur radio operators. Built with Flask and SQLite — runs on a Raspberry Pi, a home server, or a Proxmox LXC container. No cloud account required.

**Live demo:** *(self-hosted — clone and run your own)*

---

## Features

### Dashboard
- Live solar conditions: SFI, K-index, A-index, X-ray flux
- UTC clock
- Current weather at your QTH (temperature, humidity, wind)
- Quick-access links to all pages

### Repeater Finder
- 141+ local repeaters with exact GPS tower coordinates
- Filter by band (2m / 70cm) and search radius
- Sorted by distance from your home QTH
- Import repeaters from a RepeaterBook CSV export or a KML file
- Add custom repeaters manually via the web UI
- One-click **CHIRP CSV export** to program your radio directly

### HF Propagation
- Live NOAA solar data
- Band condition estimates for 160m through 6m
- MUF estimates for paths from your region
- Links to VOACAP, PSKReporter, and DXMaps

### DX Cluster
- Live DX spots via DX Watch
- Filter by band (160m through 70cm)
- Colour-coded band badges
- Auto-refreshes every 60 seconds

### Contact Log
- Log QSOs with callsign, frequency, mode, and RST report
- Export as ADIF for LoTW, QRZ, or any other logger

### Events & Contests
- Upcoming ham radio contests from the Contest Calendar
- Live POTA activations with park info and frequency
- Auto-refreshes every 90 seconds

### Tools
- **Callsign Lookup** — FCC database for US calls, DXCC info for all others
- **Antenna Calculator** — dipole, quarter-wave, 5/8-wave, full-wave loop, 3-element Yagi with velocity factor slider and band quick-select
- **Band Plan** — HF and VHF/UHF Canadian band plan with FT8/FT4/WSPR frequencies

### APRS
- Live APRS.fi map centred on your QTH
- APRS setup guide

---

## Quick Start

```bash
git clone https://github.com/nikolaisydorenko/hamshack-dashboard.git
cd hamshack-dashboard
pip install -r requirements.txt
python3 app.py
```

Open `http://localhost:8000` in your browser. On first run, go to **Settings** and enter your callsign and home coordinates.

---

## Running as a Service (Linux)

```bash
sudo cp talkpod.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now talkpod
```

The app will start automatically on boot and be accessible from any device on your network at `http://<server-ip>:8000`.

---

## Importing Your Local Repeaters

The app ships with a bundled repeater database for the Greater Toronto Area. To add your own region:

1. Export a **CSV** from [RepeaterBook](https://www.repeaterbook.com) (free account required)
2. On the Repeater Finder page, click the upload icon and select the CSV
3. Duplicates are automatically skipped

You can also import a **KML** file (e.g. from Google Maps) with exact tower GPS coordinates, or add individual repeaters via the **+** button.

---

## Stack

| | |
|---|---|
| Backend | Python 3 + Flask |
| Database | SQLite |
| Frontend | Bootstrap 5, Font Awesome 6, Leaflet.js |
| Fonts | DM Sans + JetBrains Mono |
| Solar data | NOAA Space Weather Prediction Center |
| DX spots | DX Watch |
| Weather | Open-Meteo (no API key needed) |
| Callsign data | callook.info (US), HamQTH DXCC (international) |

No build step. No Node.js. No API keys required for basic operation.

---

## License

MIT — free to use, modify, and share.

Built by **VA3CZT** — Nikolai, Etobicoke, ON.
