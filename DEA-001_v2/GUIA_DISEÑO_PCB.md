# DEA-001 v2 — Guía de diseño PCB
## Para KiCad 8 — PCB 50mm × 80mm — 2 capas

---

## Diagrama de bloques

```
                    USB-C (J1)
                       │
                    [IP2312/TP4056] ──── CHRG LED (DL1)
                       │
                    [BT1: 18650]
                       │
              D1 (protección polaridad)
                       │
                  VBAT_RAW
                       │
            [SW2 latching + Q4 AO3407] ◄── J9 boton ON/OFF externo
                       │
                 ─────VBAT─────────────────────────────────
                 │              │                │
           [XL6009]        [Q3 MOSFET]      [AMS1117-3.3]
           Boost 9V         corte 3.3V         3.3V
                 │              │                │
           VOUT_9V          VBAT_SIM           3V3
                 │              │                │
                 └──────────[A7670SA]         [ESP32-C3] ◄── SW1 RESET (PCB + J8 externo)
                            │     │            │
                         GPS ANT  GSM ANT   GPIO20(RX)
                         (J2)    (J3)       GPIO21(TX)
                                            GPIO0 ← Reed SW (J5)
                            │               GPIO1 ← Boton colgar (J6)
                         SPK+/SPK-
                            │
                         [PAM8403]
                            │
                         SPK 8Ω (J4)
```

---

## Botones — RESET y ON/OFF

### SW1 — Botón RESET (doble acceso)

```
3V3 ──── R_pullup (10k) ──── EN (ESP32-C3)
                                   │
                               C12 (100nF)
                                   │
                                  GND
                                   │
                              SW1 (en PCB)
                                   │
                              J8 (conector externo)
```

- SW1 es un pulsador SMD 6mm soldado en la PCB — visible y accesible
- J8 es un conector 2 pines para un botón externo montado en el gabinete
- Ambos van en paralelo — cualquiera de los dos hace el reset
- C12 de 100nF evita rebotes y falsas activaciones por ruido
- Al presionar: pin EN del ESP32 va a GND → reset inmediato
- Solo reinicia el ESP32, el A7670SA sigue activo

### SW2 — Botón ON/OFF (corte total con MOSFET P-channel)

```
VBAT_RAW ──── Q4 (AO3407 P-MOS) ──── VBAT (al sistema)
                    │
                   GATE
                    │
              R15 (10k) ──── J9 / SW2_latching
                    │
              R14 (100k) ──── VBAT_RAW  ← pull-up apaga Q4
```

**Cómo funciona:**
- Con SW2 **abierto**: R14 mantiene el gate de Q4 a VBAT → Q4 apagado → sistema sin alimentación
- Con SW2 **cerrado** (latching): gate de Q4 va a GND → Q4 conduce → VBAT fluye al sistema
- El botón latching mantiene el estado — un click enciende, otro apaga
- El corte es **total**: apaga ESP32, A7670SA, audio, todo

**Componente recomendado para SW2 externo:**
- Botón latching metálico 16mm o 19mm (tipo industrial) para montaje en panel del gabinete
- Corriente: el AO3407 soporta hasta 4A continuo — suficiente para todo el sistema

## Dimensiones PCB

- **Ancho:** 50mm
- **Alto:** 80mm
- **Capas:** 2 (Top copper + Bottom copper)
- **Grosor PCB:** 1.6mm estándar
- **Acabado:** HASL o ENIG
- **Solder mask:** Verde (color Late Corazón)
- **Silkscreen:** Blanco

---

## Zonas de ubicación de componentes

```
┌──────────────────────────────────────┐  80mm
│  [J1 USB-C]    [J7 USB ESP32]        │
│  [SW1 RESET ← visible en PCB]        │
│  [J8 conector reset externo]         │
│                                      │
│  [BT1 18650 HOLDER]                  │
│  ────────────────────                │
│                                      │
│  [U1 TP4056]  [U6 XL6009]           │
│  [U7 AMS1117] [Q3 MOSFET]           │
│  [Q4 AO3407]  [D1 Schottky]         │
│  [R14][R15]   [C10 4700uF]          │
│  [J9 conector ON/OFF externo]        │
│                                      │
│  [U2 ESP32-C3]    [U4 A7670SA]      │
│                   [SIM1]            │
│                   [J2 GPS ANT]      │
│                   [J3 GSM ANT]      │
│                                      │
│  [U3 PAM8403]     [J4 SPK]          │
│  [J5 Reed]  [J6 Boton colgar]       │
│  [DL1][DL2][DL3]                    │
└──────────────────────────────────────┘
       50mm
```

---

## Reglas de ruteo por red

### Redes de potencia alta (pista 0.8mm mínimo)
- `VBAT` — batería a XL6009, TP4056, A7670SA
- `VOUT_9V` — salida boost a A7670SA
- `GND` principal

### Redes de potencia media (pista 0.5mm)
- `3V3` — AMS1117 a ESP32, LEDs
- `5V` — USB a TP4056

### Redes de señal (pista 0.25mm)
- `UART_TX`, `UART_RX` — ESP32 a A7670SA
- `GPIO0`, `GPIO1` — reed switch y botón
- `SPK_P`, `SPK_N` — A7670SA a PAM8403
- `MIC_P`, `MIC_N` — micrófono a A7670SA

### Redes de audio (pista 0.3mm, separadas de digitales)
- Trazar SPK+/SPK- como par diferencial
- Mantener alejadas de UART y VOUT_9V

---

## Reglas críticas de diseño

### C10 — Condensador 4700μF (MUY IMPORTANTE)
El A7670SA consume hasta **2A en picos** durante transmisión GSM.
- Ubicar C10 lo más cerca posible de los pines VBAT del A7670SA
- Pistas VBAT al A7670SA deben ser de **mínimo 1.2mm** de ancho
- Agregar vías de 0.8mm cada 5mm en pistas VBAT largas

### Separación antenas
- Zona GPS: mantener libre de pistas de cobre en 5mm alrededor del conector U.FL
- Zona GSM: igual tratamiento
- No rutear pistas digitales debajo del módulo A7670SA

### Plano de tierra
- Usar flood fill de GND en capa Bottom completa
- Conectar a GND con vías cada 10mm
- El plano de GND mejora el rendimiento de RF del A7670SA

### Inductor L1 (XL6009)
- Ubicar L1 adyacente al IC XL6009
- No rutear pistas sensibles cerca del inductor (campo magnético)
- El nodo SW del XL6009 es ruidoso — mantener pista corta y gruesa (1mm)

### UART ESP32 → A7670SA
- R7 y R8 (100Ω) deben estar en serie lo más cerca posible del ESP32
- Mantener pistas UART alejadas de SPK y MIC

---

## Condensadores de desacoplamiento

Colocar cada condensador a máximo 2mm del pin VCC/VDD del IC correspondiente:

| IC | Cap | Ubicación |
|----|-----|-----------|
| A7670SA VBAT | C6 + C7 (100nF c/u) + C10 (4700μF) | Justo en los pads VBAT |
| ESP32-C3 3V3 | C5 (100nF) | Pin 3V3 del ESP32 |
| AMS1117 salida | C3 (10nF) | Pin VOUT |
| PAM8403 VDD | C4 (100nF) | Pin VDD |
| XL6009 entrada | C1 (22nF) | Pin VIN |
| XL6009 salida | C2 (22nF) | Pin VOUT |

---

## Pasos para completar en KiCad

1. **Abrir** `DEA-001_v2.kicad_pro` en KiCad 8
2. **Esquemático**: revisar y completar conexiones en `DEA-001_v2.kicad_sch`
3. **Asignar footprints**: usar la BOM como referencia (`BOM_DEA-001_v2.csv`)
4. **Ejecutar ERC** (Electrical Rules Check) y corregir errores
5. **Actualizar PCB desde esquemático**: `Tools → Update PCB from Schematic`
6. **Definir board outline**: rectángulo 50mm × 80mm en capa Edge.Cuts
7. **Ubicar componentes** según el diagrama de zonas de esta guía
8. **Rutear** siguiendo las reglas de ancho de pista definidas arriba
9. **Flood fill GND** en capa Bottom
10. **Ejecutar DRC** (Design Rules Check) hasta cero errores
11. **Generar Gerbers** para fabricación: `File → Fabrication Outputs → Gerbers`

---

## Fabricación recomendada

- **JLCPCB** o **PCBWay** — ambas aceptan diseños KiCad directamente
- Especificar: 2 capas, 1.6mm, HASL, color verde, silkscreen blanco
- Pedir mínimo 5 unidades para pruebas

---

## Notas de mejora vs versión anterior

| Problema v1 | Solución v2 |
|-------------|-------------|
| Cables volantes A7670SA | Footprint soldado directo en PCB |
| XL6009 módulo externo suelto | IC XL6009 SMD integrado en PCB |
| Condensadores 4700μF externos | Condensador SMD/THT en PCB |
| Error serigrafía VIN/GND | Corregido con marcas claras |
| ESP32 sobre conector poco confiable | Footprint castellated soldado |
| Sin protección polaridad batería | Diodo D1 Schottky en serie |
| Sin corte por bajo voltaje | Q3 MOSFET + DZ1 Zener 3.3V |
| Cables audio ruido | Pistas diferenciales en PCB |
| Sin boton reset accesible | SW1 en PCB + J8 conector externo |
| Sin boton ON/OFF | SW2 latching + Q4 AO3407 corte total VBAT |
