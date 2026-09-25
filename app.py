import os
import platform
import re
import sqlite3
import subprocess
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, render_template, request


# =========================================================
# KONFIGURASI
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "monitoring.db")

HOST = "127.0.0.1"
PORT = 5000
MONITOR_INTERVAL = 5

# Status latency:
# <= 30 ms  : ONLINE
# > 30 ms   : SLOW
# OFFLINE hanya setelah RTO 4 kali berturut-turut.
LATENCY_NORMAL = 30
LATENCY_HIGH = 100
RTO_OFFLINE_THRESHOLD = 4
HISTORY_LIMIT = 120


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)


# =========================================================
# DATABASE
# =========================================================

def get_db():
    connection = sqlite3.connect(DATABASE, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _column_exists(connection, table_name, column_name):
    columns = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()
    return any(column["name"] == column_name for column in columns)


def init_database():
    """Buat tabel dan lakukan migrasi ringan untuk database lama."""
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL,
            ip_address TEXT NOT NULL UNIQUE,
            description TEXT,
            status TEXT DEFAULT 'UNKNOWN',
            latency REAL,
            checked_at TEXT,
            rto_count INTEGER NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monitoring_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            latency REAL,
            checked_at TEXT NOT NULL,
            rto_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(device_id)
                REFERENCES devices(id)
                ON DELETE CASCADE
        )
    """)

    # Database project lama belum memiliki kolom rto_count.
    if not _column_exists(connection, "devices", "rto_count"):
        cursor.execute(
            "ALTER TABLE devices ADD COLUMN rto_count INTEGER NOT NULL DEFAULT 0"
        )

    if not _column_exists(connection, "monitoring_logs", "rto_count"):
        cursor.execute(
            "ALTER TABLE monitoring_logs ADD COLUMN rto_count INTEGER NOT NULL DEFAULT 0"
        )

    connection.commit()
    connection.close()


# =========================================================
# WAKTU
# =========================================================

def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =========================================================
# PING
# =========================================================

# Mendukung output umum Windows/Linux, termasuk "time<1ms" dan "time=2.3 ms".
PING_TIME_PATTERN = re.compile(
    r"(?:time|waktu)\s*([=<])\s*([0-9]+(?:[.,][0-9]+)?)\s*ms",
    re.IGNORECASE,
)


def _extract_ping_latency(output):
    match = PING_TIME_PATTERN.search(output or "")
    if not match:
        return None

    operator = match.group(1)
    value = float(match.group(2).replace(",", "."))

    # Windows kadang menampilkan time<1ms. Nilai 0.5 dipakai sebagai
    # representasi numerik agar grafik tetap dapat digambar.
    if operator == "<" and value <= 1:
        value = 0.5

    return round(value, 2)


def ping_device(ip_address):
    """
    Melakukan satu ICMP ping.

    Nilai latency diambil dari RTT yang dilaporkan perintah ping, bukan dari
    total waktu eksekusi subprocess. Ini membuat angka latency lebih akurat.
    """
    system = platform.system().lower()

    try:
        if system == "windows":
            command = ["ping", "-n", "1", "-w", "1000", ip_address]
        else:
            command = ["ping", "-c", "1", "-W", "1", ip_address]

        start_time = time.perf_counter()
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        if result.returncode != 0:
            return None

        output = f"{result.stdout}\n{result.stderr}"
        parsed_latency = _extract_ping_latency(output)

        if parsed_latency is not None:
            return parsed_latency

        # Fallback jika format output OS tidak dikenali, tetapi ping berhasil.
        return round(elapsed_ms, 2)

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    except Exception as error:
        print(f"[PING ERROR] {ip_address}: {error}")
        return None


# =========================================================
# STATUS DAN RTO
# =========================================================

def determine_status(latency, rto_count):
    """
    Aturan status:
      - Ping berhasil <= 30 ms : ONLINE
      - Ping berhasil > 30 ms  : SLOW
      - RTO 1-3 kali           : SLOW
      - RTO >= 4 kali          : OFFLINE
    """
    if latency is None:
        if rto_count >= RTO_OFFLINE_THRESHOLD:
            return "OFFLINE"
        return "SLOW"

    if latency <= LATENCY_NORMAL:
        return "ONLINE"

    return "SLOW"


# =========================================================
# MONITORING SATU DEVICE
# =========================================================

def monitor_device(device_id, ip_address, previous_rto_count=0):
    latency = ping_device(ip_address)

    if latency is None:
        rto_count = min(
            int(previous_rto_count or 0) + 1,
            RTO_OFFLINE_THRESHOLD,
        )
    else:
        rto_count = 0

    status = determine_status(latency, rto_count)
    checked_at = current_time()

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE devices
        SET status = ?,
            latency = ?,
            checked_at = ?,
            rto_count = ?
        WHERE id = ?
    """, (
        status,
        latency,
        checked_at,
        rto_count,
        device_id,
    ))

    cursor.execute("""
        INSERT INTO monitoring_logs
            (device_id, status, latency, checked_at, rto_count)
        VALUES (?, ?, ?, ?, ?)
    """, (
        device_id,
        status,
        latency,
        checked_at,
        rto_count,
    ))

    connection.commit()
    connection.close()

    latency_text = f"{latency} ms" if latency is not None else f"RTO {rto_count}/{RTO_OFFLINE_THRESHOLD}"
    print(f"[MONITOR] {ip_address} | {status} | {latency_text}")


# =========================================================
# MONITORING SEMUA DEVICE
# =========================================================

def monitor_all_devices():
    connection = get_db()
    devices = connection.execute("""
        SELECT id, ip_address, rto_count
        FROM devices
    """).fetchall()
    connection.close()

    for device in devices:
        monitor_device(
            device["id"],
            device["ip_address"],
            device["rto_count"],
        )


# =========================================================
# BACKGROUND MONITORING
# =========================================================

def monitoring_loop():
    print(f"[MONITORING] Interval = {MONITOR_INTERVAL} detik")

    while True:
        try:
            monitor_all_devices()
        except Exception as error:
            print(f"[MONITORING ERROR] {error}")

        time.sleep(MONITOR_INTERVAL)


# =========================================================
# HALAMAN
# =========================================================

@app.route("/")
def index():
    return render_template(
        "index.html",
        interval=MONITOR_INTERVAL,
        history_limit=HISTORY_LIMIT,
        rto_threshold=RTO_OFFLINE_THRESHOLD,
    )


@app.route("/grafik")
def grafik():
    return render_template(
        "grafik.html",
        interval=MONITOR_INTERVAL,
        history_limit=HISTORY_LIMIT,
        rto_threshold=RTO_OFFLINE_THRESHOLD,
        latency_normal=LATENCY_NORMAL,
        latency_high=LATENCY_HIGH,
    )


# =========================================================
# API - DEVICE
# =========================================================

@app.route("/api/devices", methods=["GET"])
def get_devices():
    connection = get_db()
    devices = connection.execute("""
        SELECT *
        FROM devices
        ORDER BY id DESC
    """).fetchall()
    connection.close()

    return jsonify([dict(device) for device in devices])


@app.route("/api/devices", methods=["POST"])
def add_device():
    data = request.get_json(silent=True) or {}
    location = data.get("location", "").strip()
    ip_address = data.get("ip_address", "").strip()
    description = data.get("description", "").strip()

    if not location:
        return jsonify({"error": "Nama/lokasi wajib diisi."}), 400

    if not ip_address:
        return jsonify({"error": "IP Address wajib diisi."}), 400

    connection = get_db()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO devices
                (location, ip_address, description, rto_count)
            VALUES (?, ?, ?, 0)
        """, (location, ip_address, description))
        connection.commit()
        device_id = cursor.lastrowid
        connection.close()

        return jsonify({
            "message": "Lokasi berhasil ditambahkan.",
            "id": device_id,
        }), 201

    except sqlite3.IntegrityError:
        connection.close()
        return jsonify({"error": "IP Address tersebut sudah terdaftar."}), 400


@app.route("/api/devices/<int:device_id>", methods=["PUT"])
def update_device(device_id):
    data = request.get_json(silent=True) or {}
    location = data.get("location", "").strip()
    ip_address = data.get("ip_address", "").strip()
    description = data.get("description", "").strip()

    if not location:
        return jsonify({"error": "Nama/lokasi wajib diisi."}), 400

    if not ip_address:
        return jsonify({"error": "IP Address wajib diisi."}), 400

    connection = get_db()

    try:
        cursor = connection.cursor()
        current = cursor.execute(
            "SELECT ip_address FROM devices WHERE id = ?",
            (device_id,),
        ).fetchone()

        if current is None:
            connection.close()
            return jsonify({"error": "Perangkat tidak ditemukan."}), 404

        if current["ip_address"] != ip_address:
            cursor.execute("""
                UPDATE devices
                SET location = ?,
                    ip_address = ?,
                    description = ?,
                    status = 'UNKNOWN',
                    latency = NULL,
                    checked_at = NULL,
                    rto_count = 0
                WHERE id = ?
            """, (location, ip_address, description, device_id))
        else:
            cursor.execute("""
                UPDATE devices
                SET location = ?,
                    ip_address = ?,
                    description = ?
                WHERE id = ?
            """, (location, ip_address, description, device_id))

        connection.commit()
        connection.close()
        return jsonify({"message": "Lokasi berhasil diperbarui."})

    except sqlite3.IntegrityError:
        connection.close()
        return jsonify({"error": "IP Address tersebut sudah digunakan."}), 400


@app.route("/api/devices/<int:device_id>", methods=["DELETE"])
def delete_device(device_id):
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM monitoring_logs WHERE device_id = ?",
        (device_id,),
    )
    cursor.execute(
        "DELETE FROM devices WHERE id = ?",
        (device_id,),
    )

    if cursor.rowcount == 0:
        connection.close()
        return jsonify({"error": "Perangkat tidak ditemukan."}), 404

    connection.commit()
    connection.close()
    return jsonify({"message": "Lokasi berhasil dihapus."})


# =========================================================
# API - SUMMARY
# =========================================================

@app.route("/api/summary", methods=["GET"])
def get_summary():
    connection = get_db()
    cursor = connection.cursor()

    total = cursor.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    online = cursor.execute(
        "SELECT COUNT(*) FROM devices WHERE status = 'ONLINE'"
    ).fetchone()[0]
    slow = cursor.execute(
        "SELECT COUNT(*) FROM devices WHERE status = 'SLOW'"
    ).fetchone()[0]
    offline = cursor.execute(
        "SELECT COUNT(*) FROM devices WHERE status = 'OFFLINE'"
    ).fetchone()[0]

    connection.close()

    return jsonify({
        "total": total,
        "online": online,
        "slow": slow,
        "offline": offline,
    })


# =========================================================
# API - LOG DEVICE
# =========================================================

@app.route("/api/devices/<int:device_id>/logs", methods=["GET"])
def get_device_logs(device_id):
    limit = request.args.get("limit", default=HISTORY_LIMIT, type=int)
    limit = max(1, min(limit, 500))

    connection = get_db()
    logs = connection.execute("""
        SELECT
            id,
            device_id,
            status,
            latency,
            checked_at,
            rto_count
        FROM monitoring_logs
        WHERE device_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (device_id, limit)).fetchall()
    connection.close()

    return jsonify([dict(log) for log in logs])


# =========================================================
# API - SEMUA LOG
# =========================================================

@app.route("/api/logs", methods=["GET"])
def get_all_logs():
    limit = request.args.get("limit", default=100, type=int)
    limit = max(1, min(limit, 2000))

    connection = get_db()
    logs = connection.execute("""
        SELECT
            monitoring_logs.id,
            monitoring_logs.device_id,
            devices.location,
            devices.ip_address,
            monitoring_logs.status,
            monitoring_logs.latency,
            monitoring_logs.checked_at,
            monitoring_logs.rto_count
        FROM monitoring_logs
        JOIN devices
            ON monitoring_logs.device_id = devices.id
        ORDER BY monitoring_logs.id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    connection.close()

    return jsonify([dict(log) for log in logs])


# =========================================================
# API - HISTORY UNTUK GRAFIK KESELURUHAN
# =========================================================

@app.route("/api/history", methods=["GET"])
def get_history():
    """Mengembalikan N log terakhir untuk setiap perangkat."""
    limit = request.args.get("limit", default=HISTORY_LIMIT, type=int)
    limit = max(1, min(limit, 500))

    connection = get_db()
    devices = connection.execute("""
        SELECT
            id,
            location,
            ip_address,
            status,
            latency,
            checked_at,
            rto_count
        FROM devices
        ORDER BY id ASC
    """).fetchall()

    result = []

    for device in devices:
        logs = connection.execute("""
            SELECT
                id,
                status,
                latency,
                checked_at,
                rto_count
            FROM monitoring_logs
            WHERE device_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (device["id"], limit)).fetchall()

        item = dict(device)
        item["logs"] = [dict(log) for log in logs]
        result.append(item)

    connection.close()

    return jsonify({
        "devices": result,
        "limit": limit,
        "monitor_interval": MONITOR_INTERVAL,
        "rto_threshold": RTO_OFFLINE_THRESHOLD,
        "latency_normal": LATENCY_NORMAL,
        "latency_high": LATENCY_HIGH,
    })


# =========================================================
# MENJALANKAN PROGRAM
# =========================================================

if __name__ == "__main__":
    print("")
    print("=" * 55)
    print("       NETWORK MONITORING DISKOMINFO")
    print("=" * 55)
    print("")

    init_database()

    monitoring_thread = threading.Thread(
        target=monitoring_loop,
        daemon=True,
    )
    monitoring_thread.start()

    print(f"Dashboard: http://{HOST}:{PORT}")
    print(f"Monitoring interval: {MONITOR_INTERVAL} detik")
    print(f"Offline setelah: {RTO_OFFLINE_THRESHOLD} RTO berturut-turut")
    print("")
    print("Tekan CTRL+C untuk menghentikan server.")
    print("")

    app.run(
        host=HOST,
        port=PORT,
        debug=False,
        threaded=True,
    )
