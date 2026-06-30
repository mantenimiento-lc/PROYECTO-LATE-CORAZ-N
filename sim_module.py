# ============================================================
#  sim_module.py — Driver AT para el A7670SA
#  Maneja UART, comandos AT, GPS, HTTP, SMS y llamadas
# ============================================================

import time
import machine
from machine import WDT
from config import (
    SIM_TX_PIN, SIM_RX_PIN, SIM_BAUDRATE,
    APN, APN_MAP, DNS_PRIMARY, DNS_SECONDARY,
    OUT_GAIN, MIC_GAIN,
    TRACKING_URL,
    USE_FAKE_GPS, FAKE_LAT, FAKE_LON,
)


class SIMModule:
    """Interfaz completa con el módulo A7670SA vía comandos AT."""

    def __init__(self):
        self.uart = machine.UART(
            1,
            baudrate=SIM_BAUDRATE,
            tx=SIM_TX_PIN,
            rx=SIM_RX_PIN,
            bits=8,
            parity=None,
            stop=1,
            timeout=100,        # timeout de lectura por byte (ms)
            timeout_char=100,
        )
        self._imei_cache = None

        # WDT con 8 segundos — lo alimentamos en cada operación larga
        # Desactivar en debug poniendo wdt=False en config si es necesario
        try:
            self._wdt = WDT(timeout=30000)  # 30 seg — suficiente para HTTP
        except Exception:
            self._wdt = None

    def _feed(self):
        """Alimenta el watchdog para evitar reset por WDT."""
        if self._wdt:
            self._wdt.feed()

    # ----------------------------------------------------------
    # UART helpers
    # ----------------------------------------------------------

    def _flush_rx(self):
        """Vacía el buffer de recepción antes de enviar un comando."""
        while self.uart.any():
            self.uart.read(self.uart.any())
            time.sleep_ms(5)

    def _safe_decode(self, data: bytes) -> str:
        """Decodifica bytes del UART de forma segura, ignorando bytes invalidos."""
        result = []
        for b in data:
            if b < 128:
                result.append(chr(b))
            else:
                result.append('?')
        return ''.join(result)

    def _read_response(self, timeout_ms: int = 300) -> str:
        """
        Lee la respuesta del UART con timeout.
        Alimenta el WDT en cada iteración para evitar panic.
        """
        response = b""
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)

        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            self._feed()
            chunk = self.uart.read(64)
            if chunk:
                response += chunk
                # Salir temprano — buscar terminadores en bytes
                if b"OK\r\n" in response or b"ERROR" in response or b">" in response:
                    break
            else:
                time.sleep_ms(20)

        self._feed()
        return self._safe_decode(response)

    def send_at(self, command: str, timeout_ms: int = 1000) -> str:
        """Envía un comando AT, espera respuesta y la devuelve."""
        self._flush_rx()
        self.uart.write((command + "\r\n").encode())
        self._feed()
        resp = self._read_response(timeout_ms)
        return resp

    def write_raw(self, data: bytes):
        """Escribe bytes crudos al UART (usado para Ctrl+Z en SMS)."""
        self.uart.write(data)
        self._feed()

    def detect_apn(self) -> str:
        """
        Lee el código MCC+MNC del operador con AT+COPS y
        busca el APN correspondiente en APN_MAP.
        Si no encuentra coincidencia usa el APN por defecto.
        """
        resp = self.send_at("AT+COPS?", timeout_ms=3000)
        self._feed()
        apn = APN  # default

        try:
            # Respuesta: +COPS: 0,2,"732103",7
            if "+COPS:" in resp:
                idx   = resp.index("+COPS:")
                parts = resp[idx + 6:].strip().split(",")
                if len(parts) >= 3:
                    mccmnc = parts[2].replace('"', '').strip()
                    if mccmnc in APN_MAP:
                        apn = APN_MAP[mccmnc]
                        print("Operador detectado: {} -> APN: {}".format(mccmnc, apn))
                    else:
                        print("Operador {} no en tabla, usando APN default: {}".format(mccmnc, apn))
        except Exception as e:
            print("detect_apn error:", e)

        return apn

    # ----------------------------------------------------------
    # Inicialización del módulo
    # ----------------------------------------------------------

    def prepare(self):
        """Secuencia de arranque: red, datos, GPS."""
        print("Iniciando modulo A7670SA...")

        self._feed()
        self.send_at("AT",            timeout_ms=1000)   # verificar comunicacion
        self._feed()
        self.send_at("ATE0",          timeout_ms=1000)   # desactivar eco — clave para SMS
        self._feed()
        self.send_at("AT+CFUN=0",     timeout_ms=6000)
        self._feed()
        self.send_at("AT+CFUN=1",     timeout_ms=6000)
        self._feed()
        self.send_at("ATE0",          timeout_ms=1000)   # repetir tras reset funcional
        self._feed()
        self.send_at("AT+CNMP=2",     timeout_ms=5000)
        self._feed()
        self.send_at("AT+CGNSSPWR=0", timeout_ms=3000)
        self._feed()

        self.send_at("AT+CREG?",      timeout_ms=5000)
        self._feed()
        self.send_at("AT+CGATT=1",    timeout_ms=5000)
        self._feed()

        # Detectar APN automaticamente segun operador
        apn = self.detect_apn()

        self.send_at(f'AT+CGDCONT=1,"IP","{apn}"', timeout_ms=5000)
        self._feed()
        self.send_at("AT+CGACT=1,1",  timeout_ms=5000)
        self._feed()
        self.send_at(f'AT+CDNSCFG="{DNS_PRIMARY}","{DNS_SECONDARY}"', timeout_ms=2000)
        self._feed()
        self.send_at(f"AT+COUTGAIN={OUT_GAIN}", timeout_ms=1000)
        self.send_at(f"AT+CMICGAIN={MIC_GAIN}", timeout_ms=1000)
        self._feed()

        # Encender GPS
        self.send_at("AT+CGNSSPWR=1", timeout_ms=3000)
        self._feed()
        self.send_at("AT+CGPSHOT",    timeout_ms=3000)
        self._feed()

        print("Modulo listo.")

    def configure_sms(self):
        """Configura modo texto para SMS."""
        self.send_at("AT+CMGF=1", timeout_ms=1000)
        self._feed()

    # ----------------------------------------------------------
    # Diagnóstico de red y SIM
    # ----------------------------------------------------------

    def check_sim(self) -> str:
        """
        Verifica si hay SIM insertada.
        Retorna: "OK", "NO_SIM", "ERROR"
        """
        resp = self.send_at("AT+CIMI", timeout_ms=2000)
        self._feed()
        if "ERROR" in resp:
            return "NO_SIM"
        # CIMI devuelve el IMSI (15 dígitos) si hay SIM
        for line in resp.splitlines():
            line = line.strip()
            if line.isdigit() and len(line) >= 10:
                return "OK"
        return "NO_SIM"

    def check_signal(self) -> dict:
        """
        Lee la señal GSM con AT+CSQ.
        Retorna dict con:
            rssi    : valor crudo (0-31, 99=sin señal)
            dbm     : dBm aproximado (-113 a -51)
            percent : porcentaje de señal (0-100)
            label   : texto descriptivo
            ok      : bool
        """
        resp = self.send_at("AT+CSQ", timeout_ms=2000)
        self._feed()

        result = {"rssi": 99, "dbm": -999, "percent": 0, "label": "Sin señal", "ok": False}

        try:
            if "+CSQ:" not in resp:
                return result

            idx   = resp.index("+CSQ:")
            parts = resp[idx + 5:].strip().split(",")
            rssi  = int(parts[0].strip())

            if rssi == 99:
                result["label"] = "Sin señal / Sin SIM"
                return result

            # Conversión RSSI → dBm: dBm = -113 + (rssi * 2)
            dbm     = -113 + (rssi * 2)
            percent = min(100, int((rssi / 31) * 100))

            if rssi >= 20:
                label = "Excelente"
            elif rssi >= 15:
                label = "Buena"
            elif rssi >= 10:
                label = "Moderada"
            elif rssi >= 5:
                label = "Debil"
            else:
                label = "Muy debil"

            result = {
                "rssi":    rssi,
                "dbm":     dbm,
                "percent": percent,
                "label":   label,
                "ok":      True,
            }

        except Exception as e:
            print("check_signal error:", e)

        return result

    def check_registration(self) -> str:
        """
        Verifica el registro en red GSM con AT+CREG?.
        Retorna: "REGISTRADO", "BUSCANDO", "DENEGADO", "ROAMING", "DESCONOCIDO"
        """
        resp = self.send_at("AT+CREG?", timeout_ms=2000)
        self._feed()

        try:
            idx   = resp.index("+CREG:")
            parts = resp[idx + 6:].strip().split(",")
            # Puede ser ",<stat>" o "<n>,<stat>"
            stat = int(parts[-1].strip().split("\r")[0])

            return {
                0: "NO_REGISTRADO",
                1: "REGISTRADO",
                2: "BUSCANDO",
                3: "DENEGADO",
                4: "DESCONOCIDO",
                5: "ROAMING",
            }.get(stat, "DESCONOCIDO")

        except Exception:
            return "DESCONOCIDO"

    def print_status(self):
        """
        Imprime en consola un resumen completo del estado del módulo:
        SIM, señal, registro de red y temperatura.
        Útil al arrancar y para debug.
        """
        # Alimentar WDT antes de empezar — prepare() puede haberlo dejado cerca del limite
        self._feed()
        print("")
        print("=" * 40)
        print("  ESTADO DEL MODULO A7670SA")
        print("=" * 40)

        # SIM
        sim_status = self.check_sim()
        self._feed()
        if sim_status == "OK":
            print("  SIM     : INSERTADA OK")
        else:
            print("  SIM     : NO DETECTADA *** verificar SIM ***")

        # Señal
        sig = self.check_signal()
        self._feed()
        if sig["ok"]:
            print("  SEÑAL   : {} ({} dBm, {}%, RSSI={})".format(
                sig["label"], sig["dbm"], sig["percent"], sig["rssi"]))
        else:
            print("  SEÑAL   : {} — sin cobertura o sin SIM".format(sig["label"]))

        # Registro
        reg = self.check_registration()
        self._feed()
        reg_icons = {
            "REGISTRADO":    "OK — red local",
            "ROAMING":       "OK — roaming",
            "BUSCANDO":      "Buscando red...",
            "DENEGADO":      "DENEGADO *** verificar plan ***",
            "NO_REGISTRADO": "No registrado",
            "DESCONOCIDO":   "Estado desconocido",
        }
        print("  RED     : {}".format(reg_icons.get(reg, reg)))

        # Temperatura
        temp = self.get_temperature()
        self._feed()
        print("  TEMP    : {} °C".format(temp))

        # IMEI
        imei = self.get_imei()
        self._feed()
        print("  IMEI    : {}".format(imei))

        print("=" * 40)
        print("")

    # ----------------------------------------------------------
    # GPS
    # ----------------------------------------------------------

    def get_gps(self) -> dict:
        """
        Retorna dict completo con latitude, longitude, hdop,
        accuracy_m, timedate, speed, valid.
        Delega el parseo a gps_utils.parse_cgnssinfo.
        """
        from gps_utils import parse_cgnssinfo

        if USE_FAKE_GPS:
            import random
            return {
                "latitude":   FAKE_LAT + random.uniform(-0.001, 0.001),
                "longitude":  FAKE_LON + random.uniform(-0.001, 0.001),
                "hdop":       1.2,
                "accuracy_m": 6,
                "timedate":   "2025-10-02 12:34:56",
                "speed":      0.0,
                "valid":      True,
            }

        resp = self.send_at("AT+CGNSSINFO", timeout_ms=500)
        self._feed()
        return parse_cgnssinfo(resp)

    # ----------------------------------------------------------
    # IMEI
    # ----------------------------------------------------------

    def get_imei(self) -> str:
        """Lee el IMEI (con caché para no repetir AT en cada ciclo)."""
        if self._imei_cache:
            return self._imei_cache

        resp = self.send_at("AT+CGSN", timeout_ms=1000)
        self._feed()

        for line in resp.splitlines():
            line = line.strip()
            if line.isdigit() and len(line) == 15:
                self._imei_cache = line
                return line
        return "000000000000000"

    # ----------------------------------------------------------
    # RTC / Hora de la SIM
    # ----------------------------------------------------------

    def get_rtc(self) -> str:
        """Devuelve fecha/hora desde la SIM ajustada a Colombia (UTC-5)."""
        resp = self.send_at("AT+CCLK?", timeout_ms=1000)
        self._feed()

        try:
            idx   = resp.index("+CCLK: ")
            start = resp.index('"', idx) + 1
            end   = resp.index('"', start)
            dt    = resp[start:end]

            year   = int("20" + dt[0:2])
            month  = int(dt[3:5])
            day    = int(dt[6:8])
            hour   = int(dt[9:11])
            minute = int(dt[12:14])
            second = int(dt[15:17])

            # Ajustar a UTC-5 (Colombia)
            hour -= 5
            if hour < 0:
                hour += 24
                day  -= 1
                if day < 1:
                    # Retroceder mes
                    month -= 1
                    if month < 1:
                        month = 12
                        year -= 1
                    # Dias del mes anterior (simplificado)
                    days = [0,31,28,31,30,31,30,31,31,30,31,30,31]
                    day = days[month]

            return "{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                year, month, day, hour, minute, second)
        except Exception:
            return "N/A"

    # ----------------------------------------------------------
    # Temperatura del módulo
    # ----------------------------------------------------------

    def get_temperature(self) -> str:
        resp = self.send_at("AT+CPMUTEMP", timeout_ms=1000)
        self._feed()
        try:
            idx  = resp.index("+CPMUTEMP:")
            temp = resp[idx + 10:].split("\r")[0].strip()
            return temp.replace("OK", "").strip()
        except Exception:
            return "N/A"

    # ----------------------------------------------------------
    # SMS
    # ----------------------------------------------------------

    def send_sms(self, phone_numbers: list, message: str):
        """Envía el mismo SMS a todos los números de la lista."""
        for number in phone_numbers:
            print("Enviando SMS a {}...".format(number))
            self._feed()
            self._flush_rx()

            # Verificar que el modulo este listo antes de enviar SMS
            # Reintentar AT hasta 5 veces con 1 seg de espera
            ready = False
            for _ in range(5):
                self._feed()
                resp = self.send_at("AT", timeout_ms=1000)
                if "OK" in resp:
                    ready = True
                    break
                time.sleep_ms(1000)

            if not ready:
                print("SMS ERROR: modulo no responde para {}".format(number))
                continue

            self._feed()
            self._flush_rx()
            time.sleep_ms(300)

            # Enviar AT+CMGS y esperar prompt ">"
            self.uart.write('AT+CMGS="{}"\r\n'.format(number).encode())
            self._feed()

            # Esperar ">" — max 5 seg
            buf = b""
            deadline = time.ticks_add(time.ticks_ms(), 5000)
            got_prompt = False
            while time.ticks_diff(deadline, time.ticks_ms()) > 0:
                self._feed()
                chunk = self.uart.read(32)
                if chunk:
                    buf += chunk
                    if b">" in buf:
                        got_prompt = True
                        break
                time.sleep_ms(50)

            if not got_prompt:
                print("SMS ERROR: sin prompt '>' para {}".format(number))
                self.uart.write(bytes([27]))  # ESC para cancelar
                time.sleep_ms(300)
                self._flush_rx()
                continue

            time.sleep_ms(150)
            self._feed()

            # Enviar texto en ASCII (GSM7) + Ctrl+Z
            self.uart.write(message.encode("ascii", "replace"))
            time.sleep_ms(50)
            self.uart.write(bytes([26]))  # Ctrl+Z
            self._feed()

            # Esperar +CMGS: — max 20 seg
            # El módulo puede ecoar el mensaje antes del +CMGS: — no limpiamos buffer
            confirm = b""
            deadline = time.ticks_add(time.ticks_ms(), 20000)
            sent_ok = False
            while time.ticks_diff(deadline, time.ticks_ms()) > 0:
                self._feed()
                chunk = self.uart.read(64)
                if chunk:
                    confirm += chunk
                    s = self._safe_decode(confirm)
                    if "+CMGS:" in s:
                        sent_ok = True
                        break
                    if "ERROR" in s and "+CMGS" not in s:
                        break
                time.sleep_ms(100)

            if sent_ok:
                print("SMS OK -> {}".format(number))
            else:
                raw = self._safe_decode(confirm).strip()
                # Solo mostrar las últimas 2 líneas para no mostrar el mensaje completo
                lines = [l.strip() for l in raw.splitlines() if l.strip()]
                print("SMS FALLO -> {} | {}".format(number, " | ".join(lines[-2:])))

            # Esperar 5 seg entre SMS para que el modulo se recupere y evitar filtro anti-spam
            time.sleep_ms(5000)
            self._feed()

    # ----------------------------------------------------------
    # Llamada
    # ----------------------------------------------------------

    def dial(self, number: str):
        """Realiza una llamada de voz."""
        print(f"Marcando {number}...")
        self.uart.write(f"ATD{number};\r".encode())
        self._feed()

    def hang_up(self):
        """Cuelga la llamada activa."""
        print("Colgando...")
        self.uart.write(b"AT+CHUP\r")
        self._feed()

    # ----------------------------------------------------------
    # HTTP POST
    # ----------------------------------------------------------

    def http_post(self, json_body: str, url: str = None) -> str:
        """POST JSON al endpoint indicado. Si no se pasa url usa TRACKING_URL."""
        target_url = url if url else TRACKING_URL
        self._feed()
        self.send_at("AT+HTTPTERM",  timeout_ms=500)
        self._feed()
        # Deshabilitar verificacion SSL — necesario para certificados de Render/onrender.com
        self.send_at("AT+HTTPSSL=1", timeout_ms=500)
        self._feed()
        self.send_at("AT+HTTPINIT",  timeout_ms=2000)
        self._feed()
        self.send_at('AT+HTTPPARA="CID",1',              timeout_ms=500)
        self._feed()
        self.send_at('AT+HTTPPARA="URL","' + target_url + '"', timeout_ms=1000)
        self._feed()
        self.send_at('AT+HTTPPARA="CONTENT","application/json"', timeout_ms=500)
        self._feed()

        body_len = len(json_body.encode())
        self.send_at(f"AT+HTTPDATA={body_len},5000", timeout_ms=2000)
        self._feed()
        time.sleep_ms(300)
        self._feed()

        self.uart.write(json_body.encode())
        self._feed()
        time.sleep_ms(500)
        self._feed()

        self.send_at("AT+HTTPACTION=1", timeout_ms=3000)
        self._feed()

        # Esperar respuesta del servidor — max 15 seg con WDT activo
        action_resp = b""
        deadline = time.ticks_add(time.ticks_ms(), 15000)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            self._feed()
            chunk = self.uart.read(64)
            if chunk:
                action_resp += chunk
                if b"+HTTPACTION" in action_resp:
                    break
            time.sleep_ms(100)
            self._feed()

        # Extraer código HTTP (ej: 200, 404)
        decoded = self._safe_decode(action_resp)
        http_code = "?"
        if "+HTTPACTION:" in decoded:
            try:
                parts = decoded.split("+HTTPACTION:")[1].strip().split(",")
                http_code = parts[1].strip()
            except Exception:
                pass

        self._feed()
        server_resp = self.send_at("AT+HTTPREAD", timeout_ms=3000)
        self._feed()

        # Solo mostrar si el servidor devuelve body con contenido útil
        body = server_resp.strip()
        for line in body.splitlines():
            line = line.strip()
            if line and line not in ("OK", "ERROR", "AT+HTTPREAD"):
                print("HTTP {} | {}".format(http_code, line))
                break
        else:
            print("HTTP {} | OK (sin body)".format(http_code))

        self.send_at("AT+HTTPTERM", timeout_ms=500)
        self._feed()

        return server_resp
