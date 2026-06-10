# HamShack Dashboard

A self-hosted ham radio web dashboard — works with any CHIRP-compatible radio. Built for **VA3CZT** in Etobicoke, ON.

## Features

| Page | Description |
|---|---|
| **Dashboard** | Live solar conditions (SFI, K-index), UTC clock, recent contacts |
| **Repeater Finder** | Pulls open VHF/UHF repeaters near you from RepeaterBook — filterable by band and radius |
| **CHIRP Export** | One-click CSV export formatted for import directly into CHIRP radio programming software |
| **HF Propagation** | Live NOAA solar data, estimated band conditions (160m–6m), MUF estimates for common paths |
| **Contact Log** | Log QSOs with callsign, frequency, mode, RST — export as ADIF for LOTW/other loggers |
| **APRS Map** | Live aprs.fi map centred on your location, APRS setup guide for A36+ |

## Stack

- **Backend:** Python 3 + Flask
- **Data sources:** RepeaterBook API, NOAA Space Weather Prediction Center, aprs.fi
- **Frontend:** Bootstrap 5 (dark), Font Awesome — no JS frameworks, no build step
- **Database:** SQLite (contact log)
- **Compatible radios:** Any CHIRP-supported radio (Talkpod, Baofeng, Yaesu, Kenwood, Icom, and hundreds more)

## Running

```bash
pip install flask requests
python3 app.py
```

App runs on port `8000`, accessible from any device on your LAN at `http://<server-ip>:8000`.

## Running as a systemd service

```bash
sudo cp talkpod.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now talkpod
```

## Connecting your Talkpod A36 Plus

1. Install a **USB programming cable** (Kenwood K-type 2-pin)
2. Install the **CH340 driver** on Windows (from wch-ic.com)
3. Install **CHIRP Next** from chirpmyradio.com
4. In CHIRP: `Radio → Download from Radio`, select your COM port
5. Use the **CHIRP Export** page in this app to get a ready-to-import channel list of repeaters near you

## Finding repeaters

The Repeater Finder page queries RepeaterBook for open FM repeaters within your chosen radius. Each result shows:
- RX frequency, offset direction, CTCSS/PL tone
- Location and distance from your home QTH
- Open/Closed status

Export to CHIRP to program them all into your radio in one shot.

## HF Propagation

The HF page pulls live data from NOAA SWPC every time you load it:
- **SFI** (Solar Flux Index) — higher is better; >150 = excellent HF
- **Kp** (K-index) — lower is better; >4 means geomagnetic storm, bad for HF
- **Band conditions** — colour-coded estimate for 160m through 6m based on SFI + Kp
- **MUF estimates** — approximate Maximum Usable Frequency for common paths from Ontario

For precise path predictions, links to VOACAP, PSKReporter, and DXMaps are provided.

## License

MIT
