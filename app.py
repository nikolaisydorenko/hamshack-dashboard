from flask import Flask, render_template, request, jsonify, send_file
import requests
import sqlite3
import csv
import io
import math
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

app = Flask(__name__)

_repeater_cache = {"data": None, "ts": 0}
CACHE_TTL = 6 * 3600

WMO_CODES = {
    0:("Clear sky","fa-sun","green"), 1:("Mainly clear","fa-sun","green"),
    2:("Partly cloudy","fa-cloud-sun","yellow"), 3:("Overcast","fa-cloud","muted"),
    45:("Fog","fa-smog","muted"), 48:("Freezing fog","fa-smog","muted"),
    51:("Light drizzle","fa-cloud-drizzle","blue"), 53:("Drizzle","fa-cloud-drizzle","blue"),
    55:("Heavy drizzle","fa-cloud-drizzle","blue"),
    61:("Slight rain","fa-cloud-rain","blue"), 63:("Rain","fa-cloud-rain","blue"),
    65:("Heavy rain","fa-cloud-showers-heavy","blue"),
    71:("Slight snow","fa-snowflake","white"), 73:("Snow","fa-snowflake","white"),
    75:("Heavy snow","fa-snowflake","white"), 77:("Snow grains","fa-snowflake","white"),
    80:("Showers","fa-cloud-showers-water","blue"), 81:("Showers","fa-cloud-showers-water","blue"),
    82:("Heavy showers","fa-cloud-showers-heavy","blue"),
    85:("Snow showers","fa-snowflake","white"), 86:("Heavy snow showers","fa-snowflake","white"),
    95:("Thunderstorm","fa-bolt","yellow"), 96:("Thunderstorm+hail","fa-bolt","yellow"),
    99:("Thunderstorm+hail","fa-bolt","yellow"),
}

WIND_DIRS = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]


def get_db():
    conn = sqlite3.connect("talkpod.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        datetime TEXT NOT NULL, callsign TEXT NOT NULL,
        frequency REAL, band TEXT, mode TEXT,
        rst_sent TEXT, rst_recv TEXT, notes TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT)""")
    conn.commit()
    conn.close()


def get_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    s = {r["key"]: r["value"] for r in rows}
    lat = float(s["home_lat"]) if s.get("home_lat") else None
    lon = float(s["home_lon"]) if s.get("home_lon") else None
    return {
        "callsign":   s.get("callsign", ""),
        "home_lat":   lat,
        "home_lon":   lon,
        "home_label": s.get("home_label", ""),
        "configured": bool(s.get("callsign")),
    }


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def fetch_hearham():
    now = time.time()
    if _repeater_cache["data"] is None or now - _repeater_cache["ts"] > CACHE_TTL:
        r = requests.get("https://hearham.com/api/repeaters/v1?lat=0&lng=0&range=99999",
                         timeout=30, headers={"User-Agent": "HamShackDashboard/1.0"})
        _repeater_cache["data"] = r.json()
        _repeater_cache["ts"] = now
    return _repeater_cache["data"]


def wind_dir(deg):
    return WIND_DIRS[round(deg / 22.5) % 16]


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    conn = get_db()
    contact_count = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    recent = conn.execute("SELECT * FROM contacts ORDER BY datetime DESC LIMIT 5").fetchall()
    conn.close()
    settings = get_settings()
    return render_template("index.html", contact_count=contact_count,
                           recent=[dict(r) for r in recent], settings=settings)

@app.route("/repeaters")
def repeaters():
    return render_template("repeaters.html", settings=get_settings())

@app.route("/hf")
def hf():
    return render_template("hf.html", settings=get_settings())

@app.route("/log")
def log():
    conn = get_db()
    contacts = conn.execute("SELECT * FROM contacts ORDER BY datetime DESC LIMIT 200").fetchall()
    conn.close()
    return render_template("log.html", contacts=[dict(c) for c in contacts], settings=get_settings())

@app.route("/aprs")
def aprs():
    return render_template("aprs.html", settings=get_settings())

@app.route("/settings")
def settings_page():
    return render_template("settings.html", settings=get_settings())

@app.route("/tools/callsign")
def tool_callsign():
    return render_template("callsign.html", settings=get_settings())

@app.route("/tools/antenna")
def tool_antenna():
    return render_template("antenna.html", settings=get_settings())

@app.route("/tools/bandplan")
def tool_bandplan():
    return render_template("bandplan.html", settings=get_settings())

@app.route("/dx")
def dx():
    return render_template("dx.html", settings=get_settings())

@app.route("/events")
def events():
    return render_template("events.html", settings=get_settings())


# ── API ────────────────────────────────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    return jsonify(get_settings())

@app.route("/api/settings", methods=["POST"])
def api_settings_save():
    data = request.json or {}
    conn = get_db()
    for key in ("callsign", "home_lat", "home_lon", "home_label"):
        if key in data:
            val = str(data[key]).strip().upper() if key == "callsign" else str(data[key]).strip()
            conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                         (key, val))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route("/api/geocode")
def api_geocode():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "query required"}), 400
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={"q": q, "format": "json", "limit": 1},
                         headers={"User-Agent": "HamShackDashboard/1.0"}, timeout=8)
        results = r.json()
        if not results:
            return jsonify({"error": "not found"}), 404
        hit = results[0]
        return jsonify({"lat": float(hit["lat"]), "lon": float(hit["lon"]),
                        "label": hit.get("display_name", q)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/repeaters")
def api_repeaters():
    try:
        lat = float(request.args.get("lat", 0))
        lon = float(request.args.get("lon", 0))
        dist_km = float(request.args.get("distance", 50))
        band = request.args.get("band", "all")
    except ValueError:
        return jsonify({"error": "invalid parameters"}), 400
    if lat == 0 and lon == 0:
        return jsonify({"error": "location required"}), 400
    try:
        all_reps = fetch_hearham()
    except Exception as e:
        return jsonify({"error": f"Could not fetch repeater data: {e}"}), 500

    results = []
    for r in all_reps:
        try:
            rlat, rlon = float(r["latitude"]), float(r["longitude"])
            d = haversine(lat, lon, rlat, rlon)
            if d > dist_km:
                continue
            freq_hz = int(r.get("frequency") or 0)
            off_hz  = int(r.get("offset") or 0)
            freq_mhz = freq_hz / 1e6
            if band == "2m" and not (144 <= freq_mhz <= 148): continue
            if band == "70cm" and not (420 <= freq_mhz <= 450): continue
            if band == "6m" and not (50 <= freq_mhz <= 54): continue
            if band == "10m" and not (28 <= freq_mhz <= 30): continue
            results.append({
                "callsign": r.get("callsign",""), "frequency": round(freq_mhz,4),
                "offset_hz": off_hz, "offset_mhz": round(off_hz/1e6,3),
                "ctcss": r.get("encode") or "", "mode": r.get("mode","FM"),
                "city": r.get("city",""), "distance": round(d,1),
            })
        except Exception:
            continue
    results.sort(key=lambda x: x["distance"])
    return jsonify({"count": len(results), "results": results[:200]})

@app.route("/api/export/chirp")
def export_chirp():
    try:
        lat = float(request.args.get("lat", 0))
        lon = float(request.args.get("lon", 0))
        dist_km = float(request.args.get("distance", 80))
    except ValueError:
        return jsonify({"error": "invalid parameters"}), 400
    try:
        all_reps = fetch_hearham()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    nearby = []
    for r in all_reps:
        try:
            d = haversine(lat, lon, float(r["latitude"]), float(r["longitude"]))
            if d <= dist_km: nearby.append((d, r))
        except Exception:
            continue
    nearby.sort(key=lambda x: x[0])

    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["Location","Name","Frequency","Duplex","Offset","Tone","rToneFreq",
                "cToneFreq","DtcsCode","DtcsPolarity","Mode","TStep","Skip","Comment",
                "URCALL","RPT1CALL","RPT2CALL","DVCODE"])
    for i, (d, r) in enumerate(nearby[:128]):
        try:
            freq_mhz = float(r.get("frequency",0)) / 1e6
            off_hz   = float(r.get("offset",0))
            off_mhz  = abs(off_hz) / 1e6
            duplex   = "+" if off_hz > 0 else "-" if off_hz < 0 else ""
            ctcss    = r.get("encode") or ""
            tone_mode = "Tone" if ctcss and float(ctcss) > 0 else ""
            w.writerow([i, (r.get("callsign") or "")[:8], f"{freq_mhz:.5f}", duplex,
                        f"{off_mhz:.5f}", tone_mode,
                        ctcss if (ctcss and float(ctcss) > 0) else "88.5", "88.5",
                        "023","NN", r.get("mode","FM"),"5.00","",
                        (r.get("city") or "")[:64], "","","",""])
        except Exception:
            continue
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype="text/csv",
                     as_attachment=True, download_name="hamshack_chirp.csv")

@app.route("/api/solar")
def api_solar():
    results = {}
    try:
        r = requests.get("https://services.swpc.noaa.gov/products/summary/10cm-flux.json", timeout=8)
        data = r.json()
        latest = data[-1] if isinstance(data, list) and data else data
        results["sfi"] = latest.get("flux") if isinstance(latest, dict) else None
    except Exception:
        results["sfi"] = None
    try:
        r = requests.get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json", timeout=8)
        data = r.json()
        results["khistory"] = data[-25:] if isinstance(data, list) else []
        results["kp"] = data[-1]["Kp"] if data else None
        results["ap"] = data[-1]["a_running"] if data else None
    except Exception:
        results["khistory"] = []; results["kp"] = None; results["ap"] = None
    try:
        r = requests.get("https://services.swpc.noaa.gov/products/summary/solar-wind-speed.json", timeout=8)
        data = r.json()
        latest = data[-1] if isinstance(data, list) and data else data
        results["wind_speed"] = latest.get("proton_speed") if isinstance(latest, dict) else None
    except Exception:
        results["wind_speed"] = None
    try:
        r = requests.get("https://services.swpc.noaa.gov/json/sunspot_report.json", timeout=8)
        data = r.json()
        if isinstance(data, list) and data:
            latest_ts = data[-1].get("time_tag")
            latest_spots = [s for s in data if s.get("time_tag") == latest_ts]
            results["ssn"] = sum(s.get("Numspot", 0) for s in latest_spots)
        else:
            results["ssn"] = None
    except Exception:
        results["ssn"] = None
    return jsonify(results)

@app.route("/api/weather")
def api_weather():
    s = get_settings()
    if not s["home_lat"]:
        return jsonify({"error": "location not configured"}), 400
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": s["home_lat"], "longitude": s["home_lon"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,wind_direction_10m,weather_code,precipitation",
            "wind_speed_unit": "kmh", "temperature_unit": "celsius",
            "timezone": "auto", "forecast_days": 1
        }, timeout=8)
        data = r.json()
        c = data.get("current", {})
        code = c.get("weather_code", 0)
        desc, icon, color = WMO_CODES.get(code, ("Unknown","fa-question","muted"))
        wdir = c.get("wind_direction_10m", 0)
        return jsonify({
            "temp":       c.get("temperature_2m"),
            "feels_like": c.get("apparent_temperature"),
            "humidity":   c.get("relative_humidity_2m"),
            "wind_kmh":   c.get("wind_speed_10m"),
            "wind_dir":   wind_dir(wdir),
            "wind_deg":   wdir,
            "precip":     c.get("precipitation"),
            "condition":  desc,
            "icon":       icon,
            "icon_color": color,
            "location":   s["home_label"],
            "time":       c.get("time"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/callsign")
def api_callsign():
    call = request.args.get("call", "").strip().upper()
    if not call:
        return jsonify({"error": "callsign required"}), 400
    try:
        r = requests.get(f"http://api.hamdb.org/v1/json/{call}",
                         headers={"User-Agent": "HamShackDashboard/1.0"}, timeout=8)
        data = r.json()
        cs = data.get("hamdb", {}).get("callsign", {})
        if not cs or cs.get("call") in (None, "NOT_FOUND"):
            return jsonify({"error": "Callsign not found"}), 404
        return jsonify({
            "call":    cs.get("call",""),
            "name":    f"{cs.get('fname','')} {cs.get('name','')}".strip(),
            "country": cs.get("country",""),
            "state":   cs.get("state",""),
            "grid":    cs.get("grid",""),
            "class":   cs.get("class",""),
            "expires": cs.get("expires",""),
            "email":   cs.get("email",""),
            "addr":    f"{cs.get('addr1','')} {cs.get('addr2','')}".strip(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/dx")
def api_dx():
    band = request.args.get("band", "all")
    try:
        r = requests.get("https://www.dxsummit.fi/api/v1/spots",
                         params={"limit": 100},
                         headers={"User-Agent": "HamShackDashboard/1.0"}, timeout=10)
        spots = r.json()
        if band != "all":
            spots = [s for s in spots if s.get("band","").lower() == band.lower()]
        return jsonify(spots[:80])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/pota")
def api_pota():
    try:
        r = requests.get("https://api.pota.app/spot/activator",
                         headers={"User-Agent": "HamShackDashboard/1.0"}, timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/contests")
def api_contests():
    try:
        r = requests.get("https://www.contestcalendar.com/weeklycalcgi.php",
                         params={"output": "rss"},
                         headers={"User-Agent": "HamShackDashboard/1.0"}, timeout=10)
        root = ET.fromstring(r.content)
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        items = []
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            desc  = item.findtext("description", "")
            link  = item.findtext("link", "")
            date  = item.findtext("pubDate", "") or item.findtext("dc:date", "", ns)
            items.append({"title": title, "description": desc, "link": link, "date": date})
        return jsonify(items[:30])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/log", methods=["GET"])
def api_log_get():
    conn = get_db()
    contacts = conn.execute("SELECT * FROM contacts ORDER BY datetime DESC LIMIT 200").fetchall()
    conn.close()
    return jsonify([dict(c) for c in contacts])

@app.route("/api/log", methods=["POST"])
def api_log_add():
    data = request.json or {}
    if not data.get("callsign"):
        return jsonify({"error": "callsign required"}), 400
    dt = data.get("datetime") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_db()
    cur = conn.execute("""INSERT INTO contacts (datetime,callsign,frequency,band,mode,rst_sent,rst_recv,notes)
                          VALUES (?,?,?,?,?,?,?,?)""",
                       (dt, data["callsign"].upper().strip(), data.get("frequency"),
                        data.get("band",""), data.get("mode","FM"),
                        data.get("rst_sent","59"), data.get("rst_recv","59"), data.get("notes","")))
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
    settings = get_settings()
    conn = get_db()
    contacts = conn.execute("SELECT * FROM contacts ORDER BY datetime DESC").fetchall()
    conn.close()
    prog = "HAMSHACK"
    lines = [f"<ADIF_VER:5>3.1.0\n<PROGRAMID:{len(prog)}>{prog}\n<EOH>\n"]
    for c in contacts:
        dt_str = (c["datetime"] or "").replace("-","").replace(":","").replace("T"," ").split(".")[0]
        date_part = dt_str[:8]
        time_part = dt_str[9:15] if len(dt_str) > 9 else "000000"
        freq_mhz = f"{float(c['frequency']):.4f}" if c["frequency"] else ""
        call = c["callsign"]; mode = c["mode"] or "FM"
        rst_s = c["rst_sent"] or "59"; rst_r = c["rst_recv"] or "59"
        parts = [f"<CALL:{len(call)}>{call}", f"<QSO_DATE:8>{date_part}",
                 f"<TIME_ON:6>{time_part}", f"<MODE:{len(mode)}>{mode}",
                 f"<RST_SENT:{len(rst_s)}>{rst_s}", f"<RST_RCVD:{len(rst_r)}>{rst_r}"]
        if freq_mhz: parts.append(f"<FREQ:{len(freq_mhz)}>{freq_mhz}")
        if settings["callsign"]:
            op = settings["callsign"]
            parts.append(f"<OPERATOR:{len(op)}>{op}")
        parts.append("<EOR>")
        lines.append("".join(parts) + "\n")
    content = "".join(lines)
    return send_file(io.BytesIO(content.encode()), mimetype="text/plain",
                     as_attachment=True, download_name="hamshack_log.adi")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=False)
