# ============================================================
#  main.py — DEA-001  (ESP32-C3 Super Mini + A7670SA)
#  MicroPython
# ============================================================

import time
import machine

from config      import PHONE_NUMBERS, HTTP_INTERVAL_MS, RESET_INTERVAL_MS, CALL_RETRY_MS
from sim_module  import SIMModule
from emergency   import build_sms, handle_hangup
from tracker     import send_position
from call_log    import log_event
import inputs

# ── Hardware ──────────────────────────────────────────────────
sim = SIMModule()

# ── Estado ────────────────────────────────────────────────────
# Fases de la emergencia
IDLE      = 0   # gabinete cerrado, sistema en espera
ALERTING  = 1   # iman retirado — llamando hasta que contesten
ANSWERED  = 2   # alguien contesto — parar llamadas

state               = IDLE
sms_sent            = False       # SMS ya enviados en este evento
call_index          = 0           # a cual numero de la lista estamos llamando
last_call_time      = 0           # cuando fue la ultima llamada
last_valid_gps_time = time.ticks_ms()
last_http_time      = time.ticks_ms() - HTTP_INTERVAL_MS
last_gps            = {"latitude": 0.0, "longitude": 0.0,
                       "accuracy_m": 999, "timedate": "", "valid": False}


# ── Setup ─────────────────────────────────────────────────────

def setup():
    global last_valid_gps_time

    print("DEA-001 arrancando...")
    log_event("BOOT", "inicio", 0.0, 0.0)

    sim.prepare()
    sim.configure_sms()
    sim._feed()
    sim.print_status()
    sim._feed()
    inputs.attach_interrupts()

    last_valid_gps_time = time.ticks_ms()
    print("Setup completo.")


# ── Loop ──────────────────────────────────────────────────────

def loop():
    global state, sms_sent, call_index, last_call_time
    global last_valid_gps_time, last_http_time, last_gps

    reed_ausente = inputs.pin_reed.value() == 1  # HIGH = iman retirado

    # ── Deteccion de imán retirado → activar emergencia ──
    if reed_ausente and state == IDLE:
        print("EMERGENCIA: iman retirado del gabinete")
        ts = last_gps.get("timedate", "") or sim.get_rtc()
        log_event("EMERGENCY", ts,
                  last_gps.get("latitude", 0.0),
                  last_gps.get("longitude", 0.0))
        state      = ALERTING
        sms_sent   = False
        call_index = 0
        last_call_time = 0

    if not reed_ausente and state in (ALERTING, ANSWERED):
        print("Gabinete cerrado — emergencia cancelada")
        sim.hang_up()
        ts = last_gps.get("timedate", "") or sim.get_rtc()
        log_event("CANCELLED", ts, 0.0, 0.0)
        state    = IDLE
        sms_sent = False
        call_index = 0
        return

    # ── Logica de emergencia activa ──
    if state == ALERTING:

        # 1. Enviar SMS una sola vez a todos los numeros
        if not sms_sent:
            print("Enviando SMS de emergencia...")
            rtcs     = last_gps.get("timedate", "") or sim.get_rtc()
            mensajes = build_sms(rtcs, last_gps)
            # Enviar a numeros unicos solamente
            numeros_unicos = list(dict.fromkeys(PHONE_NUMBERS))
            for msg in mensajes:
                for number in numeros_unicos:
                    sim._feed()
                    sim.send_sms([number], msg)
            sms_sent = True
            log_event("SMS_SENT", rtcs,
                      last_gps.get("latitude", 0.0),
                      last_gps.get("longitude", 0.0))

        # 2. Llamar al siguiente numero de la lista en loop
        now = time.ticks_ms()
        if time.ticks_diff(now, last_call_time) >= CALL_RETRY_MS:
            number = PHONE_NUMBERS[call_index % len(PHONE_NUMBERS)]
            print("Llamando a {} (intento {})...".format(number, call_index + 1))
            sim.dial(number)
            ts = last_gps.get("timedate", "") or sim.get_rtc()
            log_event("CALL", ts,
                      last_gps.get("latitude", 0.0),
                      last_gps.get("longitude", 0.0),
                      extra=number)
            last_call_time = time.ticks_ms()
            call_index += 1

        # 3. Detectar si alguien contesto (modulo manda VOICE CALL: BEGIN o ATH)
        if sim.uart.any():
            raw = sim.uart.read(sim.uart.any())
            if raw:
                s = raw.decode("utf-8", "ignore")
                if "VOICE CALL: BEGIN" in s or "ATH" in s:
                    print("Llamada contestada — deteniendo llamadas")
                    state = ANSWERED
                    ts = last_gps.get("timedate", "") or sim.get_rtc()
                    log_event("ANSWERED", ts, 0.0, 0.0)
                elif "NO CARRIER" in s or "BUSY" in s or "NO ANSWER" in s:
                    # Nadie contesto — seguir con el siguiente numero
                    print("Sin respuesta, siguiente numero...")
                    last_call_time = 0  # llamar de inmediato al siguiente

    # ── Leer GPS ──
    gps = sim.get_gps()
    if gps["valid"]:
        last_gps            = gps
        last_valid_gps_time = time.ticks_ms()

    # ── Watchdog GPS ──
    if time.ticks_diff(time.ticks_ms(), last_valid_gps_time) > RESET_INTERVAL_MS:
        print("Sin GPS 30 min. Reiniciando...")
        log_event("GPS_TIMEOUT", "N/A", 0.0, 0.0)
        machine.reset()

    # ── Envio HTTP periodico ──
    if time.ticks_diff(time.ticks_ms(), last_http_time) >= HTTP_INTERVAL_MS:
        last_http_time = time.ticks_ms()
        send_position(sim, last_gps)


# ── Arranque ──────────────────────────────────────────────────

setup()

while True:
    loop()
    time.sleep_ms(100)
