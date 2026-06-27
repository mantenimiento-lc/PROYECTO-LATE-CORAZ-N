# ============================================================
#  call_log.py — Registro de llamadas en memoria flash
#  Guarda cada evento en /call_log.txt dentro del ESP32
# ============================================================

LOG_FILE = "/call_log.txt"
MAX_ENTRIES = 200   # máximo de líneas antes de rotar el archivo


def _count_lines() -> int:
    """Cuenta las líneas actuales del log."""
    try:
        with open(LOG_FILE, "r") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def _rotate():
    """
    Si el log supera MAX_ENTRIES, elimina la mitad más antigua
    para liberar espacio en flash.
    """
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()

        keep = lines[len(lines) // 2:]

        with open(LOG_FILE, "w") as f:
            for line in keep:
                f.write(line)

        print("call_log: rotacion aplicada, entradas conservadas:", len(keep))
    except OSError:
        pass


def log_event(event_type: str, timestamp: str, lat: float, lon: float, extra: str = ""):
    """
    Agrega una línea al log de llamadas.

    Formato de línea:
        2025-06-21 10:30:00 | CALL     | 6.123456 | -75.654321 | nota
        2025-06-21 10:35:00 | HANGUP   | 0.000000 |   0.000000 |
        2025-06-21 10:40:00 | SMS_SENT | 6.123456 | -75.654321 | +573043659495

    Args:
        event_type : "CALL", "HANGUP", "SMS_SENT", "BOOT", "GPS_TIMEOUT"
        timestamp  : string YYYY-MM-DD HH:MM:SS
        lat        : latitud float (0.0 si no aplica)
        lon        : longitud float (0.0 si no aplica)
        extra      : información adicional opcional
    """
    if _count_lines() >= MAX_ENTRIES:
        _rotate()

    line = "{} | {:10s} | {:10.6f} | {:11.6f} | {}\n".format(
        timestamp, event_type, lat, lon, extra
    )

    try:
        with open(LOG_FILE, "a") as f:
            f.write(line)
            f.flush()   # forzar escritura a flash inmediatamente
    except OSError as e:
        print("call_log ERROR escribiendo:", e)


def read_log() -> str:
    """Devuelve todo el contenido del log como string."""
    try:
        with open(LOG_FILE, "r") as f:
            return f.read()
    except OSError:
        return "(log vacio o no existe)"


def clear_log():
    """Borra completamente el archivo de log."""
    try:
        with open(LOG_FILE, "w") as f:
            f.write("")
        print("call_log: borrado.")
    except OSError as e:
        print("call_log ERROR borrando:", e)


def print_log():
    """Imprime el log en consola (util para debug via REPL)."""
    print("=" * 60)
    print("REGISTRO DE LLAMADAS — DEA-001")
    print("=" * 60)
    print(read_log())
    print("=" * 60)
