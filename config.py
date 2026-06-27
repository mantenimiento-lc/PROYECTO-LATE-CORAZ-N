# ============================================================
#  config.py — Configuración global del proyecto DEA-001
#  Hardware: ESP32-C3 Super Mini + A7670SA
# ============================================================
 
# Pines UART hacia el módulo A7670SA
SIM_TX_PIN = 21
SIM_RX_PIN = 20
SIM_BAUDRATE = 115200

# Pines de entradas
PIN_REED   = 0   # Reed switch (sensor imán del gabinete) — INPUT_PULLUP
PIN_HANGUP = 1   # Botón colgar                            — INPUT_PULLUP

# Números de teléfono — solo llamadas (2 destinos)
CALL_NUMBERS = [
    "+573104382572",
    "+573242663949",
]

# Números de teléfono — solo mensajes de texto (3 destinos)
SMS_NUMBERS = [
    "+573043659495",
    "+573235138812",
    "+573003455313",
]

# APN por operador — deteccion automatica en sim_module.py
# Formato: {codigo_mcc_mnc: apn}
APN_MAP = {
    "732101": "internet.claro.com.co",   # Claro Colombia
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

# DNS
DNS_PRIMARY   = "8.8.8.8"
DNS_SECONDARY = "8.8.4.4"

# Endpoint de tracking
TRACKING_URL = "https://latecorazon.com/api/tracking"

# Intervalo de envío HTTP (ms)
HTTP_INTERVAL_MS = 10_000

# Intervalo de reinicio si no hay GPS válido (ms) — 30 minutos
RESET_INTERVAL_MS = 1_800_000

# Intervalo entre reintentos de llamada (ms) — 30 segundos
CALL_RETRY_MS = 30_000

# Retardo de confirmacion antes de disparar la alerta (ms) — 30 segundos
# Durante este tiempo el boton de colgar o devolver el iman cancela la alerta
CONFIRM_TIMEOUT_MS = 30_000

# Debounce para interrupciones (ms)
DEBOUNCE_MS = 200

# Ganancia de audio / micrófono
OUT_GAIN = 7
MIC_GAIN = 7

# GPS simulado (True = datos falsos, útil para debug sin antena)
USE_FAKE_GPS = False
FAKE_LAT  =  6.200000
FAKE_LON  = -75.600000
