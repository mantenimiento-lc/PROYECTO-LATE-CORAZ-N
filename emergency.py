# ============================================================
#  emergency.py — Lógica de emergencia DEA
#  Construye los SMS de alerta con GPS y fecha
# ============================================================

from gps_utils import is_valid_fix


def build_sms(rtcs: str, gps: dict) -> list:
    """
    Construye los mensajes de emergencia.
    Retorna lista de 2 strings, cada uno <= 160 chars.

    SMS 1 — identificación y fecha
    SMS 2 — ubicación GPS con link y precisión
    """
    lat = gps.get("latitude",   0.0)
    lon = gps.get("longitude",  0.0)
    acc = gps.get("accuracy_m", 999)

    lat_str = "{:.6f}".format(lat)
    lon_str = "{:.6f}".format(lon)

    sms1 = (
        "EMERGENCIA DEA\r\n"
        "El DEA fue retirado del gabinete.\r\n"
        "Fecha: {}"
    ).format(rtcs)

    if is_valid_fix(lat, lon):
        sms2 = (
            "Ubicacion DEA:\r\n"
            "Lat: {lat}\r\n"
            "Lon: {lon}\r\n"
            "Precision: ~{acc} metros\r\n"
            "maps.google.com/?q={lat},{lon}\r\n"
            "Se presume emergencia medica."
        ).format(lat=lat_str, lon=lon_str, acc=acc)
    else:
        sms2 = (
            "Ubicacion DEA:\r\n"
            "GPS sin fix disponible.\r\n"
            "Se presume emergencia medica."
        )

    return [sms1, sms2]
l