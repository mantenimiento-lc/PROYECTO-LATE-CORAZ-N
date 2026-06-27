# DEA Monitor — Dashboard de monitoreo remoto

Dashboard web para monitorear dispositivos DEA-001 en tiempo real.

## Deploy en Railway (gratis)

### 1. Instalar Railway CLI
```bash
npm install -g @railway/cli
railway login
```

### 2. Crear proyecto y hacer deploy
```bash
cd dashboard
railway init
railway up
```

### 3. Obtener la URL pública
Railway te da una URL tipo: `https://dea-monitor-xxxx.railway.app`

### 4. Actualizar el dispositivo
En `heartbeat.py` del dispositivo, reemplaza:
```python
MONITOR_URL = "https://TU-APP.railway.app/api/heartbeat"
```
Por tu URL real, por ejemplo:
```python
MONITOR_URL = "https://dea-monitor-xxxx.railway.app/api/heartbeat"
```

Luego sube el archivo al dispositivo:
```bash
py -m mpremote connect COM30 cp heartbeat.py :heartbeat.py
py -m mpremote connect COM30 cp Main.py :main.py
py -m mpremote connect COM30 cp sim_module.py :sim_module.py
```

## Correr localmente (para probar)

```bash
cd dashboard
pip install -r requirements.txt
python main.py
```

Abre http://localhost:8000 en el navegador.

## Endpoints disponibles

| Método | URL | Descripción |
|--------|-----|-------------|
| POST | /api/heartbeat | Recibe eventos del dispositivo |
| POST | /api/tracking  | Recibe posición GPS (compatible con tracker.py) |
| GET  | /api/devices   | Lista todos los dispositivos |
| GET  | /api/events    | Historial de eventos |
| GET  | /api/positions/{imei} | Historial GPS de un dispositivo |
| PUT  | /api/devices/{imei}   | Actualiza nombre y ubicación |

## Eventos que reporta el dispositivo

| Evento | Cuándo ocurre |
|--------|--------------|
| BOOT | Cada vez que el ESP32 arranca |
| HEARTBEAT | Cada 60 segundos (señal de vida) |
| EMERGENCY | Cuando se confirma emergencia (30 seg sin cancelar) |
| GPS_TIMEOUT | Sin fix GPS por 30 minutos |
| SMS_SENT | Al enviar SMS de emergencia |
| CALL | Al marcar un número |
| ANSWERED | Cuando contestan la llamada |
| CANCELLED | Cuando se cancela la alerta |
