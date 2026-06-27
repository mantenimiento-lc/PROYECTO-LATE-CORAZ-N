# ============================================================
#  emergency.py — Lógica de emergencia DEA-001
#  Construye SMS, realiza llamada y registra el evento
# ============================================================

import time
from call_log import log_event
from gps_utils import maps_link, is_valid_fix


def build_sms(rtcs: str, gps: dict) -> list:
    """
    Construye el mensaje de emergencia completo.
    Retorna lista de strings — cada uno <= 160 chars (un SMS).

    SMS 1 — identificacion y fecha
    SMS 2 — ubicacion con link Google Maps y precision
    """
    lat = gps.get("latitude",   0.0)
    lon = gps.get("longitude",  0.0)
    acc = gps.get("accuracy_m", 999)

    lat_str = "{:.6f}".format(lat)
    lon_str = "{:.6f}".format(lon)
    gmaps   = "maps.google.com/?q={:.6f},{:.6f}".format(lat, lon)

    sms1 = (
        "EMERGENCIA DEA\r\n"
        "El DEA PRIMEDIC YA , SERIAL:A124C00947: FUE RETIRADO DEL GABINETE.\r\n"
        "Fecha: {}"
    ).format(rtcs)

    if is_valid_fix(lat, lon):
        sms2 = (
            "Ubicacion DEA PRIMEDIC , SERIAL: A124C00947:\r\n"
            "Lat: {lat}\r\n"
            "Lon: {lon}\r\n"
            "Precision: ~{acc} metros\r\n"
            "{gmaps}\r\n"
            "SE PRESUME EMERGENCIA MEDICA."
        ).format(lat=lat_str, lon=lon_str, acc=acc, gmaps=gmaps)
    else:
        sms2 = (
            "Ubicacion DEA PRIMEDIC , SERIAL: A124C00947:\r\n"
            "GPS sin fix disponible.\r\n"
            "SE PRESUME EMERGENCIA MEDICA."
        )

    return [sms1, sms2]


def handle_call(sim, phone_numbers: list, gps: dict) -> str:
    """
    Ejecuta la secuencia completa de emergencia:
      1. Obtiene hora del RTC
      2. Construye y envía SMS a todos los números
      3. Realiza la llamada al primer número
      4. Registra el evento en call_log
      5. Re-asegura GPS activo

    Retorna el timestamp del evento.
    """
    rtcs     = sim.get_rtc()
    mensajes = build_sms(rtcs, gps)

    # Enviar cada SMS por separado a todos los números
    for mensaje in mensajes:
        sim.send_sms(phone_numbers, mensaje)

    # Registrar SMS en log
    for number in phone_numbers:
        log_event(
            "SMS_SENT",
            rtcs,
            gps.get("latitude",  0.0),
            gps.get("longitude", 0.0),
            extra=number,
        )

    # Llamada
    print("LLAMANDO...")
    sim.dial(phone_numbers[0])

    # Registrar llamada en log
    log_event(
        "CALL",
        rtcs,
        gps.get("latitude",  0.0),
        gps.get("longitude", 0.0),
        extra=phone_numbers[0],
    )

    # Re-asegurar GPS
    sim.send_at("AT+CGNSSPWR=1", timeout_ms=1000)
    sim.send_at("AT+CGPSHOT",    timeout_ms=1000)

    return rtcs


def handle_hangup(sim) -> str:
    """
    Cuelga la llamada y registra el evento en call_log.
    Retorna el timestamp del evento.
    """
    rtcs = sim.get_rtc()
    sim.hang_up()

    log_event("HANGUP", rtcs, 0.0, 0.0)

    return rtcs
