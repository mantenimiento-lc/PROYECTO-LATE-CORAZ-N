# ============================================================
#  main.py — DEA Monitor API + Dashboard
#  FastAPI — recibe heartbeats del dispositivo y sirve el web
# ============================================================

import os
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import database as db

app = FastAPI(title="DEA Monitor", version="1.0.0")

# Inicializar base de datos al arrancar
db.init_db()

# Servir archivos estáticos (dashboard HTML)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Modelos de entrada ────────────────────────────────────────

class HeartbeatPayload(BaseModel):
    imei: str
    event: str                    # HEARTBEAT, BOOT, GPS_TIMEOUT, ERROR, etc.
    message: Optional[str] = ""
    lat: Optional[float] = 0.0
    lon: Optional[float] = 0.0
    rssi: Optional[int] = 0
    temp: Optional[float] = 0.0
    signal: Optional[str] = ""
    uptime_s: Optional[int] = 0
    extra: Optional[str] = ""


class TrackingPayload(BaseModel):
    imei: str
    latitude: float
    longitude: float
    date: Optional[str] = ""
    accuracy_m: Optional[int] = 999
    speed: Optional[float] = 0.0


class DeviceInfoPayload(BaseModel):
    name: str
    location: str


# ── Endpoints del dispositivo ─────────────────────────────────

@app.post("/api/heartbeat")
async def heartbeat(payload: HeartbeatPayload):
    """
    Recibe eventos del dispositivo: arranques, errores, GPS timeout, etc.
    El dispositivo llama esto periódicamente para reportar su estado.
    """
    data = {
        "lat":      payload.lat,
        "lon":      payload.lon,
        "rssi":     payload.rssi,
        "temp":     payload.temp,
        "signal":   payload.signal,
        "uptime_s": payload.uptime_s,
        "is_boot":  1 if payload.event == "BOOT" else 0,
    }

    db.upsert_device(payload.imei, data)

    # HEARTBEAT: un solo registro que se actualiza
    if payload.event == "HEARTBEAT":
        db.upsert_heartbeat(payload.imei, {
            "message": payload.message or "",
            "lat": payload.lat, "lon": payload.lon,
            "rssi": payload.rssi, "temp": payload.temp,
        })
    elif payload.event == "GPS_TIMEOUT":
        db.upsert_gps_alert(payload.imei)
    else:
        db.log_event(
            imei       = payload.imei,
            event_type = payload.event,
            message    = payload.message or "",
            lat        = payload.lat,
            lon        = payload.lon,
            rssi       = payload.rssi,
            temp       = payload.temp,
            extra      = payload.extra or "",
        )

    return {"status": "ok"}


@app.post("/api/tracking")
async def tracking(payload: TrackingPayload):
    """
    Recibe posición GPS periódica del dispositivo.
    Compatible con el formato actual del dispositivo.
    """
    data = {
        "lat":    payload.latitude,
        "lon":    payload.longitude,
        "rssi":   0,
        "temp":   0.0,
        "signal": "",
        "uptime_s": 0,
        "is_boot": 0,
    }

    db.upsert_device(payload.imei, data)
    db.log_position(
        imei       = payload.imei,
        lat        = payload.latitude,
        lon        = payload.longitude,
        accuracy_m = payload.accuracy_m or 999,
        speed      = payload.speed or 0.0,
    )
    # Registrar evento de tracking (uno solo que se actualiza)
    db.upsert_tracking_event(payload.imei, payload.latitude, payload.longitude,
                             payload.accuracy_m or 999, payload.speed or 0.0)

    return {"status": "ok"}


# ── Endpoints del dashboard ───────────────────────────────────

@app.get("/api/boots")
async def get_boots(imei: Optional[str] = None, limit: int = 100):
    """Retorna historial de reinicios con causa probable."""
    boots = db.get_boots(imei=imei, limit=limit)
    devices = {d["imei"]: d for d in db.get_all_devices()}
    for b in boots:
        dev = devices.get(b["imei"], {})
        b["device_name"]     = dev.get("name", "") or ""
        b["device_location"] = dev.get("location", "") or ""
    return JSONResponse(content=boots)


@app.get("/api/emergencies")
async def get_emergencies(imei: Optional[str] = None, limit: int = 200):
    """Retorna todas las emergencias registradas, opcionalmente por dispositivo."""
    events = db.get_emergencies(imei=imei, limit=limit)
    # Enriquecer con nombre del dispositivo
    devices = {d["imei"]: d for d in db.get_all_devices()}
    for e in events:
        dev = devices.get(e["imei"], {})
        e["device_name"]     = dev.get("name", "") or ""
        e["device_location"] = dev.get("location", "") or ""
    return JSONResponse(content=events)


@app.get("/api/devices")
async def get_devices():
    """Lista todos los dispositivos con su estado actual."""
    devices = db.get_all_devices()
    now = datetime.now(timezone.utc)

    for d in devices:
        # En línea = último reporte < 5 minutos Y tiene GPS válido
        if d.get("last_seen"):
            try:
                last = datetime.strptime(d["last_seen"], "%Y-%m-%d %H:%M:%S")
                last = last.replace(tzinfo=timezone.utc)
                diff = (now - last).total_seconds()
                has_gps = not (d.get("last_lat", 0.0) == 0.0 and d.get("last_lon", 0.0) == 0.0)
                d["online"] = diff < 600 and has_gps  # 10 minutos
                d["minutes_ago"] = int(diff / 60)
            except Exception:
                d["online"] = False
                d["minutes_ago"] = 999
        else:
            d["online"] = False
            d["minutes_ago"] = 999

    return JSONResponse(content=devices)


@app.get("/api/events")
async def get_events(imei: Optional[str] = None, limit: int = 200):
    """Retorna los últimos eventos, opcionalmente filtrados por IMEI."""
    events = db.get_events(imei=imei, limit=limit)
    return JSONResponse(content=events)


@app.get("/api/positions/{imei}")
async def get_positions(imei: str, limit: int = 50):
    """Retorna las últimas posiciones GPS de un dispositivo."""
    positions = db.get_positions(imei=imei, limit=limit)
    return JSONResponse(content=positions)


@app.put("/api/devices/{imei}")
async def update_device(imei: str, payload: DeviceInfoPayload):
    """Actualiza nombre y ubicación de un dispositivo."""
    db.update_device_info(imei, payload.name, payload.location)
    return {"status": "ok"}


# ── Dashboard HTML ────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Sirve el dashboard principal."""
    html_path = os.path.join("static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard no encontrado</h1>", status_code=404)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
