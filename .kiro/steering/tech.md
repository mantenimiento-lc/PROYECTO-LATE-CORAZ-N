# DEA-001 — Tech Stack

## Runtime & Language

- **MicroPython** v1.23+ for ESP32-C3
- Python syntax, but constrained to MicroPython's stdlib subset
- No `json` module used — JSON is built manually via string concatenation (flash/RAM constraints)
- No `asyncio` — single-threaded blocking loop with `time.sleep_ms()`

## Hardware Interface

- **UART**: `machine.UART(1, tx=21, rx=20, baudrate=115200)` → SIM A7670SA
- **GPIO**: `machine.Pin` with `PULL_UP` for reed switch and hangup button
- **WDT**: `machine.WDT(timeout=30000)` — 30s hardware watchdog, fed via `sim._feed()` throughout long operations
- **Flash storage**: Files written directly with `open()` to the ESP32's internal filesystem

## Cellular Module (A7670SA)

- Controlled entirely via **AT commands** over UART
- Key command sets used: network registration (`AT+CREG`), data (`AT+CGDCONT`, `AT+CGACT`), SMS text mode (`AT+CMGF`), GPS (`AT+CGNSSPWR`, `AT+CGNSSINFO`), HTTP (`AT+HTTPINIT/ACTION/READ`), voice (`ATD`, `AT+CHUP`)
- All AT responses decoded with `latin-1` (never raises `UnicodeError` on raw bytes)
- Response parsing uses `str.index()` + manual splitting — no regex

## Dependencies

No external packages. Everything uses MicroPython built-ins:
- `machine`, `time`, `math`, `random` (fake GPS only)

## Tooling

| Tool | Purpose |
|------|---------|
| `esptool` | Flash/erase firmware onto ESP32-C3 |
| `mpremote` | Upload files to the device, access REPL |

## Common Commands

```bash
# Install tools
py -m pip install esptool mpremote

# Erase flash (use before first flash)
py -m esptool --chip esp32c3 --port COM6 erase_flash

# Flash MicroPython firmware
py -m esptool --chip esp32c3 --port COM6 --baud 460800 write_flash -z 0x0 esp32c3-xxxx.bin

# Upload a single file
py -m mpremote connect COM6 cp config.py :config.py

# Upload all project files
py -m mpremote connect COM6 cp config.py :config.py
py -m mpremote connect COM6 cp sim_module.py :sim_module.py
py -m mpremote connect COM6 cp emergency.py :emergency.py
py -m mpremote connect COM6 cp tracker.py :tracker.py
py -m mpremote connect COM6 cp inputs.py :inputs.py
py -m mpremote connect COM6 cp gps_utils.py :gps_utils.py
py -m mpremote connect COM6 cp call_log.py :call_log.py
py -m mpremote connect COM6 cp main.py :main.py

# Open REPL (live logs)
py -m mpremote connect COM6 repl
# Exit REPL: Ctrl+X  |  Soft reset: Ctrl+D

# List available COM ports
py -m mpremote connect list
```

## Debug Utilities (from REPL)

```python
# Read event log
from call_log import print_log
print_log()

# Clear event log
from call_log import clear_log
clear_log()
```

## Debug GPS Mode

Set `USE_FAKE_GPS = True` in `config.py` to simulate Medellín coordinates without an antenna.
