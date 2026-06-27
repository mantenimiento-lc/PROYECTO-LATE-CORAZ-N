# ============================================================
#  heartbeat.py — Reporte de eventos al servidor de monitoreo
#  Envía estado del dispositivo via HTTP POST a Railway
# ============================================================

from config import MONITOR_URL


def send_heartbeat(sim, event: str, message: str = "",
                   lat: float = 0.0, lon: float = 0.0,
                   extra: str = ""):
    """
    Envía un evento de estado al servidor de monitoreo.

    Args:
        sim     : instancia SIMModule
        event   : tipo — BOOT, HEARTBEAT, EMERGENCY, GPS_TIMEOUT, etc.
        message : descripción opcional
        lat/lon : coordenadas si están disponibles
        extra   : dato adicional (número marcado, código de error, etc.)
    """
    try:
        sig    = sim.check_signal()
        rssi   = sig.get("rssi", 0)
        signal = sig.get("label", "")
        temp   = sim.get_temperature()
        imei   = sim.get_imei()

        payload = (
            '{"imei":"'    + imei + '"' +
            ',"event":"'   + event + '"' +
            ',"message":"' + message.replace('"', "'") + '"' +
            ',"lat":'      + "{:.6f}".format(lat) +
            ',"lon":'      + "{:.6f}".format(lon) +
            ',"rssi":'     + str(rssi) +
            ',"temp":'     + str(temp) +
            ',"signal":"'  + signal + '"' +
            ',"extra":"'   + extra.replace('"', "'") + '"' +
            '}'
        )

        sim.http_post(payload, url=MONITOR_URL)

    except Exception as e:
        print("heartbeat error:", e)
