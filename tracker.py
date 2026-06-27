# ============================================================
#  tracker.py — Envío periódico de posición GPS
#  POST al servidor principal y al monitor de estado
# ============================================================

from config import MONITOR_URL


def build_json(gps: dict, imei: str) -> str:
    """Construye el payload JSON para el endpoint de tracking principal."""
    lat  = gps.get("latitude",   0.0)
    lon  = gps.get("longitude",  0.0)
    date = gps.get("timedate",   "")
    acc  = gps.get("accuracy_m", 999)
    spd  = gps.get("speed",      0.0)

    return (
        '{"latitude":'  + "{:.7f}".format(lat) +
        ',"longitude":' + "{:.7f}".format(lon) +
        ',"date":"'     + date + '"' +
        ',"imei":"'     + imei + '"' +
        ',"accuracy_m":' + str(acc) +
        ',"speed":'     + "{:.2f}".format(spd) +
        '}'
    )


def _build_monitor_json(gps: dict, sim) -> str:
    """
    Payload para el monitor de Railway.
    Incluye GPS + señal celular + temperatura.
    """
    imei = sim.get_imei()
    lat  = gps.get("latitude",  0.0)
    lon  = gps.get("longitude", 0.0)
    acc  = gps.get("accuracy_m", 999)
    spd  = gps.get("speed", 0.0)

    try:
        sig    = sim.check_signal()
        rssi   = sig.get("rssi", 0)
        signal = sig.get("label", "")
        temp   = sim.get_temperature()
    except Exception:
        rssi, signal, temp = 0, "", "0"

    return (
        '{"imei":"'   + imei + '"' +
        ',"event":"HEARTBEAT"' +
        ',"message":"GPS activo"' +
        ',"lat":'     + "{:.6f}".format(lat) +
        ',"lon":'     + "{:.6f}".format(lon) +
        ',"rssi":'    + str(rssi) +
        ',"temp":'    + str(temp) +
        ',"signal":"' + signal + '"' +
        ',"extra":"acc:{}m spd:{:.1f}km/h"'.format(acc, spd) +
        '}'
    )


def send_position(sim, gps: dict):
    """
    Envía posición al servidor principal (latecorazon.com) y
    al monitor de estado (Railway) en cada ciclo con GPS válido.
    """
    lat = gps.get("latitude",  0.0)
    lon = gps.get("longitude", 0.0)

    if lat == 0.0 and lon == 0.0:
        print("GPS invalido, no se envia HTTP")
        return

    imei    = sim.get_imei()
    payload = build_json(gps, imei)

    print("--- GPS ---")
    print(payload)
    print("----------")

    # 1. Servidor principal
    sim.http_post(payload)

    # 2. Monitor de estado
    try:
        sim.http_post(_build_monitor_json(gps, sim), url=MONITOR_URL)
    except Exception as e:
        print("monitor error:", e)
