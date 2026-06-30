# ============================================================
#  config.py — Configuración global del proyecto DEA
#  Hardware: ESP32-C3 Super Mini + A7670SA
# ============================================================

# ── Pines UART → A7670SA ──────────────────────────────────────
SIM_TX_PIN  = 21
SIM_RX_PIN  = 20
SIM_BAUDRATE = 115200

# ── Pines de entradas ─────────────────────────────────────────
PIN_REED   = 0   # Reed switch (imán gabinete) — INPUT_PULLUP
PIN_HANGUP = 1   # Botón colgar               — INPUT_PULLUP

# ── Números de teléfono ───────────────────────────────────────
# Solo llamadas (2 destinos)
CALL_NUMBERS = [
    "+573043659495",
    "+573043659495",
]

# Solo mensajes de texto (3 destinos)
SMS_NUMBERS = [
    "+573043659495",
    "+573043659495",
    "+573043659495",
]

# ── APN por operador ──────────────────────────────────────────
# Formato: {mcc_mnc: apn}
APN_MAP = {
    "732101": "internet.claro.com.co",    # Claro Colombia
    "732103": "web.colombiamovil.com.co", # Tigo Colombia
    "732111": "internet.movistar.com.co", # Movistar Colombia
    "732123": "internet.movistar.com.co", # Movistar Colombia (alt)
    "732130": "apn.colombia.com",         # Avantel
    "732154": "internet.une.net.co",      # UNE / ETB
    "732165": "internet.virgin.com.co",   # Virgin Mobile
    "732187": "internet.uff.com.co",      # Uff Movil
}

# APN por defecto si no se detecta el operador
APN = "web.colombiamovil.com.co"

# ── DNS ───────────────────────────────────────────────────────
DNS_PRIMARY   = "8.8.8.8"
DNS_SECONDARY = "8.8.4.4"

# ── URLs de servidor ──────────────────────────────────────────
TRACKING_URL = "https://latecorazon.com/api/tracking"
MONITOR_URL  = "https://proyecto-late-coraz-n-production.up.railway.app/api/heartbeat"

# ── Intervalos (ms) ───────────────────────────────────────────
HTTP_INTERVAL_MS      = 10_000    # Envío de posición GPS
HEARTBEAT_INTERVAL_MS = 30_000    # Señal de vida al monitor
CALL_RETRY_MS         = 30_000    # Reintento de llamada
CONFIRM_TIMEOUT_MS    = 30_000    # Retardo antes de disparar alerta
RESET_INTERVAL_MS     = 1_800_000 # Reset si no hay GPS (30 min)

# ── Debounce ──────────────────────────────────────────────────
DEBOUNCE_MS = 200

# ── Ganancia de audio ─────────────────────────────────────────
OUT_GAIN = 7
MIC_GAIN = 7

# ── GPS simulado (debug sin antena) ───────────────────────────
USE_FAKE_GPS = False
FAKE_LAT     =  6.200000
FAKE_LON     = -75.600000
