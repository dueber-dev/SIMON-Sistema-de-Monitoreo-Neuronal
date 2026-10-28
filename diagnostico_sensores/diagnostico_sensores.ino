// Diagnóstico de sensores de SIMON
// Imprime las lecturas "crudas" de cada sensor para compararlas contra el multímetro.
// No recorta ni corrige nada: si un valor sale raro, aquí se ve tal cual.
//
// Qué comparar con el multímetro:
//   Vbus  -> voltaje entre VIN- del INA219 y GND
//   Vshunt-> voltaje entre VIN+ y VIN- (en mV; 100 mA dan 10 mV con el shunt de 0.1 ohm)
//   LM35  -> voltaje entre la pata Out del LM35 y GND (10 mV por grado)

#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_INA219.h>

// Ponlo en true para comparar el ruido del ADC con el Wi-Fi encendido
const bool CON_WIFI = false;

const int pinTemp = 33;
const int pinLDR  = 32;
const int MUESTRAS = 64;           // lecturas del ADC por cada línea
const float R_SHUNT_OHM = 0.1;     // shunt del módulo INA219 (R100)
const float R_CARGA_OHM = 30.0;    // R1 + R2 + R3 = 3 x 10 ohm

Adafruit_INA219 ina219;
bool inaPresente = false;

struct LecturaADC { float prom_mV; int min_mV; int max_mV; };

LecturaADC leerADC(int pin) {
  long suma = 0;
  int mn = 99999, mx = 0;
  for (int i = 0; i < MUESTRAS; i++) {
    int mv = analogReadMilliVolts(pin);   // usa la calibración de fábrica del ESP32
    suma += mv;
    if (mv < mn) mn = mv;
    if (mv > mx) mx = mv;
    delayMicroseconds(200);
  }
  return { suma / (float)MUESTRAS, mn, mx };
}

void escanearI2C() {
  Serial.println("Escaneando bus I2C...");
  int encontrados = 0;
  for (uint8_t dir = 1; dir < 127; dir++) {
    Wire.beginTransmission(dir);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  dispositivo en 0x%02X%s\n", dir, dir == 0x40 ? "  <- INA219" : "");
      encontrados++;
    }
  }
  if (encontrados == 0) Serial.println("  NADA. Revisa SDA (D21), SCL (D22), VCC y GND del INA219.");
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n--- DIAGNOSTICO DE SENSORES SIMON ---");

  Wire.begin(21, 22);
  escanearI2C();

  inaPresente = ina219.begin();
  if (inaPresente) {
    ina219.setCalibration_32V_1A();   // hasta 1 A, mejor resolución que el 32V_2A por defecto
    Serial.println("INA219 OK.");
  } else {
    Serial.println("INA219 NO responde: todo lo del INA219 saldrá inválido.");
  }

  analogSetPinAttenuation(pinTemp, ADC_6db);   // 150-1750 mV: cubre el LM35 hasta ~175 C
  analogSetPinAttenuation(pinLDR, ADC_11db);

  if (CON_WIFI) {
    WiFi.mode(WIFI_AP);
    WiFi.softAP("ESP32_Panel_Solar", "");
    Serial.println("Wi-Fi encendido (modo AP).");
  } else {
    WiFi.mode(WIFI_OFF);
    Serial.println("Wi-Fi apagado.");
  }

  Serial.println("Vbus[V] | Vshunt[mV] | I_ina[mA] | I_shunt[mA] | I_esperada[mA] | I2C | LM35 prom/min/max [mV] -> C | LDR [mV]");
}

void loop() {
  // --- INA219, sin recortar negativos ---
  float vbus = ina219.getBusVoltage_V();
  bool okBus = ina219.success();
  float vshunt = ina219.getShuntVoltage_mV();
  bool okShunt = ina219.success();
  float i_ina = ina219.getCurrent_mA();
  bool okI = ina219.success();

  float i_shunt = vshunt / R_SHUNT_OHM;          // ley de Ohm sobre el shunt
  float i_esperada = vbus / R_CARGA_OHM * 1000;  // lo que deberían pasar los 30 ohm
  bool okI2C = inaPresente && okBus && okShunt && okI;

  // --- LM35 y LDR ---
  LecturaADC t = leerADC(pinTemp);
  LecturaADC l = leerADC(pinLDR);
  float tempC = t.prom_mV / 10.0;

  Serial.printf("%6.3f | %8.2f | %8.2f | %8.2f | %8.1f | %s | %6.1f / %4d / %4d -> %5.1f C | %6.1f",
                vbus, vshunt, i_ina, i_shunt, i_esperada, okI2C ? "ok " : "ERR",
                t.prom_mV, t.min_mV, t.max_mV, tempC, l.prom_mV);

  // Avisos para no tener que interpretar cada número a mano
  if (!okI2C)                             Serial.print("  <- fallo de I2C: este Vbus no vale");
  if (i_ina < -1.0)                       Serial.print("  <- corriente NEGATIVA: VIN+ y VIN- invertidos");
  if (vbus > 1.0 && fabs(i_ina) < 1.0)    Serial.print("  <- hay voltaje pero no corriente: carga abierta");
  if (t.max_mV - t.min_mV > 50)           Serial.print("  <- LM35 ruidoso/oscilando (>5 C entre muestras)");
  if (t.max_mV > 1000)                    Serial.print("  <- pico >100 C: lectura imposible");
  Serial.println();

  delay(1000);
}
