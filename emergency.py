# ============================================================
#  emergency.py — Lógica de emergencia DEA-001
#  Construye los SMS de alerta con GPS y fecha
# ============================================================

from gps_utils import is_valid_fix
from config    import DEA_SERIAL


def build_sms(rtcs: str, gps: dict) -> list:
    """
    Construye los mensajes de emergencia.
    Retorna lista de 2 strings, cada uno <= 160 chars.

    SMS 1 — identificación y fecha
    SMS 2 — ubicación GPS o aviso de sin fix
    """
    lat = gps.get("latitude",   0.0)
    lon = gps.get("longitude",  0.0)
    acc = gps.get("accuracy_m", 999)

    lat_str = "{:.6f}".format(lat)
    lon_str = "{:.6f}".format(lon)

    sms1 = (
        "EMERGENCIA DEA\r\n"
        "DEA PRIMEDIC S/N:{serial} RETIRADO DEL GABINETE.\r\n"
        "Fecha: {fecha}"
    ).format(serial=DEA_SERIAL, fecha=rtcs)

    if is_valid_fix(lat, lon):
        sms2 = (
            "DEA:{lat},{lon}\r\n"
            "~{acc}m\r\n"
            "maps.google.com/?q={lat},{lon}\r\n"
            "EMERGENCIA MEDICA."
        ).format(lat=lat_str, lon=lon_str, acc=acc)
    else:
        sms2 = (
            "DEA S/N:{serial}\r\n"
            "GPS sin fix.\r\n"
            "EMERGENCIA MEDICA."
        ).format(serial=DEA_SERIAL)

    return [sms1, sms2]
