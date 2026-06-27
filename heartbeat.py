# ============================================================
#  heartbeat.py — Reporte de estado remoto DEA-001
#  Envía eventos al servidor de monitoreo via HTTP POST
# ============================================================

# URL del servidor de monitoreo
# Reemplaza con la URL de tu app en Railway una vez deployada
MONITOR_URL = "https://TU-APP.railway.app/api/heartbeat"


def send_heartbeat(sim, event: str, message: str = "",
                   lat: float = 0.0, lon: float = 0.0,
                   extra: str = ""):
    """
    Envía un evento de estado al servidor de monitoreo.

    Parámetros:
        sim     : instancia SIMModule
        event   : BOOT, GPS_TIMEOUT, ERROR, HEARTBEAT, EMERGENCY, etc.
        message : descripción opcional del evento
        lat/lon : coordenadas si están disponibles
        extra   : información adicional (número marcado, código de error, etc.)
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
