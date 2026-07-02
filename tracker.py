# ============================================================
#  tracker.py — Envío periódico de posición GPS
#  POST a latecorazon.com/api/tracking
# ============================================================

from config import TRACKING_URL


def build_json(gps: dict, imei: str) -> str:
    """Construye el payload JSON para el endpoint de tracking."""
    lat  = gps.get("latitude",   0.0)
    lon  = gps.get("longitude",  0.0)
    date = gps.get("timedate",   "")
    acc  = gps.get("accuracy_m", 999)
    spd  = gps.get("speed",      0.0)

    return (
        '{"imei":"'      + imei + '"' +
        ',"latitude":'   + "{:.7f}".format(lat) +
        ',"longitude":'  + "{:.7f}".format(lon) +
        ',"date":"'      + date + '"' +
        ',"accuracy_m":' + str(acc) +
        ',"speed":'      + "{:.2f}".format(spd) +
        '}'
    )


def send_position(sim, gps: dict):
    """
    Envía posición GPS periódica a latecorazon.com/api/tracking.
    Solo envía si las coordenadas son válidas.
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

    sim.http_post(payload, url=TRACKING_URL)
