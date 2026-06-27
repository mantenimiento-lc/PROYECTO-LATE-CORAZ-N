# DEA-001 — Project Structure

## File Layout

```
Late Corazón/
├── main.py          # Entry point — setup() + while True: loop()
├── config.py        # All configuration constants (pins, numbers, URLs, timings)
├── sim_module.py    # SIMModule class — full AT driver (UART, GPS, HTTP, SMS, calls)
├── emergency.py     # Emergency logic — build_sms(), handle_call(), handle_hangup()
├── tracker.py       # HTTP tracking — build_json(), send_position()
├── inputs.py        # GPIO management — pin setup, IRQs, debounce, flag consumption
├── gps_utils.py     # GPS parsing — parse_cgnssinfo(), hdop_to_meters(), maps_link()
├── call_log.py      # Flash log — log_event(), read_log(), clear_log(), print_log()
└── README.md
```

## Architecture Pattern

**Flat module structure** — no packages, no subdirectories (MicroPython flash constraint).

- `main.py` is the orchestrator: it holds state variables and calls into other modules. It contains no business logic of its own.
- `config.py` is the single source of truth for all tuneable values. No magic numbers elsewhere.
- All hardware I/O is encapsulated in `SIMModule` (sim_module.py) and `inputs.py`. Other modules never touch `machine` or `uart` directly.
- Modules import from `config.py` and each other, but `main.py` is never imported by any module.

## State Machine (main.py)

```
IDLE (0) → ALERTING (1) → ANSWERED (2)
         ↖ (magnet returned, any state)
```

State is tracked via a plain integer constant, not a class.

## Code Style Conventions

- **Module header**: every file starts with a `# ===...===` banner comment with filename and one-line description.
- **Section dividers**: `# ── Section name ───` lines group related code within a file.
- **Docstrings**: every public function has a docstring. Args and return values documented inline when non-obvious.
- **Type hints**: used in function signatures where MicroPython supports them (basic types only).
- **Error handling**: `try/except Exception as e: print(...)` — exceptions are caught and printed, never silently swallowed or re-raised (device must keep running).
- **WDT discipline**: call `sim._feed()` before and after every UART operation or blocking wait to prevent hardware watchdog reset.
- **latin-1 decoding**: always use `decode("latin-1")` for UART bytes — never `utf-8`, which can throw on raw modem output.
- **No f-strings in hot paths**: prefer `.format()` to stay compatible with older MicroPython builds; f-strings are used in non-critical paths.
- **JSON by hand**: never `import json` — build JSON payloads via string concatenation.
- **Timestamps**: always obtained from `sim.get_rtc()` (SIM clock), not from `time.time()` (ESP32 has no RTC battery).

## Configuration Rules

- All tuneable values live exclusively in `config.py` — never hardcode pins, numbers, URLs, or intervals in other files.
- `PHONE_NUMBERS` is a list (supports duplicates; deduplication done at call site with `dict.fromkeys()`).
- `APN_MAP` maps MCC+MNC codes to APNs; `APN` is the fallback default.
- `USE_FAKE_GPS = True` enables offline testing without antenna or SIM.

## Flash / Memory Constraints

- Keep files small and self-contained — avoid large imports or circular dependencies.
- Log rotation is automatic at 200 entries (`call_log.py`), keeping the newest 50%.
- No external libraries — only MicroPython built-ins (`machine`, `time`, `math`, `random`).
