from flask import Flask, render_template, request, jsonify, send_file
import requests
import sqlite3
import csv
import io
from datetime import datetime, timezone

app = Flask(__name__)

DEFAULT_LAT = 43.6490
DEFAULT_LON = -79.5469
CALLSIGN = "VA3CZT"
RB_HEADERS = {"User-Agent": "TalkpodApp/1.0 VA3CZT"}


def get_db():
    conn = sqlite3.connect("talkpod.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT NOT NULL,
            callsign TEXT NOT NULL,
            frequency REAL,
            band TEXT,
            mode TEXT,
            rst_sent TEXT,
            rst_recv TEXT,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    conn = get_db()
    contact_count = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    recent = conn.execute(
        "SELECT * FROM contacts ORDER BY datetime DESC LIMIT 5"
    ).fetchall()
    conn.close()
    return render_template("index.html", contact_count=contact_count,
                           recent=[dict(r) for r in recent], callsign=CALLSIGN)


@app.route("/repeaters")
def repeaters():
    return render_template("repeaters.html")


@app.route("/hf")
def hf():
    return render_template("hf.html")


@app.route("/log")
def log():
    conn = get_db()
    contacts = conn.execute(
        "SELECT * FROM contacts ORDER BY datetime DESC LIMIT 200"
    ).fetchall()
    conn.close()
    return render_template("log.html", contacts=[dict(c) for c in contacts])


@app.route("/aprs")
def aprs():
    return render_template("aprs.html")


# ── API ────────────────────────────────────────────────────────────────────────

@app.route("/api/repeaters")
def api_repeaters():
    lat = request.args.get("lat", DEFAULT_LAT)
    lon = request.args.get("lon", DEFAULT_LON)
    distance = request.args.get("distance", 50)
    band = request.args.get("band", "%25")

    url = (
        "https://www.repeaterbook.com/api/export.php"
        f"?country=Canada&state=Ontario"
        f"&band={band}&freq=%25&use=OPEN"
        f"&near_lat={lat}&near_lon={lon}"
        f"&distance={distance}&Dunit=km"
        f"&call=%25&status_id=%25&features=%25"
        f"&tone=%25&digi=false&format=json"
    )

    try:
        resp = requests.get(url, timeout=12, headers=RB_HEADERS)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export/chirp")
def export_chirp():
    lat = request.args.get("lat", DEFAULT_LAT)
    lon = request.args.get("lon", DEFAULT_LON)
    url = (
        "https://www.repeaterbook.com/api/export.php"
        f"?country=Canada&state=Ontario"
        f"&band=%25&freq=%25&use=OPEN"
        f"&near_lat={lat}&near_lon={lon}"
        f"&distance=80&Dunit=km"
        f"&call=%25&status_id=%25&features=%25"
        f"&tone=%25&digi=false&format=json"
    )

    try:
        resp = requests.get(url, timeout=12, headers=RB_HEADERS)
        repeaters = resp.json().get("results", [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    output = io.StringIO()
    w = csv.writer(output)
    w.writerow([
        "Location", "Name", "Frequency", "Duplex", "Offset",
        "Tone", "rToneFreq", "cToneFreq", "DtcsCode", "DtcsPolarity",
        "Mode", "TStep", "Skip", "Comment",
        "URCALL", "RPT1CALL", "RPT2CALL", "DVCODE"
    ])

    for i, r in enumerate(repeaters[:128]):
        try:
            rx = float(r.get("Frequency") or 0)
            tx_raw = r.get("Input Freq") or r.get("Input_Freq") or rx
            tx = float(tx_raw)
            offset = abs(rx - tx)
            duplex = "+" if tx > rx else "-" if tx < rx else ""
            ctcss = r.get("CTCSS") or r.get("PL") or ""
            tone_mode = "Tone" if ctcss else ""
            name = ((r.get("Callsign") or "") + " " + (r.get("Landmark") or ""))[:8].strip()
            comment = (r.get("Landmark") or r.get("City") or "")[:64]
            w.writerow([
                i, name, f"{rx:.5f}", duplex, f"{offset:.5f}",
                tone_mode, ctcss if ctcss else "88.5", "88.5",
                "023", "NN", "FM", "5.00", "", comment,
                "", "", "", ""
            ])
        except Exception:
            continue

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="talkpod_chirp.csv"
    )


@app.route("/api/solar")
def api_solar():
    results = {}

    # Solar flux — returns list: [{flux, time_tag}]
    try:
        r = requests.get("https://services.swpc.noaa.gov/products/summary/10cm-flux.json", timeout=8)
        data = r.json()
        latest = data[-1] if isinstance(data, list) and data else data
        results["sfi"] = latest.get("flux") if isinstance(latest, dict) else None
    except Exception:
        results["sfi"] = None

    # K-index history — list of {time_tag, Kp, a_running}; take most recent
    try:
        r = requests.get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json", timeout=8)
        data = r.json()
        results["khistory"] = data[-25:] if isinstance(data, list) else []
        results["kp"] = data[-1]["Kp"] if data else None
        results["ap"] = data[-1]["a_running"] if data else None
    except Exception:
        results["khistory"] = []
        results["kp"] = None
        results["ap"] = None

    # Solar wind speed — returns list: [{proton_speed, time_tag}]
    try:
        r = requests.get("https://services.swpc.noaa.gov/products/summary/solar-wind-speed.json", timeout=8)
        data = r.json()
        latest = data[-1] if isinstance(data, list) and data else data
        results["wind_speed"] = latest.get("proton_speed") if isinstance(latest, dict) else None
    except Exception:
        results["wind_speed"] = None

    # Sunspot report — list of spot observations; count unique regions as proxy for SSN
    try:
        r = requests.get("https://services.swpc.noaa.gov/json/sunspot_report.json", timeout=8)
        data = r.json()
        if isinstance(data, list) and data:
            # Sum area from most recent timestamp as SSN proxy
            latest_ts = data[-1].get("time_tag") if data else None
            latest_spots = [s for s in data if s.get("time_tag") == latest_ts]
            results["ssn"] = sum(s.get("Numspot", 0) for s in latest_spots)
        else:
            results["ssn"] = None
    except Exception:
        results["ssn"] = None

    return jsonify(results)


@app.route("/api/log", methods=["GET"])
def api_log_get():
    conn = get_db()
    contacts = conn.execute(
        "SELECT * FROM contacts ORDER BY datetime DESC LIMIT 200"
    ).fetchall()
    conn.close()
    return jsonify([dict(c) for c in contacts])


@app.route("/api/log", methods=["POST"])
def api_log_add():
    data = request.json or {}
    if not data.get("callsign"):
        return jsonify({"error": "callsign required"}), 400

    dt = data.get("datetime") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO contacts (datetime, callsign, frequency, band, mode, rst_sent, rst_recv, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        dt,
        data["callsign"].upper().strip(),
        data.get("frequency"),
        data.get("band", ""),
        data.get("mode", "FM"),
        data.get("rst_sent", "59"),
        data.get("rst_recv", "59"),
        data.get("notes", ""),
    ))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"status": "ok", "id": new_id})


@app.route("/api/log/<int:cid>", methods=["DELETE"])
def api_log_delete(cid):
    conn = get_db()
    conn.execute("DELETE FROM contacts WHERE id = ?", (cid,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/log/export/adif")
def export_adif():
    conn = get_db()
    contacts = conn.execute("SELECT * FROM contacts ORDER BY datetime DESC").fetchall()
    conn.close()

    lines = ["<ADIF_VER:5>3.1.0\n<PROGRAMID:8>TALKPOD\n<EOH>\n"]
    for c in contacts:
        dt_str = (c["datetime"] or "").replace("-", "").replace(":", "").replace("T", " ").split(".")[0]
        date_part = dt_str[:8]
        time_part = dt_str[9:15] if len(dt_str) > 9 else "000000"
        freq_mhz = f"{float(c['frequency']):.4f}" if c["frequency"] else ""
        call = c["callsign"]
        line = (
            f"<CALL:{len(call)}>{call}"
            f"<QSO_DATE:8>{date_part}"
            f"<TIME_ON:6>{time_part}"
            f"<FREQ:{len(freq_mhz)}>{freq_mhz}" if freq_mhz else ""
            f"<MODE:{len(c['mode'] or 'FM')}>{c['mode'] or 'FM'}"
            f"<RST_SENT:{len(c['rst_sent'] or '59')}>{c['rst_sent'] or '59'}"
            f"<RST_RCVD:{len(c['rst_recv'] or '59')}>{c['rst_recv'] or '59'}"
            f"<EOR>\n"
        )
        lines.append(line)

    content = "".join(lines)
    return send_file(
        io.BytesIO(content.encode()),
        mimetype="text/plain",
        as_attachment=True,
        download_name="talkpod_log.adi"
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=False)
