# DEA — Sistema de Alerta de Emergencia
## ESP32-C3 Super Mini + SIM A7670SA + Dashboard de monitoreo

---

## Descripción general

Sistema embebido de alerta automática para gabinetes de DEA (Desfibrilador Externo Automático).
Al retirar el imán del gabinete (reed switch), el dispositivo:

1. Espera **30 segundos** de confirmación — el operador puede cancelar devolviendo el imán o presionando el botón
2. Si no se cancela: envía **SMS de emergencia** a los números configurados
3. Realiza **llamadas** ciclando entre los números hasta que alguien conteste
4. Envía **posición GPS** al servidor cada 10 segundos
5. Reporta el **estado del sistema** al dashboard de monitoreo en Railway

---

## Estructura del proyecto

```
Late Corazón/
├── Main.py          # Punto de entrada — setup() + loop principal
├── config.py        # Toda la configuración: pines, números, URLs, intervalos
├── sim_module.py    # Driver AT completo para el A7670SA (UART, GPS, HTTP, SMS, llamadas)
├── emergency.py     # Construye los SMS de alerta con GPS y fecha
├── tracker.py       # Envío periódico de posición GPS al servidor HTTP
├── heartbeat.py     # Reporte de estado al dashboard de monitoreo (Railway)
├── inputs.py        # Gestión de pines, interrupciones y debounce (reed + botón)
├── gps_utils.py     # Parseo CGNSSINFO, precisión HDOP→metros, enlace Google Maps
├── call_log.py      # Registro local de eventos en /call_log.txt (flash ESP32)
├── dashboard/       # Servidor web de monitoreo remoto
│   ├── main.py      # FastAPI — API REST + sirve el dashboard HTML
│   ├── database.py  # PostgreSQL — modelos y queries
│   ├── static/
│   │   └── index.html  # Dashboard web completo
│   ├── requirements.txt
│   ├── Procfile
│   └── railway.toml
└── README.md
```

---

## Módulos del dispositivo

| Archivo | Responsabilidad |
|---|---|
| `Main.py` | Orquesta todo. Máquina de estados: IDLE → CONFIRMING → ALERTING → ANSWERED |
| `config.py` | Pines, números, APN, URLs, intervalos, flags de debug |
| `sim_module.py` | Todo lo que habla con el A7670SA por AT commands |
| `emergency.py` | Arma el SMS con coordenadas y enlace Google Maps |
| `tracker.py` | JSON con GPS + señal + temperatura, POST a latecorazon.com y Railway |
| `heartbeat.py` | Reporta eventos (BOOT, EMERGENCY, CALL, etc.) al dashboard |
| `inputs.py` | Reed switch e IRQ con debounce, flags de solicitud |
| `gps_utils.py` | Parsea `+CGNSSINFO`, convierte HDOP a metros |
| `call_log.py` | Escribe y rota `/call_log.txt` en la flash del ESP32 |

---

## Máquina de estados (Main.py)

```
IDLE (0) → CONFIRMING (3) → ALERTING (1) → ANSWERED (2)
               ↓ cancelar          ↑ 30 seg sin cancelar
              IDLE               sin llamadas aunque imán siga afuera
```

| Estado | Descripción |
|---|---|
| `IDLE` | Gabinete cerrado, sistema en espera |
| `CONFIRMING` | Imán retirado — esperando 30 seg antes de alertar. Cancelable con botón o devolviendo el imán |
| `ALERTING` | Emergencia activa — enviando SMS y llamando en ciclo |
| `ANSWERED` | Alguien contestó — detiene llamadas, sigue tracking GPS |

---

## Configuración — config.py

| Variable | Descripción | Default |
|---|---|---|
| `CALL_NUMBERS` | Números para llamadas (2) | `+573043659495` |
| `SMS_NUMBERS` | Números para SMS (3) | `+573043659495` |
| `DEA_SERIAL` | Serial del equipo impreso en el gabinete | `A124C00947` |
| `APN` | APN por defecto | `web.colombiamovil.com.co` |
| `TRACKING_URL` | Endpoint GPS servidor principal | `latecorazon.com/api/tracking` |
| `MONITOR_URL` | Endpoint dashboard Railway | `*.railway.app/api/heartbeat` |
| `HTTP_INTERVAL_MS` | Frecuencia envío GPS | `10000` (10 seg) |
| `HEARTBEAT_INTERVAL_MS` | Frecuencia señal de vida al monitor | `30000` (30 seg) |
| `CONFIRM_TIMEOUT_MS` | Retardo antes de activar alerta | `30000` (30 seg) |
| `RESET_INTERVAL_MS` | Reinicio si no hay GPS | `1800000` (30 min) |
| `USE_FAKE_GPS` | GPS simulado para debug | `False` |

---

## Pines de conexión

| Pin ESP32-C3 | Función | Conexión |
|---|---|---|
| GPIO 20 (RX) | UART RX | → TX del A7670SA |
| GPIO 21 (TX) | UART TX | → RX del A7670SA |
| GPIO 0 | Reed switch | Reed → GND, Pull-up interno |
| GPIO 1 | Botón colgar / cancelar | Botón → GND, Pull-up interno |

---

## Subir archivos al ESP32

```bash
py -m pip install mpremote

py -m mpremote connect COM9 cp config.py      :config.py
py -m mpremote connect COM9 cp sim_module.py  :sim_module.py
py -m mpremote connect COM9 cp emergency.py   :emergency.py
py -m mpremote connect COM9 cp tracker.py     :tracker.py
py -m mpremote connect COM9 cp heartbeat.py   :heartbeat.py
py -m mpremote connect COM9 cp inputs.py      :inputs.py
py -m mpremote connect COM9 cp gps_utils.py   :gps_utils.py
py -m mpremote connect COM9 cp call_log.py    :call_log.py
py -m mpremote connect COM9 cp Main.py        :main.py
```

Ver logs en tiempo real:
```bash
py -m mpremote connect COM9 repl
```

Descargar log de llamadas:
```bash
py -m mpremote connect COM9 cp :call_log.txt call_log.txt
```

---

## Formato del SMS de emergencia

**SMS 1** — identificación:
```
EMERGENCIA DEA
DEA PRIMEDIC S/N:A124C00947 RETIRADO DEL GABINETE.
Fecha: 2026-06-29 10:30:00
```

**SMS 2** — ubicación (máx 160 chars):
```
DEA:6.138689,-75.570850
~15m
maps.google.com/?q=6.138689,-75.570850
EMERGENCIA MEDICA.
```

---

## Dashboard de monitoreo — Railway

URL: `https://proyecto-late-coraz-n-production.up.railway.app`

### Funcionalidades
- Estado en tiempo real: **En línea / Sin señal / Apagado**
- Señal celular con etiqueta descriptiva (Excelente, Buena, Sin señal, Apagado)
- Temperatura con alerta visual a partir de **72°C**
- **Uptime sesión** — tiempo desde el último reinicio (verde)
- **Uptime total** — tiempo desde el primer registro (azul)
- Contador de reinicios con botón de reset por equipo
- Historial de eventos con checkbox para eliminar por fila
- Historial de reinicios con causa detectada automáticamente
- Registro de emergencias con coordenadas y link a Google Maps
- Selector de equipo para filtrar eventos por dispositivo
- Auto-refresh cada 30 segundos

### Eventos registrados

| Evento | Cuándo ocurre |
|---|---|
| `BOOT` | Cada arranque del ESP32 |
| `HEARTBEAT` | Cada 30 segundos (señal de vida) |
| `EMERGENCY` | Al confirmar emergencia (30 seg sin cancelar) |
| `SMS_SENT` | Al enviar SMS de alerta |
| `CALL` | Cada llamada realizada (con número en extra) |
| `ANSWERED` | Al contestar (con duración en extra) |
| `CANCELLED` | Al cancelar alerta (botón o imán devuelto) |
| `GPS_TIMEOUT` | Sin fix GPS por 30 minutos |
| `TRACKING` | Última posición GPS recibida |

### Base de datos
PostgreSQL en Railway — datos persistentes, no se borran con reinicios o redeploys.

---

## Debug GPS simulado

```python
# config.py
USE_FAKE_GPS = True
```

Simula coordenadas de Medellín con variación aleatoria mínima.

---

## Comandos útiles desde REPL

```python
# Leer log local del dispositivo
from call_log import print_log
print_log()

# Borrar log local
from call_log import clear_log
clear_log()
```
