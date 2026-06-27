# ============================================================
#  gps_utils.py — Utilidades de GPS y ubicación
#  Precisión HDOP, enlace Google Maps, validación de fix
# ============================================================

import math


# ── Tabla de precisión HDOP → metros aproximados ─────────────
# El módulo A7670SA entrega HDOP en +CGNSSINFO campo [2]
# Referencia: HDOP * factor_base ≈ error horizontal en metros
_HDOP_BASE_METERS = 5.0   # GPS civil típico con señal buena


def hdop_to_meters(hdop: float) -> int:
    """
    Convierte HDOP a precisión estimada en metros.
    Retorna entero redondeado al alza.

    Ejemplos:
        hdop=1.0  → ~5 m   (excelente)
        hdop=2.0  → ~10 m  (bueno)
        hdop=5.0  → ~25 m  (moderado)
        hdop=10.0 → ~50 m  (pobre)
    """
    if hdop <= 0:
        return 999
    return int(math.ceil(hdop * _HDOP_BASE_METERS))


def maps_link(lat: float, lon: float) -> str:
    """
    Genera un enlace corto de Google Maps con las coordenadas.
    Formato: https://maps.google.com/?q=LAT,LON
    """
    return "maps.google.com/?q={:.6f},{:.6f}".format(lat, lon)


def is_valid_fix(lat: float, lon: float) -> bool:
    """Valida que las coordenadas no sean el valor nulo (0,0)."""
    return not (lat == 0.0 and lon == 0.0)


def parse_cgnssinfo(resp: str) -> dict:
    """
    Parsea la respuesta completa de AT+CGNSSINFO.

    Formato SIMCOM A7670:
    +CGNSSINFO: <fix>,<sat_used>,<HDOP>,<PDOP>,<VDOP>,<lat>,<N/S>,<lon>,<E/W>,
                <date>,<UTC_time>,<alt>,<speed>,<course>

    Retorna dict con:
        latitude, longitude, hdop, accuracy_m, timedate, speed, valid
    """
    result = {
        "latitude":   0.0,
        "longitude":  0.0,
        "hdop":       99.9,
        "accuracy_m": 999,
        "timedate":   "",
        "speed":      0.0,
        "valid":      False,
    }

    if "+CGNSSINFO:" not in resp:
        return result

    try:
        idx     = resp.index("+CGNSSINFO:")
        line    = resp[idx:].split("\r\n")[0]
        payload = line.split(":", 1)[1].strip()
        parts   = [p.strip() for p in payload.split(",")]

        # Necesitamos al menos 13 campos
        if len(parts) < 13:
            return result

        # fix mode: 0=no fix, 1=2D, 2=3D
        fix_mode = parts[0]
        if fix_mode == "0" or fix_mode == "":
            return result

        hdop_str = parts[2]
        lat_str  = parts[5]
        lat_hem  = parts[6]
        lon_str  = parts[7]
        lon_hem  = parts[8]
        date_str = parts[9]   # DDMMYY
        time_str = parts[10]  # HHMMSS.ss
        speed_str = parts[12] # km/h

        if not lat_str or not lon_str:
            return result

        lat  = float(lat_str)
        lon  = float(lon_str)
        hdop = float(hdop_str) if hdop_str else 99.9

        if lat_hem == "S":
            lat = -lat
        if lon_hem == "W":
            lon = -lon

        # Convertir fecha DDMMYY + hora HHMMSS a string legible
        timedate = ""
        if len(date_str) == 6 and len(time_str) >= 6:
            dd = date_str[0:2]
            mm = date_str[2:4]
            yy = date_str[4:6]
            hh = time_str[0:2]
            mi = time_str[2:4]
            ss = time_str[4:6]
            timedate = "20{}-{}-{} {}:{}:{}".format(yy, mm, dd, hh, mi, ss)

        speed = float(speed_str) if speed_str else 0.0

        result.update({
            "latitude":   lat,
            "longitude":  lon,
            "hdop":       hdop,
            "accuracy_m": hdop_to_meters(hdop),
            "timedate":   timedate,
            "speed":      speed,
            "valid":      True,
        })

    except Exception as e:
        print("gps_utils parse error:", e)

    return result
