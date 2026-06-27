# ============================================================
#  tracker.py — Envío periódico de posición al servidor
#  Construye el JSON y ejecuta el HTTP POST via sim_module
# ============================================================


def build_json(gps: dict, imei: str) -> str:
    """
    Construye el payload JSON para el endpoint de tracking.

    Campos enviados:
        latitude    float  7 decimales
        longitude   float  7 decimales
        date        str    YYYY-MM-DD HH:MM:SS
        imei        str    15 dígitos
        accuracy_m  int    precisión estimada en metros
        speed       float  km/h
    """
    lat  = gps.get("latitude",   0.0)
    lon  = gps.get("longitude",  0.0)
    date = gps.get("timedate",   "")
    acc  = gps.get("accuracy_m", 999)
    spd  = gps.get("speed",      0.0)

    return (
        '{"latitude":' + "{:.7f}".format(lat) +
        ',"longitude":' + "{:.7f}".format(lon) +
        ',"date":"' + date + '"' +
        ',"imei":"' + imei + '"' +
        ',"accuracy_m":' + str(acc) +
        ',"speed":' + "{:.2f}".format(spd) +
        '}'
    )


def send_position(sim, gps: dict):
    """
    Valida el fix GPS y envía la posición al servidor.
    No hace nada si las coordenadas son 0,0.
    """
    lat = gps.get("latitude",  0.0)
    lon = gps.get("longitude", 0.0)

    if lat == 0.0 and lon == 0.0:
        print("GPS invalido, no se envia HTTP")
        return

    imei     = sim.get_imei()
    payload  = build_json(gps, imei)

    print("--- JSON enviado ---")
    print(payload)
    print("-------------------")

    sim.http_post(payload)
