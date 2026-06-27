# DEA-001 — Product Overview

DEA-001 is an embedded emergency alert system for an AED (Automated External Defibrillator) cabinet, running **MicroPython on an ESP32-C3 Super Mini** paired with a **SIM A7670SA** cellular module.

## Core Function

When the cabinet magnet (reed switch) is removed — indicating the AED is being taken out for use — the device automatically:

1. Sends multi-part emergency SMS to up to 3 configured phone numbers, including GPS coordinates and a Google Maps link.
2. Dials the first emergency number and cycles through all numbers until answered.
3. Continuously tracks and POSTs GPS position to a remote server every 10 seconds.
4. Logs all events (BOOT, CALL, SMS_SENT, HANGUP, GPS_TIMEOUT, CANCELLED) to `/call_log.txt` in onboard flash.

## Target Hardware

- **MCU**: ESP32-C3 Super Mini
- **Cellular/GPS**: SIM A7670SA (via AT commands over UART)
- **Inputs**: Reed switch (GPIO 0), hangup button (GPIO 1)
- **Deployment**: Runs autonomously as a headless embedded device

## Operational Context

- Device is deployed in Colombia; phone numbers and APN defaults are Colombia-based (Claro, Tigo, Movistar).
- All user-facing strings (SMS, log messages, print statements) are in **Spanish**.
- System must be robust to GPS loss (auto-resets after 30 min without a valid fix).
- Flash storage is constrained — log file auto-rotates at 200 entries.
