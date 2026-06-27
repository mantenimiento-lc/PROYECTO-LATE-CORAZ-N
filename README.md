# DEA-001 — MicroPython
## ESP32-C3 Super Mini + SIM A7670SA

---

## Estructura del proyecto

```
micropython/
├── main.py          # Punto de entrada — loop principal (limpio)
├── config.py        # Toda la configuración en un solo lugar
├── sim_module.py    # Driver AT completo para el A7670SA (UART, GPS, HTTP, SMS, llamadas)
├── emergency.py     # Lógica de emergencia: construye SMS, hace llamada, registra evento
├── tracker.py       # Envío periódico de posición GPS al servidor HTTP
├── inputs.py        # Gestión de pines, interrupciones y debounce (reed + botón)
├── gps_utils.py     # Parseo CGNSSINFO, precisión HDOP→metros, enlace Google Maps
├── call_log.py      # Registro de llamadas en /call_log.txt dentro del ESP32
└── README.md
```

---

## Descripción de cada módulo

| Archivo | Responsabilidad |
|---|---|
| `main.py` | Setup + loop. Solo orquesta, no tiene lógica de negocio |
| `config.py` | Pines, números, APN, URLs, intervalos, flags de debug |
| `sim_module.py` | Todo lo que habla con el A7670SA por AT commands |
| `emergency.py` | Arma el SMS con mapa y precisión, hace la llamada, guarda en log |
| `tracker.py` | Construye JSON y lo envía por HTTP POST al servidor |
| `inputs.py` | Reed switch e IRQ con debounce, flags `call_request` / `hang_request` |
| `gps_utils.py` | Parsea `+CGNSSINFO`, convierte HDOP a metros, genera link Google Maps |
| `call_log.py` | Escribe y rota `/call_log.txt` en la flash del ESP32 |

---

## Requisitos de firmware

- **MicroPython para ESP32-C3** v1.23 o superior
- Descargar: https://micropython.org/download/esp32c3/

---

## Flashear el firmware

```bash
# 1. Instalar esptool
py -m pip install esptool

# 2. Borrar flash
py -m esptool --chip esp32c3 --port COM6 erase_flash

# 3. Flashear MicroPython
py -m esptool --chip esp32c3 --port COM6 --baud 460800 write_flash -z 0x0 esp32c3-xxxx.bin
```

---

## Subir archivos al ESP32

```bash
# Instalar mpremote si no lo tienes
py -m pip install mpremote

# Subir todos los archivos de una vez
py -m mpremote connect COM6 cp config.py      :config.py
py -m mpremote connect COM6 cp sim_module.py  :sim_module.py
py -m mpremote connect COM6 cp emergency.py   :emergency.py
py -m mpremote connect COM6 cp tracker.py     :tracker.py
py -m mpremote connect COM6 cp inputs.py      :inputs.py
py -m mpremote connect COM6 cp gps_utils.py   :gps_utils.py
py -m mpremote connect COM6 cp call_log.py    :call_log.py
py -m mpremote connect COM6 cp main.py        :main.py
```

> Cambiar `COM6` por el puerto que aparezca en `py -m mpremote connect list`

---

## Ver logs en tiempo real

```bash
py -m mpremote connect COM6 repl
```

Salir del REPL: `Ctrl + X`

Reinicio suave desde el REPL: `Ctrl + D`

---

## Configuración rápida — config.py

| Variable | Descripción | Default |
|---|---|---|
| `PHONE_NUMBERS` | Lista de 3 números de emergencia | `+573043659495` |
| `APN` | APN del operador | `internet.comcel.com.co` (Claro) |
| `TRACKING_URL` | Endpoint HTTPS del servidor | `latecorazon.com/api/tracking` |
| `HTTP_INTERVAL_MS` | Frecuencia de envío GPS (ms) | `10000` (10 seg) |
| `RESET_INTERVAL_MS` | Reinicio si no hay GPS (ms) | `900000` (15 min) |
| `PIN_REED` | GPIO reed switch | `0` |
| `PIN_HANGUP` | GPIO botón colgar | `1` |
| `USE_FAKE_GPS` | GPS simulado para debug | `False` |

---

## Pines de conexión

| Pin ESP32-C3 | Función | Conexión |
|---|---|---|
| GPIO 20 (RX) | UART RX | → TX del A7670SA |
| GPIO 21 (TX) | UART TX | → RX del A7670SA |
| GPIO 0 | Reed switch | Reed → GND, Pull-up interno |
| GPIO 1 | Botón colgar | Botón → GND, Pull-up interno |

---

## Lógica de operación

1. Al arrancar se registra evento `BOOT` en el log y se inicializa el A7670SA.
2. **Reed switch HIGH** (imán retirado del gabinete):
   - Envía SMS de emergencia a los 3 números configurados.
   - El SMS incluye coordenadas, precisión en metros y enlace a Google Maps.
   - Realiza llamada al primer número.
   - Registra `CALL` y `SMS_SENT` en `/call_log.txt`.
3. **Botón colgar LOW** → cuelga la llamada, registra `HANGUP`.
4. Cada 10 segundos envía posición GPS al servidor vía HTTP POST con campos:
   `latitude`, `longitude`, `date`, `imei`, `accuracy_m`, `speed`.
5. Si no hay fix GPS válido por 15 minutos → reinicio automático (registra `GPS_TIMEOUT`).

---

## Formato del SMS de emergencia

```
EMERGENCIA DEA

El DEA-001 fue retirado del gabinete.

Fecha: 2025-06-21 10:30:00

Ubicacion:
Lat: 6.123456
Lon: -75.654321
Precision: ~10 metros
Ver en mapa:
maps.google.com/?q=6.123456,-75.654321

Se presume uso por emergencia medica.
```

---

## Registro de llamadas — call_log.txt

El archivo `/call_log.txt` vive en la flash del ESP32 y sobrevive reinicios.

**Formato de cada línea:**
```
YYYY-MM-DD HH:MM:SS | EVENTO     | LATITUD    | LONGITUD     | EXTRA
2025-06-21 10:30:00 | CALL       |   6.123456 |  -75.654321  | +573043659495
2025-06-21 10:30:00 | SMS_SENT   |   6.123456 |  -75.654321  | +573043659495
2025-06-21 10:35:00 | HANGUP     |   0.000000 |    0.000000  |
2025-06-21 00:00:00 | BOOT       |   0.000000 |    0.000000  |
2025-06-21 10:45:00 | GPS_TIMEOUT|   0.000000 |    0.000000  |
```

**Leer el log desde el REPL:**
```python
from call_log import print_log
print_log()
```

**Borrar el log:**
```python
from call_log import clear_log
clear_log()
```

El log rota automáticamente cuando supera 200 entradas — elimina la mitad más antigua.

---

## Debug GPS simulado

Activar en `config.py`:
```python
USE_FAKE_GPS = True
```
Simula coordenadas de Medellín con variación aleatoria mínima y precisión de 6 metros.
