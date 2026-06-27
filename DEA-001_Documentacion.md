# DEA-001 — Documentación completa del código
## Cómo funciona el sistema desde cero

---

## El concepto general

Imagina el dispositivo como un vigilante que está dormido esperando que pase algo. Ese "algo" es que alguien retire el imán del gabinete del DEA. Cuando eso ocurre, el vigilante despierta, manda mensajes de emergencia, llama, y sigue reportando la ubicación hasta que todo se resuelva.

---

## 1. El arranque — main.py + setup()

Cuando conectas el USB o se reinicia la ESP32, MicroPython busca automáticamente un archivo llamado `main.py` y lo ejecuta. Ahí empieza todo.

```python
setup()         # configura todo el hardware
while True:     # loop infinito
    loop()      # revisa qué está pasando
    time.sleep_ms(100)  # espera 100ms y vuelve a revisar
```

`setup()` hace 4 cosas:
1. Registra el arranque en el log → evento BOOT
2. Inicializa el módulo SIM → sim.prepare()
3. Configura modo SMS → sim.configure_sms()
4. Activa las interrupciones del reed switch y botón → inputs.attach_interrupts()

---

## 2. La configuración — config.py

Es el único lugar con valores editables. Nunca hay números o URLs hardcodeados en otros archivos.

```python
PHONE_NUMBERS = ["+573245326622", "+573043659495", ...]  # a quién llamar
TRACKING_URL  = "https://latecorazon.com/api/tracking"  # servidor GPS
HTTP_INTERVAL_MS  = 10_000    # enviar GPS cada 10 segundos
RESET_INTERVAL_MS = 1_800_000 # reiniciar si no hay GPS en 30 min
CALL_RETRY_MS     = 30_000    # reintentar llamada cada 30 seg
PIN_REED   = 0   # GPIO del reed switch
PIN_HANGUP = 1   # GPIO del botón colgar
```

Parámetros editables:

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| PHONE_NUMBERS | Lista de números de emergencia | +573245326622 |
| TRACKING_URL | Servidor donde se envía el GPS | latecorazon.com/api/tracking |
| HTTP_INTERVAL_MS | Frecuencia de envío GPS | 10000 (10 seg) |
| RESET_INTERVAL_MS | Reinicio si no hay GPS | 1800000 (30 min) |
| CALL_RETRY_MS | Tiempo entre llamadas | 30000 (30 seg) |
| PIN_REED | GPIO del reed switch | 0 |
| PIN_HANGUP | GPIO del botón colgar | 1 |
| USE_FAKE_GPS | GPS simulado para pruebas | False |

---

## 3. El hardware — sim_module.py

Es el módulo más grande. Contiene la clase `SIMModule` que habla con el chip A7670SA a través de comandos AT por UART.

### ¿Qué es un comando AT?

Es un protocolo de texto de los años 80 que usan todos los módems. Le mandas un texto y el chip responde:

```
Tú envías:     AT+CSQ\r\n
Chip responde: +CSQ: 18,0\r\nOK\r\n
```

### Métodos principales de SIMModule

| Método | Qué hace |
|--------|----------|
| prepare() | Secuencia de arranque: red, datos, GPS |
| send_at() | Envía un comando AT y retorna la respuesta |
| get_gps() | Lee coordenadas con AT+CGNSSINFO |
| send_sms() | Envía SMS con AT+CMGS |
| dial() | Hace una llamada con ATD+numero; |
| hang_up() | Cuelga con AT+CHUP |
| http_post() | Envía JSON al servidor con AT+HTTPACTION |
| get_rtc() | Lee la hora de la SIM con AT+CCLK? |
| check_signal() | Lee la señal GSM con AT+CSQ |
| check_sim() | Verifica si hay SIM con AT+CIMI |
| print_status() | Imprime resumen completo del estado |

### El WDT (watchdog)

Es un temporizador de 30 segundos. Si el código no lo "alimenta" con `_feed()` antes de que venza, la ESP32 se reinicia automáticamente. Protege contra cuelgues infinitos.

Cada operación larga llama `self._feed()` antes y después para evitar el reset.

### Secuencia de arranque — prepare()

Cuando la ESP32 arranca, `prepare()` ejecuta estos comandos AT en orden:

1. `AT` — verificar comunicación con el chip
2. `ATE0` — desactivar eco
3. `AT+CFUN=0` / `AT+CFUN=1` — reset funcional del módem
4. `AT+CNMP=2` — modo de red automático
5. `AT+CGNSSPWR=0` — apagar GPS temporalmente
6. `AT+CREG?` — verificar registro en red
7. `AT+CGATT=1` — adjuntar a red de datos
8. `AT+COPS?` — detectar operador y APN automáticamente
9. `AT+CGDCONT=1,"IP","apn"` — configurar contexto de datos
10. `AT+CGACT=1,1` — activar contexto de datos
11. `AT+CDNSCFG` — configurar DNS de Google
12. `AT+CGNSSPWR=1` — encender GPS
13. `AT+CGPSHOT` — modo GPS continuo

---

## 4. Las entradas — inputs.py

Maneja dos pines físicos:

- **Reed switch (GPIO 0)** — detecta si el imán está presente. HIGH = imán retirado = emergencia
- **Botón colgar (GPIO 1)** — LOW = botón presionado = colgar llamada

### Interrupciones (IRQ)

Usa interrupciones para detectar cambios sin bloquear el loop principal:

```python
pin_reed.irq(trigger=IRQ_RISING,   handler=_irq_call)  # imán se retira
pin_hangup.irq(trigger=IRQ_FALLING, handler=_irq_hang) # botón presionado
```

Cuando ocurre el evento, activa un flag (`call_request = True`). El loop principal lee ese flag y actúa.

### Debounce

El debounce evita lecturas falsas por vibración mecánica del switch. Si dos eventos llegan en menos de 200ms, el segundo se ignora.

---

## 5. La máquina de estados — main.py loop()

El corazón de la lógica. El sistema tiene 3 estados:

```
IDLE (0)      → esperando, gabinete cerrado
ALERTING (1)  → emergencia activa, llamando
ANSWERED (2)  → alguien contestó, parar llamadas
```

### Diagrama de transiciones

```
                    imán retirado
IDLE (0) ─────────────────────────────► ALERTING (1)
  ▲                                          │
  │ imán regresa                             │ alguien contesta
  │ (cualquier estado)                       ▼
  └────────────────────────────────── ANSWERED (2)
```

### Lógica en estado ALERTING

El loop hace 3 cosas en cada iteración:

1. **SMS** — si no se han enviado todavía, los manda a todos los números (solo una vez por emergencia)
2. **Llamada** — cada 30 segundos llama al siguiente número de la lista en rotación circular
3. **Detecta respuesta** — escucha el UART por `VOICE CALL: BEGIN` para saber si contestaron

Si detecta `NO CARRIER`, `BUSY`, o `NO ANSWER`, inmediatamente llama al siguiente número sin esperar.

---

## 6. Los SMS — emergency.py

`build_sms()` construye dos mensajes separados porque el texto completo supera el límite de 160 caracteres de GSM7.

### SMS 1 — Identificación

```
EMERGENCIA DEA
El DEA-001 fue retirado del gabinete.
Fecha: 2025-06-21 10:30:00
```

### SMS 2 — Ubicación

```
Ubicacion DEA-001:
Lat: 6.123456
Lon: -75.654321
Precision: ~10 metros
maps.google.com/?q=6.123456,-75.654321
Se presume emergencia medica.
```

Si no hay fix GPS válido, el SMS 2 dice:
```
Ubicacion DEA-001:
GPS sin fix disponible.
Se presume emergencia medica.
```

---

## 7. El GPS — gps_utils.py

El chip A7670SA tiene GPS integrado. Responde al comando `AT+CGNSSINFO` con una línea de datos:

```
+CGNSSINFO: 2,8,1.2,1.5,1.8,6.200000,N,75.600000,W,210625,123456.00,1560,0.5,180
```

`parse_cgnssinfo()` extrae de ahí:

| Campo | Descripción |
|-------|-------------|
| fix_mode | 0=sin fix, 1=2D, 2=3D |
| hdop | Precisión horizontal (número menor = mejor) |
| latitude | Latitud decimal |
| longitude | Longitud decimal |
| date_str | Fecha DDMMYY |
| time_str | Hora HHMMSS |
| speed | Velocidad en km/h |

### Conversión HDOP a metros

`hdop_to_meters()` convierte el HDOP a metros aproximados:

```
metros = HDOP × 5
```

Ejemplos:
- HDOP 1.0 → ~5 metros (excelente)
- HDOP 2.0 → ~10 metros (bueno)
- HDOP 5.0 → ~25 metros (moderado)
- HDOP 10.0 → ~50 metros (pobre)

---

## 8. El tracking — tracker.py

Cada 10 segundos el loop llama a `send_position()` que:

1. Verifica que las coordenadas no sean 0,0 (sin fix)
2. Obtiene el IMEI del dispositivo
3. Construye un JSON manualmente
4. Lo envía por HTTP POST al servidor

### JSON enviado al servidor

```json
{
  "latitude": 6.2000000,
  "longitude": -75.6000000,
  "date": "2025-06-21 12:34:56",
  "imei": "123456789012345",
  "accuracy_m": 6,
  "speed": 0.00
}
```

### ¿Por qué JSON manual?

MicroPython tiene el módulo `json` pero se evita para ahorrar RAM y flash en el ESP32-C3. En vez de `json.dumps()` se construye el string directamente.

---

## 9. El log — call_log.py

Escribe cada evento en `/call_log.txt` en la flash de la ESP32. El archivo sobrevive reinicios porque está en la memoria flash, no en RAM.

### Eventos registrados

| Evento | Cuándo se registra |
|--------|-------------------|
| BOOT | Cada vez que arranca el dispositivo |
| EMERGENCY | Cuando se retira el imán |
| SMS_SENT | Cuando se envía un SMS exitosamente |
| CALL | Cuando se marca un número |
| ANSWERED | Cuando alguien contesta |
| HANGUP | Cuando se cuelga la llamada |
| CANCELLED | Cuando el imán regresa (emergencia cancelada) |
| GPS_TIMEOUT | 30 minutos sin GPS válido |

### Formato de cada línea

```
2025-06-21 10:30:00 | CALL       |   6.123456 |  -75.654321 | +573043659495
2025-06-21 10:35:00 | HANGUP     |   0.000000 |    0.000000 |
2025-06-21 00:00:00 | BOOT       |   0.000000 |    0.000000 |
```

### Rotación automática

Cuando el log supera 200 entradas, elimina automáticamente la mitad más antigua para no llenar la flash.

### Comandos útiles desde el REPL

```python
# Leer el log
from call_log import print_log
print_log()

# Borrar el log
from call_log import clear_log
clear_log()
```

---

## 10. El flujo completo de una emergencia

```
Paso 1  → Alguien retira el DEA del gabinete
Paso 2  → El imán se aleja del reed switch → GPIO 0 pasa a HIGH
Paso 3  → loop() detecta reed_ausente == True con state == IDLE
Paso 4  → state = ALERTING, registra EMERGENCY en log
Paso 5  → build_sms() construye los 2 mensajes con GPS y fecha
Paso 6  → send_sms() envía los 2 mensajes a todos los números
Paso 7  → registra SMS_SENT en log
Paso 8  → dial() llama al primer número, registra CALL en log
Paso 9  → Cada 30 seg, si no contestan, llama al siguiente número
Paso 10 → Paralelamente, cada 10 seg envía GPS al servidor HTTP
Paso 11 → Si alguien contesta → state = ANSWERED, para las llamadas
Paso 12 → Si cierran el gabinete → state = IDLE, hang_up(), registra CANCELLED
Paso 13 → Si 30 min sin GPS → registra GPS_TIMEOUT y reinicia
```

---

## 11. Comandos de mantenimiento

### Subir archivos al dispositivo

```bash
# Verificar puerto
py -m mpremote connect list

# Subir un archivo
mpremote connect COM29 cp .\config.py :config.py

# Ver archivos en el dispositivo
mpremote connect COM29 ls

# Abrir REPL (logs en vivo)
mpremote connect COM29 repl
# Salir: Ctrl+X
```

### Flashear firmware desde cero

```bash
# 1. Borrar flash
py -m esptool --chip esp32c3 --port COM29 erase_flash

# 2. Flashear MicroPython
py -m esptool --chip esp32c3 --port COM29 --baud 460800 write_flash -z 0x0 LOLIN_C3_MINI-v1.28.0.bin
```

### Debug GPS simulado

En `config.py` cambiar:
```python
USE_FAKE_GPS = True
```
Simula coordenadas de Medellín sin necesidad de antena GPS ni señal.

---

*Documentación generada para DEA-001 — ESP32-C3 Super Mini + SIM A7670SA*
*MicroPython v1.28.0*
