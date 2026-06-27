# ============================================================
#  inputs.py — Gestión de pines de entrada e interrupciones
#  Reed switch (imán gabinete) y botón colgar
# ============================================================

import time
from machine import Pin
from config import PIN_REED, PIN_HANGUP, DEBOUNCE_MS


# ── Flags de solicitud (leídos desde main.py) ─────────────────
call_request = False
hang_request = False

# ── Anti-rebote ───────────────────────────────────────────────
_last_irq_call = 0
_last_irq_hang = 0

# ── Estado anterior de pines (para detectar cambio) ──────────
_prev_reed  = -1
_prev_hang  = -1

# ── Instancias de pines ───────────────────────────────────────
pin_reed   = Pin(PIN_REED,   Pin.IN, Pin.PULL_UP)
pin_hangup = Pin(PIN_HANGUP, Pin.IN, Pin.PULL_UP)


# ── Handlers de interrupción ──────────────────────────────────

def _irq_call(pin):
    global call_request, _last_irq_call
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_irq_call) > DEBOUNCE_MS:
        call_request = True
        _last_irq_call = now


def _irq_hang(pin):
    global hang_request, _last_irq_hang
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_irq_hang) > DEBOUNCE_MS:
        hang_request = True
        _last_irq_hang = now


def attach_interrupts():
    """Registra las IRQ. Llamar una sola vez en setup."""
    pin_reed.irq(trigger=Pin.IRQ_RISING,  handler=_irq_call)
    pin_hangup.irq(trigger=Pin.IRQ_FALLING, handler=_irq_hang)


def poll(call_in_progress: bool):
    """
    Lectura directa de pines como respaldo a las IRQ.
    Solo activa call_request en el FLANCO de subida del reed
    (transicion de iman presente a ausente), no continuamente.
    """
    global call_request, hang_request, _prev_reed, _prev_hang

    reed = pin_reed.value()
    hang = pin_hangup.value()

    # Reed: solo activar en el CAMBIO de 0→1 (iman que se retira)
    # Si ya hay llamada en progreso, ignorar completamente
    if reed == 1 and _prev_reed == 0 and not call_in_progress:
        print("Iman ausente -> LLAMAR")
        call_request = True
    elif reed == 0 and _prev_reed != 0:
        print("Iman presente -> gabinete cerrado")

    _prev_reed = reed

    # Boton colgar: solo en FLANCO de bajada (0→presionado)
    if hang == 0 and _prev_hang != 0:
        print("Boton colgar presionado")
        hang_request = True

    _prev_hang = hang


def consume_call() -> bool:
    """Lee y resetea el flag de llamada. Retorna True si había solicitud."""
    global call_request
    if call_request:
        call_request = False
        return True
    return False


def consume_hang() -> bool:
    """Lee y resetea el flag de colgar. Retorna True si había solicitud."""
    global hang_request
    if hang_request:
        hang_request = False
        return True
    return False
