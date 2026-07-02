# ============================================================
#  heartbeat.py — Reporte de eventos al servidor Late Corazón
#  Envía estado del dispositivo via HTTP POST a latecorazon.com
# ============================================================

from config import HEARTBEAT_URL


def send_heartbeat(sim, event: str, message: str = "",
                   lat: float = 0.0, lon: float = 0.0,
                   extra: str = ""):
    """
    Envía un evento de estado al servidor de monitoreo.

    Args:
        sim     : instancia SIMModule
        event   : tipo — BOOT, HEARTBEAT, EMERGENCY, GPS_TIMEOUT, etc.
        message : descripción opcional en español
        lat/lon : coordenadas si están disponibles
        extra   : dato adicional (número marcado, duración, etc.)
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
            ',"uptime_s":0' +
            ',"extra":"'   + extra.replace('"', "'") + '"' +
            '}'
        )

        sim.http_post(payload, url=HEARTBEAT_URL)

    except Exception as e:
        print("heartbeat error:", e)
