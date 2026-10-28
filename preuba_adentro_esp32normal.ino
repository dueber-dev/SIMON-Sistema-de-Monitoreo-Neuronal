#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_INA219.h>

// --- INICIALIZAR SENSOR DIGITAL ---
Adafruit_INA219 ina219;
bool inaPresente = false;

// --- CONFIGURACIÓN WI-FI ---
const char* ssid = "ESP32_Panel_Solar";
const char* password = "";
WiFiServer server(8080);
WiFiClient client;

// --- PINES ANALÓGICOS RESTANTES ---
const int pinTemp = 33; // Pin central (OUT) del LM35
const int pinLDR  = 32; // Pin de la fotorresistencia

// --- FILTROS ---
const int MUESTRAS = 32;           // lecturas del ADC por cada dato
const int DESCARTE = 8;            // se tiran las 8 más bajas y las 8 más altas (quita los picos)
const float ZONA_MUERTA_mA = 0.1;  // ruido del INA219 con el panel a oscuras

unsigned long tiempoInicio = 0;

// Promedio recortado: ordena las muestras y promedia solo las del centro,
// así un pico aislado (los "180 C") no mueve el resultado.
float leerADC(int pin, bool enMilivolts) {
  int m[MUESTRAS];
  for (int i = 0; i < MUESTRAS; i++) {
    m[i] = enMilivolts ? analogReadMilliVolts(pin) : analogRead(pin);
    delayMicroseconds(200);
  }
  for (int i = 1; i < MUESTRAS; i++) {   // inserción: son pocas muestras
    int v = m[i], j = i - 1;
    while (j >= 0 && m[j] > v) { m[j + 1] = m[j]; j--; }
    m[j + 1] = v;
  }
  long suma = 0;
  for (int i = DESCARTE; i < MUESTRAS - DESCARTE; i++) suma += m[i];
  return suma / (float)(MUESTRAS - 2 * DESCARTE);
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n--- INICIANDO SISTEMA INA219 ---");

  // Iniciar INA219. Si no responde, el Wi-Fi arranca igual para poder depurar.
  inaPresente = ina219.begin();
  if (inaPresente) {
    // Mayor precisión en corrientes bajas (máx 1A)
    ina219.setCalibration_32V_1A();
  } else {
    Serial.println("Error: No se detecta el módulo INA219. Revisa cables SDA y SCL.");
  }

  // El ADC del ESP32 es poco exacto cerca de 0 V; con 6 dB el rango es 150-1750 mV
  // (LM35 hasta ~175 C) y analogReadMilliVolts aplica la calibración de fábrica.
  analogSetPinAttenuation(pinTemp, ADC_6db);
  analogSetPinAttenuation(pinLDR, ADC_11db);

  // Encender Wi-Fi
  WiFi.mode(WIFI_AP);
  WiFi.softAP(ssid, password);
  Serial.print("Red Wi-Fi Creada. Conéctate a la IP: ");
  Serial.println(WiFi.softAPIP());

  server.begin();
  tiempoInicio = millis();
}

void loop() {
  if (!client || !client.connected()) {
    client = server.available();
  }

  unsigned long segundos = (millis() - tiempoInicio) / 1000;

  // --- 1. LECTURAS DEL INA219 (Voltaje, Corriente y Potencia) ---
  float v_panel = ina219.getBusVoltage_V();
  bool okV = ina219.success();
  float corriente_mA = ina219.getCurrent_mA();
  bool okI = ina219.success();
  // V x I en vez del registro de potencia: ese tiene pasos de 0.8 mW y bajo techo marca 0
  float potencia_mW = v_panel * corriente_mA;
  bool okP = true;

  // Si la lectura I2C falló, la librería devuelve 0: no se manda un dato falso.
  if (!inaPresente || !okV || !okI || !okP) {
    Serial.println("Error: lectura I2C del INA219 fallida, se omite este dato.");
    delay(1000);
    return;
  }

  // Zona muerta simétrica: solo se anula el ruido. Una corriente negativa real se deja
  // pasar porque indica que VIN+ y VIN- están invertidos.
  if (fabs(corriente_mA) < ZONA_MUERTA_mA) {
    corriente_mA = 0.0;
    potencia_mW = 0.0;
  }

  // --- 2. TEMPERATURA (LM35, 10 mV por grado) ---
  float temp_C = leerADC(pinTemp, true) / 10.0;

  // --- 3. LUZ (LDR) ---
  float luz_pct = (leerADC(pinLDR, false) / 4095.0) * 100.0;

  // ===================================================================
  // IMPRESIÓN EN EL MONITOR SERIE
  // ===================================================================
  Serial.println("-----------------------------------------");
  Serial.print(" Voltaje Panel   : "); Serial.print(v_panel, 3); Serial.println(" V");
  Serial.print(" Corriente Panel : "); Serial.print(corriente_mA, 2); Serial.println(" mA (Digital)");
  Serial.print(" Potencia        : "); Serial.print(potencia_mW, 2); Serial.println(" mW");
  Serial.print(" Temperatura     : "); Serial.print(temp_C, 1); Serial.println(" C");
  Serial.print(" Luz             : "); Serial.print(luz_pct, 1); Serial.println(" %");
  if (corriente_mA < 0) Serial.println(" AVISO: corriente negativa, VIN+ y VIN- están invertidos");
  Serial.println("-----------------------------------------\n");

  // ===================================================================
  // ENVÍO DE DATOS A PYTHON POR WI-FI
  // ===================================================================
  // Nuevo Formato limpio: seg, v_panel, corriente, potencia, temp, luz
  String trama = String(segundos) + "," +
                 String(v_panel, 3) + "," +
                 String(corriente_mA, 2) + "," +
                 String(potencia_mW, 2) + "," +
                 String(temp_C, 1) + "," +
                 String(luz_pct, 1);

  if (client && client.connected()) {
    client.println(trama);
  }

  delay(1000);
}
