import os
import sqlite3
import subprocess
import platform
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, request, render_template


# =========================================================
# KONFIGURASI
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(
    BASE_DIR,
    "monitoring.db"
)

HOST = "127.0.0.1"

PORT = 5000

MONITOR_INTERVAL = 5

# Parameter status latency
LATENCY_NORMAL = 30
LATENCY_SLOW = 100


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)


# =========================================================
# DATABASE
# =========================================================

def get_db():

    connection = sqlite3.connect(
        DATABASE,
        timeout=10
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_database():

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

            checked_at TEXT

        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monitoring_logs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            device_id INTEGER NOT NULL,

            status TEXT NOT NULL,

            latency REAL,

            checked_at TEXT NOT NULL,

            FOREIGN KEY(device_id)
            REFERENCES devices(id)
            ON DELETE CASCADE

        )
    """)

    connection.commit()

    connection.close()


# =========================================================
# WAKTU
# =========================================================

def current_time():

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# =========================================================
# PING
# =========================================================

def ping_device(ip_address):

    system = platform.system().lower()

    try:

        if system == "windows":

            command = [
                "ping",
                "-n",
                "1",
                "-w",
                "1000",
                ip_address
            ]

        else:

            command = [
                "ping",
                "-c",
                "1",
                "-W",
                "1",
                ip_address
            ]

        start_time = time.perf_counter()

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3
        )

        end_time = time.perf_counter()

        if result.returncode != 0:

            return None

        latency = (
            end_time - start_time
        ) * 1000

        return round(
            latency,
            2
        )

    except Exception as error:

        print(
            f"[PING ERROR] {ip_address}: {error}"
        )

        return None


# =========================================================
# MENENTUKAN STATUS
# =========================================================

def determine_status(latency):

    if latency is None:

        return "OFFLINE"

    if latency <= LATENCY_NORMAL:

        return "ONLINE"

    if latency <= LATENCY_SLOW:

        return "SLOW"

    return "OFFLINE"


# =========================================================
# MONITORING SATU DEVICE
# =========================================================

def monitor_device(device_id, ip_address):

    latency = ping_device(
        ip_address
    )

    status = determine_status(
        latency
    )

    checked_at = current_time()

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute("""
        UPDATE devices

        SET
            status = ?,
            latency = ?,
            checked_at = ?

        WHERE id = ?
    """, (
        status,
        latency,
        checked_at,
        device_id
    ))

    cursor.execute("""
        INSERT INTO monitoring_logs
        (
            device_id,
            status,
            latency,
            checked_at
        )

        VALUES (?, ?, ?, ?)
    """, (
        device_id,
        status,
        latency,
        checked_at
    ))

    connection.commit()

    connection.close()

    print(
        f"[MONITOR] "
        f"{ip_address} | "
        f"{status} | "
        f"{latency if latency is not None else '-'} ms"
    )


# =========================================================
# MONITORING SEMUA DEVICE
# =========================================================

def monitor_all_devices():

    connection = get_db()

    devices = connection.execute("""
        SELECT id, ip_address
        FROM devices
    """).fetchall()

    connection.close()

    for device in devices:

        monitor_device(
            device["id"],
            device["ip_address"]
        )


# =========================================================
# BACKGROUND MONITORING
# =========================================================

def monitoring_loop():

    print(
        f"[MONITORING] "
        f"Interval = {MONITOR_INTERVAL} detik"
    )

    while True:

        try:

            monitor_all_devices()

        except Exception as error:

            print(
                f"[MONITORING ERROR] {error}"
            )

        time.sleep(
            MONITOR_INTERVAL
        )


# =========================================================
# HALAMAN UTAMA
# =========================================================

@app.route("/")
def index():

    return render_template(
        "index.html",
        interval=MONITOR_INTERVAL
    )


# =========================================================
# API - GET SEMUA DEVICE
# =========================================================

@app.route(
    "/api/devices",
    methods=["GET"]
)
def get_devices():

    connection = get_db()

    devices = connection.execute("""
        SELECT *
        FROM devices
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    result = [
        dict(device)
        for device in devices
    ]

    return jsonify(result)


# =========================================================
# API - TAMBAH DEVICE
# =========================================================

@app.route(
    "/api/devices",
    methods=["POST"]
)
def add_device():

    data = request.get_json()

    location = (
        data.get("location", "")
        .strip()
    )

    ip_address = (
        data.get("ip_address", "")
        .strip()
    )

    description = (
        data.get("description", "")
        .strip()
    )


    if not location:

        return jsonify({
            "error":
                "Nama/lokasi wajib diisi."
        }), 400


    if not ip_address:

        return jsonify({
            "error":
                "IP Address wajib diisi."
        }), 400


    connection = get_db()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO devices
            (
                location,
                ip_address,
                description
            )

            VALUES (?, ?, ?)
        """, (
            location,
            ip_address,
            description
        ))

        connection.commit()

        device_id = cursor.lastrowid

        connection.close()

        return jsonify({
            "message":
                "Lokasi berhasil ditambahkan.",
            "id":
                device_id
        }), 201

    except sqlite3.IntegrityError:

        connection.close()

        return jsonify({
            "error":
                "IP Address tersebut sudah terdaftar."
        }), 400


# =========================================================
# API - EDIT DEVICE
# =========================================================

@app.route(
    "/api/devices/<int:device_id>",
    methods=["PUT"]
)
def update_device(device_id):

    data = request.get_json()

    location = (
        data.get("location", "")
        .strip()
    )

    ip_address = (
        data.get("ip_address", "")
        .strip()
    )

    description = (
        data.get("description", "")
        .strip()
    )


    if not location:

        return jsonify({
            "error":
                "Nama/lokasi wajib diisi."
        }), 400


    if not ip_address:

        return jsonify({
            "error":
                "IP Address wajib diisi."
        }), 400


    connection = get_db()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            UPDATE devices

            SET
                location = ?,
                ip_address = ?,
                description = ?

            WHERE id = ?
        """, (
            location,
            ip_address,
            description,
            device_id
        ))

        if cursor.rowcount == 0:

            connection.close()

            return jsonify({
                "error":
                    "Perangkat tidak ditemukan."
            }), 404


        connection.commit()

        connection.close()

        return jsonify({
            "message":
                "Lokasi berhasil diperbarui."
        })


    except sqlite3.IntegrityError:

        connection.close()

        return jsonify({
            "error":
                "IP Address tersebut sudah digunakan."
        }), 400


# =========================================================
# API - HAPUS DEVICE
# =========================================================

@app.route(
    "/api/devices/<int:device_id>",
    methods=["DELETE"]
)
def delete_device(device_id):

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM monitoring_logs

        WHERE device_id = ?
    """, (
        device_id,
    ))

    cursor.execute("""
        DELETE FROM devices

        WHERE id = ?
    """, (
        device_id,
    ))

    if cursor.rowcount == 0:

        connection.close()

        return jsonify({
            "error":
                "Perangkat tidak ditemukan."
        }), 404


    connection.commit()

    connection.close()

    return jsonify({
        "message":
            "Lokasi berhasil dihapus."
    })


# =========================================================
# API - SUMMARY
# =========================================================

@app.route(
    "/api/summary",
    methods=["GET"]
)
def get_summary():

    connection = get_db()

    cursor = connection.cursor()

    total = cursor.execute("""
        SELECT COUNT(*)
        FROM devices
    """).fetchone()[0]

    online = cursor.execute("""
        SELECT COUNT(*)
        FROM devices
        WHERE status = 'ONLINE'
    """).fetchone()[0]

    slow = cursor.execute("""
        SELECT COUNT(*)
        FROM devices
        WHERE status = 'SLOW'
    """).fetchone()[0]

    offline = cursor.execute("""
        SELECT COUNT(*)
        FROM devices
        WHERE status = 'OFFLINE'
    """).fetchone()[0]

    connection.close()

    return jsonify({

        "total":
            total,

        "online":
            online,

        "slow":
            slow,

        "offline":
            offline

    })


# =========================================================
# API - LOG DEVICE
# =========================================================

@app.route(
    "/api/devices/<int:device_id>/logs",
    methods=["GET"]
)
def get_device_logs(device_id):

    limit = request.args.get(
        "limit",
        default=50,
        type=int
    )

    if limit > 100:

        limit = 100


    connection = get_db()

    logs = connection.execute("""
        SELECT
            id,
            device_id,
            status,
            latency,
            checked_at

        FROM monitoring_logs

        WHERE device_id = ?

        ORDER BY id DESC

        LIMIT ?
    """, (
        device_id,
        limit
    )).fetchall()

    connection.close()

    return jsonify([
        dict(log)
        for log in logs
    ])


# =========================================================
# API - SEMUA LOG
# =========================================================

@app.route(
    "/api/logs",
    methods=["GET"]
)
def get_all_logs():

    limit = request.args.get(
        "limit",
        default=100,
        type=int
    )

    connection = get_db()

    logs = connection.execute("""
        SELECT
            monitoring_logs.id,
            monitoring_logs.device_id,
            devices.location,
            devices.ip_address,
            monitoring_logs.status,
            monitoring_logs.latency,
            monitoring_logs.checked_at

        FROM monitoring_logs

        JOIN devices
        ON monitoring_logs.device_id = devices.id

        ORDER BY monitoring_logs.id DESC

        LIMIT ?
    """, (
        limit,
    )).fetchall()

    connection.close()

    return jsonify([
        dict(log)
        for log in logs
    ])


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
        daemon=True
    )

    monitoring_thread.start()

    print(
        f"Dashboard:"
        f" http://{HOST}:{PORT}"
    )

    print(
        f"Monitoring interval:"
        f" {MONITOR_INTERVAL} detik"
    )

    print("")
    print(
        "Tekan CTRL+C untuk menghentikan server."
    )
    print("")

    app.run(
        host=HOST,
        port=PORT,
        debug=False,
        threaded=True
    )