# ============================================================
#  database.py — SQLite setup y queries para DEA Monitor
# ============================================================

import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "dea_monitor.db")


def get_conn():
    """Retorna una conexión SQLite con row_factory para dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crea las tablas si no existen."""
    conn = get_conn()
    c = conn.cursor()

    # Tabla de dispositivos — un registro por IMEI
    c.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            imei        TEXT PRIMARY KEY,
            name        TEXT DEFAULT '',
            location    TEXT DEFAULT '',
            last_seen   TEXT,
            last_lat    REAL DEFAULT 0.0,
            last_lon    REAL DEFAULT 0.0,
            last_rssi   INTEGER DEFAULT 0,
            last_temp   REAL DEFAULT 0.0,
            last_signal TEXT DEFAULT '',
            uptime_s    INTEGER DEFAULT 0,
            boot_count  INTEGER DEFAULT 0,
            created_at  TEXT
        )
    """)

    # Tabla de eventos — heartbeats, errores, emergencias
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            imei        TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            message     TEXT DEFAULT '',
            lat         REAL DEFAULT 0.0,
            lon         REAL DEFAULT 0.0,
            rssi        INTEGER DEFAULT 0,
            temp        REAL DEFAULT 0.0,
            extra       TEXT DEFAULT '',
            created_at  TEXT NOT NULL
        )
    """)

    # Tabla de posiciones GPS — para historial de tracking
    c.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            imei        TEXT NOT NULL,
            lat         REAL NOT NULL,
            lon         REAL NOT NULL,
            accuracy_m  INTEGER DEFAULT 999,
            speed       REAL DEFAULT 0.0,
            created_at  TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def upsert_device(imei: str, data: dict):
    """Crea o actualiza el registro del dispositivo."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT imei FROM devices WHERE imei = ?", (imei,))
    exists = c.fetchone()

    if exists:
        c.execute("""
            UPDATE devices SET
                last_seen   = ?,
                last_lat    = ?,
                last_lon    = ?,
                last_rssi   = ?,
                last_temp   = ?,
                last_signal = ?,
                uptime_s    = ?,
                boot_count  = boot_count + ?
            WHERE imei = ?
        """, (
            now_utc(),
            data.get("lat", 0.0),
            data.get("lon", 0.0),
            data.get("rssi", 0),
            data.get("temp", 0.0),
            data.get("signal", ""),
            data.get("uptime_s", 0),
            data.get("is_boot", 0),
            imei,
        ))
    else:
        c.execute("""
            INSERT INTO devices
                (imei, last_seen, last_lat, last_lon, last_rssi, last_temp,
                 last_signal, uptime_s, boot_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            imei,
            now_utc(),
            data.get("lat", 0.0),
            data.get("lon", 0.0),
            data.get("rssi", 0),
            data.get("temp", 0.0),
            data.get("signal", ""),
            data.get("uptime_s", 0),
            data.get("is_boot", 0),
            now_utc(),
        ))

    conn.commit()
    conn.close()


def log_event(imei: str, event_type: str, message: str = "",
              lat: float = 0.0, lon: float = 0.0,
              rssi: int = 0, temp: float = 0.0, extra: str = ""):
    """Inserta un evento en la tabla events."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO events (imei, event_type, message, lat, lon, rssi, temp, extra, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (imei, event_type, message, lat, lon, rssi, temp, extra, now_utc()))
    conn.commit()
    conn.close()


def log_position(imei: str, lat: float, lon: float,
                 accuracy_m: int = 999, speed: float = 0.0):
    """Inserta una posición GPS en la tabla positions."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO positions (imei, lat, lon, accuracy_m, speed, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (imei, lat, lon, accuracy_m, speed, now_utc()))
    conn.commit()
    conn.close()


def get_all_devices() -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM devices ORDER BY last_seen DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_events(imei: str = None, limit: int = 100) -> list:
    conn = get_conn()
    c = conn.cursor()
    if imei:
        c.execute("""
            SELECT * FROM events WHERE imei = ?
            ORDER BY created_at DESC LIMIT ?
        """, (imei, limit))
    else:
        c.execute("""
            SELECT * FROM events
            ORDER BY created_at DESC LIMIT ?
        """, (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_positions(imei: str, limit: int = 100) -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM positions WHERE imei = ?
        ORDER BY created_at DESC LIMIT ?
    """, (imei, limit))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def update_device_info(imei: str, name: str, location: str):
    """Actualiza nombre y ubicación de un dispositivo."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE devices SET name = ?, location = ? WHERE imei = ?
    """, (name, location, imei))
    conn.commit()
    conn.close()
