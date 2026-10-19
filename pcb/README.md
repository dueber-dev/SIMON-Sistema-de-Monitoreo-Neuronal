# PCB de SIMON (una cara, para planchado)

Placa de 88 × 50 mm, todo THT, cobre solo en la capa **Bottom**. Las piezas van por arriba.
En Fusion está como `SIMON` en *Default Project*.

| Archivo | Qué es |
|---|---|
| `generar_brd.py` | Fuente del diseño: huellas, posiciones y pistas. Genera `SIMON.brd` |
| `verificar.py` | Chequeo propio de conectividad y separaciones |
| `render.py` | Genera los PDF 1:1 y la vista previa |
| `SIMON.brd` | Placa para EAGLE/Fusion (se sube a Fusion tal cual) |
| `SIMON_cobre_1a1.pdf` | Lo que se imprime para planchar |
| `SIMON_montaje.pdf` | Guía de qué va en cada lugar |

Para cambiar algo: editar `generar_brd.py` y correr `python generar_brd.py && python verificar.py && python render.py`.

## Conexiones (de la hoja "Conexiones SIMON PCB")

| Red | Une |
|---|---|
| 3V3 | ESP32 3V3 · INA219 VCC · LM35 pin 1 · LDR |
| GND | ESP32 GND (los dos) · INA219 GND · LM35 pin 3 · 10 kΩ · C1 − · panel − · fin de las resistencias de carga |
| VIN | ESP32 VIN · C1 + |
| SDA / SCL | D21 / D22 ↔ INA219 |
| TEMP | D33 ↔ LM35 pin 2 |
| LUZ | D32 ↔ LDR ↔ 10 kΩ |
| VSOLAR | panel + ↔ INA219 VIN+ |
| VCARGA | INA219 VIN− → 3 × 10 Ω en serie → GND |

Cambio respecto a la hoja: el **negativo del panel va a GND**. Sin eso el INA219 no puede medir
el voltaje del panel (lo mide respecto a GND).

## Antes de planchar

1. **Imprimir en papel normal** al 100 % y comprobar que la regla mide 50 mm.
2. Poner encima el ESP32, el módulo INA219 y la bornera: los pines deben caer en los pads.
   - ESP32: DOIT DevKit V1 de **30 pines**, filas a 25.4 mm, antena hacia arriba.
   - INA219: header de 6 pines en orden **VCC, GND, SCL, SDA, VIN−, VIN+** (tipo Adafruit) y el
     cuerpo del módulo hacia la derecha. Si el de ustedes trae otro orden, avisen antes de quemar.
3. Las resistencias de 10 Ω llevan la corriente del panel: con 6 V disipan ~0.4 W cada una,
   así que mejor de **1/2 W o 1 W**. Los pads están a 15.24 mm para que quepan.

## Imprimir para transferencia de tóner

- Impresora **láser**, en papel transfer/couché, solo negro.
- Capa inferior → se imprime **SIN espejo** (vista desde arriba). Ya viene así en `SIMON_cobre_1a1.pdf`;
  el texto "SIMON v1" se ve al revés en el papel y queda derecho en el cobre.
- Desde Fusion: *Print* con solo las capas 16 Bottom, 17 Pads y 20 Dimension; escala 1, color negro,
  relleno sólido y **Mirror desactivado**.
- Los pads tienen un punto blanco al centro para guiar la broca (0.8–1.0 mm; 1.3 mm para la bornera).

Reglas usadas: pistas de 1.0 mm (señales), 1.2 mm (3V3) y 1.5 mm (potencia/GND); separación mínima
de 0.74 mm (entre pines vecinos de los headers) y cobre a ≥ 1.15 mm del borde.
Al cortar la placa conviene dejar 2–3 mm de margen fuera del contorno.
