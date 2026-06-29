# ============================================================
#  database.py — PostgreSQL queries para DEA Monitor
#  Usa DATABASE_URL de Railway (variable de entorno)
# ============================================================

import os
from datetime import datetime, timezone
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_conn():
    """Retorna una conexión PostgreSQL con cursor de diccionarios."""
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db():
    """Crea las tablas si no existen."""
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            imei        TEXT PRIMARY KEY,
            name        TEXT DEFAULT '',
            location    TEXT DEFAULT '',
            last_seen   TIMESTAMP,
            last_lat    DOUBLE PRECISION DEFAULT 0.0,
            last_lon    DOUBLE PRECISION DEFAULT 0.0,
            last_rssi   INTEGER DEFAULT 0,
            last_temp   DOUBLE PRECISION DEFAULT 0.0,
            last_signal TEXT DEFAULT '',
            uptime_s    INTEGER DEFAULT 0,
            boot_count  INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT NOW()
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id          SERIAL PRIMARY KEY,
            imei        TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            message     TEXT DEFAULT '',
            lat         DOUBLE PRECISION DEFAULT 0.0,
            lon         DOUBLE PRECISION DEFAULT 0.0,
            rssi        INTEGER DEFAULT 0,
            temp        DOUBLE PRECISION DEFAULT 0.0,
            extra       TEXT DEFAULT '',
            created_at  TIMESTAMP DEFAULT NOW()
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id          SERIAL PRIMARY KEY,
            imei        TEXT NOT NULL,
            lat         DOUBLE PRECISION NOT NULL,
            lon         DOUBLE PRECISION NOT NULL,
            accuracy_m  INTEGER DEFAULT 999,
            speed       DOUBLE PRECISION DEFAULT 0.0,
            created_at  TIMESTAMP DEFAULT NOW()
        )
    """)

    conn.commit()
    c.close()
    conn.close()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _row_to_dict(row, cursor) -> dict:
    """Convierte una fila de psycopg2 a diccionario."""
    cols = [desc[0] for desc in cursor.description]
    d = dict(zip(cols, row))
    # Convertir timestamps a string
    for k, v in d.items():
        if hasattr(v, 'strftime'):
            d[k] = v.strftime("%Y-%m-%d %H:%M:%S")
    return d


def upsert_device(imei: str, data: dict):
    """Crea o actualiza el registro del dispositivo. Nunca borra datos."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT imei FROM devices WHERE imei = %s", (imei,))
    exists = c.fetchone()

    if exists:
        c.execute("""
            UPDATE devices SET
                last_seen   = NOW(),
                last_lat    = %s,
                last_lon    = %s,
                last_rssi   = %s,
                last_temp   = %s,
                last_signal = %s,
                uptime_s    = %s,
                boot_count  = boot_count + %s
            WHERE imei = %s
        """, (
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
                 last_signal, uptime_s, boot_count)
            VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s, %s)
        """, (
            imei,
            data.get("lat", 0.0), data.get("lon", 0.0),
            data.get("rssi", 0), data.get("temp", 0.0),
            data.get("signal", ""),
            data.get("uptime_s", 0),
            data.get("is_boot", 0),
        ))

    conn.commit()
    c.close()
    conn.close()


def log_event(imei: str, event_type: str, message: str = "",
              lat: float = 0.0, lon: float = 0.0,
              rssi: int = 0, temp: float = 0.0, extra: str = ""):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO events (imei, event_type, message, lat, lon, rssi, temp, extra)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (imei, event_type, message, lat, lon, rssi, temp, extra))
    conn.commit()
    c.close()
    conn.close()


def log_position(imei: str, lat: float, lon: float,
                 accuracy_m: int = 999, speed: float = 0.0):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO positions (imei, lat, lon, accuracy_m, speed)
        VALUES (%s, %s, %s, %s, %s)
    """, (imei, lat, lon, accuracy_m, speed))
    conn.commit()
    c.close()
    conn.close()


def upsert_heartbeat(imei: str, data: dict):
    """Actualiza el ÚNICO registro de heartbeat por dispositivo."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM events WHERE imei=%s AND event_type='HEARTBEAT'", (imei,))
    row = c.fetchone()
    msg  = data.get("message", "")
    lat  = data.get("lat", 0.0)
    lon  = data.get("lon", 0.0)
    rssi = data.get("rssi", 0)
    temp = data.get("temp", 0.0)

    if row:
        c.execute("""
            UPDATE events SET message=%s, lat=%s, lon=%s, rssi=%s, temp=%s, created_at=NOW()
            WHERE id=%s
        """, (msg, lat, lon, rssi, temp, row[0]))
    else:
        c.execute("""
            INSERT INTO events (imei, event_type, message, lat, lon, rssi, temp, extra)
            VALUES (%s, 'HEARTBEAT', %s, %s, %s, %s, %s, '')
        """, (imei, msg, lat, lon, rssi, temp))

    conn.commit()
    c.close()
    conn.close()


def upsert_gps_alert(imei: str):
    """Actualiza el ÚNICO registro de GPS_TIMEOUT por dispositivo."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM events WHERE imei=%s AND event_type='GPS_TIMEOUT'", (imei,))
    row = c.fetchone()

    if row:
        c.execute("UPDATE events SET created_at=NOW() WHERE id=%s", (row[0],))
    else:
        c.execute("""
            INSERT INTO events (imei, event_type, message, lat, lon, rssi, temp, extra)
            VALUES (%s, 'GPS_TIMEOUT', 'Sin fix GPS', 0.0, 0.0, 0, 0.0, '')
        """, (imei,))

    conn.commit()
    c.close()
    conn.close()


def upsert_tracking_event(imei: str, lat: float, lon: float,
                          accuracy_m: int = 999, speed: float = 0.0):
    """Actualiza el ÚNICO evento de tracking por dispositivo."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM events WHERE imei=%s AND event_type='TRACKING'", (imei,))
    row = c.fetchone()
    msg = "Lat:{:.6f} Lon:{:.6f} | Precision:{}m | Vel:{:.1f}km/h".format(
          lat, lon, accuracy_m, speed)

    if row:
        c.execute("""
            UPDATE events SET message=%s, lat=%s, lon=%s, created_at=NOW()
            WHERE id=%s
        """, (msg, lat, lon, row[0]))
    else:
        c.execute("""
            INSERT INTO events (imei, event_type, message, lat, lon, rssi, temp, extra)
            VALUES (%s, 'TRACKING', %s, %s, %s, 0, 0.0, '')
        """, (imei, msg, lat, lon))

    conn.commit()
    c.close()
    conn.close()


def clear_table(table: str):
    """Elimina todos los registros de una tabla."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM {}".format(table))
    conn.commit()
    c.close()
    conn.close()


def clear_table_type(table: str, event_type: str):
    """Elimina todos los registros de un tipo de evento específico."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM {} WHERE event_type = %s".format(table), (event_type,))
    conn.commit()
    c.close()
    conn.close()


def get_all_devices() -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM devices ORDER BY last_seen DESC NULLS LAST")
    rows = [_row_to_dict(r, c) for r in c.fetchall()]
    c.close()
    conn.close()
    return rows


def get_events(imei: str = None, limit: int = 100) -> list:
    conn = get_conn()
    c = conn.cursor()
    if imei:
        c.execute("""
            SELECT * FROM events WHERE imei = %s
            ORDER BY created_at DESC LIMIT %s
        """, (imei, limit))
    else:
        c.execute("""
            SELECT * FROM events
            ORDER BY created_at DESC LIMIT %s
        """, (limit,))
    rows = [_row_to_dict(r, c) for r in c.fetchall()]
    c.close()
    conn.close()
    return rows


def get_boots(imei: str = None, limit: int = 100) -> list:
    """
    Retorna historial de reinicios (BOOT) con causa probable.
    Busca el evento anterior al BOOT para determinar la causa:
    - GPS_TIMEOUT antes → causa: Sin GPS por 30 min
    - CANCELLED antes  → causa: Emergencia cancelada
    - Ninguno especial → causa: Manual / actualización
    """
    conn = get_conn()
    c = conn.cursor()

    if imei:
        c.execute("""
            SELECT * FROM events
            WHERE imei = %s AND event_type = 'BOOT'
            ORDER BY created_at DESC LIMIT %s
        """, (imei, limit))
    else:
        c.execute("""
            SELECT * FROM events
            WHERE event_type = 'BOOT'
            ORDER BY created_at DESC LIMIT %s
        """, (limit,))

    boots = [_row_to_dict(r, c) for r in c.fetchall()]

    # Para cada BOOT buscar el evento inmediatamente anterior
    for b in boots:
        c.execute("""
            SELECT event_type FROM events
            WHERE imei = %s AND created_at < %s
            ORDER BY created_at DESC LIMIT 1
        """, (b["imei"], b["created_at"]))
        prev = c.fetchone()
        if prev:
            prev_type = prev[0]
            if prev_type == "GPS_TIMEOUT":
                b["cause"] = "Sin GPS por 30 minutos (watchdog)"
            elif prev_type == "BOOT":
                b["cause"] = "Reinicio en cadena"
            elif prev_type == "EMERGENCY":
                b["cause"] = "Post-emergencia"
            else:
                b["cause"] = "Manual / actualización de código"
        else:
            b["cause"] = "Primer arranque"

    c.close()
    conn.close()
    return boots


def get_emergencies(imei: str = None, limit: int = 200) -> list:
    conn = get_conn()
    c = conn.cursor()
    if imei:
        c.execute("""
            SELECT * FROM events
            WHERE imei = %s AND event_type = 'EMERGENCY'
            ORDER BY created_at DESC LIMIT %s
        """, (imei, limit))
    else:
        c.execute("""
            SELECT * FROM events
            WHERE event_type = 'EMERGENCY'
            ORDER BY created_at DESC LIMIT %s
        """, (limit,))
    rows = [_row_to_dict(r, c) for r in c.fetchall()]
    c.close()
    conn.close()
    return rows


def get_positions(imei: str, limit: int = 100) -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM positions WHERE imei = %s
        ORDER BY created_at DESC LIMIT %s
    """, (imei, limit))
    rows = [_row_to_dict(r, c) for r in c.fetchall()]
    c.close()
    conn.close()
    return rows


def update_device_info(imei: str, name: str, location: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE devices SET name = %s, location = %s WHERE imei = %s",
              (name, location, imei))
    conn.commit()
    c.close()
    conn.close()
