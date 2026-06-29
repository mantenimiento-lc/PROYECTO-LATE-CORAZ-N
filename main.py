# ============================================================
#  main.py — DEA-001  (ESP32-C3 Super Mini + A7670SA)
#  MicroPython
# ============================================================

import time
import machine

from config      import (CALL_NUMBERS, SMS_NUMBERS,
                         HTTP_INTERVAL_MS, HEARTBEAT_INTERVAL_MS,
                         RESET_INTERVAL_MS, CALL_RETRY_MS, CONFIRM_TIMEOUT_MS)
from sim_module  import SIMModule
from emergency   import build_sms
from tracker     import send_position
from heartbeat   import send_heartbeat
from call_log    import log_event
import inputs

# ── Hardware ──────────────────────────────────────────────────
sim = SIMModule()

# ── Estado ────────────────────────────────────────────────────
# Fases de la emergencia
IDLE       = 0   # gabinete cerrado, sistema en espera
ALERTING   = 1   # iman retirado — llamando hasta que contesten
ANSWERED   = 2   # alguien contesto — parar llamadas
CONFIRMING = 3   # iman retirado — esperando confirmacion antes de alertar

state               = IDLE
sms_sent            = False       # SMS ya enviados en este evento
call_index          = 0           # a cual numero de la lista estamos llamando
last_call_time      = 0           # cuando fue la ultima llamada
call_start_time     = 0           # cuando inicio la llamada actual (para medir duracion)
confirm_start       = 0           # cuando inicio el retardo de confirmacion
last_valid_gps_time = time.ticks_ms()
last_http_time      = time.ticks_ms() - HTTP_INTERVAL_MS
last_heartbeat_time = time.ticks_ms() - HEARTBEAT_INTERVAL_MS  # primer heartbeat inmediato
last_gps            = {"latitude": 0.0, "longitude": 0.0,
                       "accuracy_m": 999, "timedate": "", "valid": False}


# ── Setup ─────────────────────────────────────────────────────

def setup():
    global last_valid_gps_time

    print("DEA arrancando...")
    log_event("BOOT", "inicio", 0.0, 0.0)

    sim.prepare()
    sim.configure_sms()
    sim._feed()
    sim.print_status()
    sim._feed()
    inputs.attach_interrupts()

    last_valid_gps_time = time.ticks_ms()
    print("Setup completo.")
    send_heartbeat(sim, "BOOT", "DEA iniciado correctamente")


# ── Loop ──────────────────────────────────────────────────────

def loop():
    global state, sms_sent, call_index, last_call_time, call_start_time, confirm_start
    global last_valid_gps_time, last_http_time, last_heartbeat_time, last_gps

    reed_ausente = inputs.pin_reed.value() == 1  # HIGH = iman retirado

    # ── Deteccion de imán retirado → iniciar retardo de confirmacion ──
    if reed_ausente and state == IDLE:
        print("Iman retirado — esperando confirmacion ({} seg)...".format(CONFIRM_TIMEOUT_MS // 1000))
        confirm_start = time.ticks_ms()
        state = CONFIRMING

    # ── Estado CONFIRMING: retardo antes de disparar alerta ──
    if state == CONFIRMING:
        # Alimentar WDT mientras esperamos
        sim._feed()

        # Cancelar si el iman regreso
        if not reed_ausente:
            print("Iman devuelto — alerta cancelada (traslado rutinario)")
            ts = last_gps.get("timedate", "") or sim.get_rtc()
            log_event("CANCELLED", ts, 0.0, 0.0)
            send_heartbeat(sim, "CANCELLED", "Iman devuelto — traslado rutinario")
            state = IDLE
            return

        # Cancelar si presionan el boton de colgar (iman dentro o fuera)
        if inputs.consume_hang():
            print("Boton presionado — alerta cancelada por operador")
            ts = last_gps.get("timedate", "") or sim.get_rtc()
            log_event("CANCELLED", ts, 0.0, 0.0)
            send_heartbeat(sim, "CANCELLED", "Cancelado por operador — boton presionado")
            state = IDLE
            return

        # Mostrar cuenta regresiva cada 5 segundos
        elapsed = time.ticks_diff(time.ticks_ms(), confirm_start)
        remaining = (CONFIRM_TIMEOUT_MS - elapsed) // 1000
        if elapsed % 5000 < 100:
            print("ALERTA en {} seg — presione boton para cancelar".format(remaining))

        # Retardo cumplido → disparar emergencia
        if elapsed >= CONFIRM_TIMEOUT_MS:
            print("EMERGENCIA CONFIRMADA: activando alerta")
            ts = last_gps.get("timedate", "") or sim.get_rtc()
            log_event("EMERGENCY", ts,
                      last_gps.get("latitude", 0.0),
                      last_gps.get("longitude", 0.0))
            send_heartbeat(sim, "EMERGENCY", "DEA retirado del gabinete",
                           lat=last_gps.get("latitude", 0.0),
                           lon=last_gps.get("longitude", 0.0))
            state      = ALERTING
            sms_sent   = False
            call_index = 0
            last_call_time = 0

        return  # no hacer nada mas mientras se confirma

    # ── Cancelar emergencia activa si el iman regresa ──
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

        # 1. Enviar SMS una sola vez a todos los numeros SMS
        if not sms_sent:
            print("Enviando SMS de emergencia...")
            rtcs     = last_gps.get("timedate", "") or sim.get_rtc()
            mensajes = build_sms(rtcs, last_gps)
            # Enviar a numeros unicos solamente
            numeros_unicos = list(dict.fromkeys(SMS_NUMBERS))
            for msg in mensajes:
                for number in numeros_unicos:
                    sim._feed()
                    sim.send_sms([number], msg)
            sms_sent = True
            log_event("SMS_SENT", rtcs,
                      last_gps.get("latitude", 0.0),
                      last_gps.get("longitude", 0.0))
            send_heartbeat(sim, "SMS_SENT",
                           "SMS enviado a {} numeros".format(len(numeros_unicos)),
                           lat=last_gps.get("latitude", 0.0),
                           lon=last_gps.get("longitude", 0.0))

        # 2. Llamar al siguiente numero de la lista en loop
        now = time.ticks_ms()
        if time.ticks_diff(now, last_call_time) >= CALL_RETRY_MS:
            number = CALL_NUMBERS[call_index % len(CALL_NUMBERS)]
            print("Llamando a {} (intento {})...".format(number, call_index + 1))
            sim.dial(number)
            call_start_time = time.ticks_ms()  # marcar inicio de llamada
            ts = last_gps.get("timedate", "") or sim.get_rtc()
            log_event("CALL", ts,
                      last_gps.get("latitude", 0.0),
                      last_gps.get("longitude", 0.0),
                      extra=number)
            send_heartbeat(sim, "CALL",
                           "Llamando a {}".format(number),
                           lat=last_gps.get("latitude", 0.0),
                           lon=last_gps.get("longitude", 0.0),
                           extra=number)
            last_call_time = time.ticks_ms()
            call_index += 1

        # 3. Detectar si alguien contesto (modulo manda VOICE CALL: BEGIN o ATH)
        if sim.uart.any():
            raw = sim.uart.read(sim.uart.any())
            if raw:
                s = "".join([chr(b) if b < 128 else '?' for b in raw])
                if "VOICE CALL: BEGIN" in s or "VOICE CALL: END" in s:
                    duracion_s = time.ticks_diff(time.ticks_ms(), call_start_time) // 1000
                    mins = duracion_s // 60
                    segs = duracion_s % 60
                    dur_str = "{}min {}seg".format(mins, segs) if mins > 0 else "{}seg".format(segs)
                    print("Llamada contestada — duracion: {}".format(dur_str))
                    state = ANSWERED
                    ts = last_gps.get("timedate", "") or sim.get_rtc()
                    log_event("ANSWERED", ts, 0.0, 0.0, extra=dur_str)
                    send_heartbeat(sim, "ANSWERED",
                                   "Llamada contestada — duracion: {}".format(dur_str),
                                   extra=dur_str)
                elif "NO CARRIER" in s or "BUSY" in s or "NO ANSWER" in s:
                    print("Sin respuesta — intentando siguiente numero...")
                    last_call_time = 0

    # ── Leer GPS ──
    gps = sim.get_gps()
    if gps["valid"]:
        last_gps            = gps
        last_valid_gps_time = time.ticks_ms()

    # ── Watchdog GPS ──
    if time.ticks_diff(time.ticks_ms(), last_valid_gps_time) > RESET_INTERVAL_MS:
        print("Sin GPS 30 min. Reiniciando...")
        log_event("GPS_TIMEOUT", "N/A", 0.0, 0.0)
        send_heartbeat(sim, "GPS_TIMEOUT", "Sin fix GPS por 30 minutos — reiniciando")
        machine.reset()

    # ── Envio HTTP periodico ──
    if time.ticks_diff(time.ticks_ms(), last_http_time) >= HTTP_INTERVAL_MS:
        last_http_time = time.ticks_ms()
        send_position(sim, last_gps)

    # ── Heartbeat periodico al servidor de monitoreo ──
    if time.ticks_diff(time.ticks_ms(), last_heartbeat_time) >= HEARTBEAT_INTERVAL_MS:
        last_heartbeat_time = time.ticks_ms()
        send_heartbeat(sim, "HEARTBEAT",
                       lat=last_gps.get("latitude",  0.0),
                       lon=last_gps.get("longitude", 0.0))


# ── Arranque ──────────────────────────────────────────────────

setup()

while True:
    loop()
    time.sleep_ms(100)
