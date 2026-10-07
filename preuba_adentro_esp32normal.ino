#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_INA219.h>

// --- INICIALIZAR SENSOR DIGITAL ---
Adafruit_INA219 ina219;

// --- CONFIGURACIÓN WI-FI ---
const char* ssid = "ESP32_Panel_Solar";
const char* password = ""; 
WiFiServer server(8080);
WiFiClient client;

// --- PINES ANALÓGICOS RESTANTES ---
const int pinTemp = 33; // Pin central (OUT) del LM35
const int pinLDR  = 32; // Pin de la fotorresistencia

unsigned long tiempoInicio = 0;

void setup() {
  Serial.begin(115200); 
  Serial.println("\n--- INICIANDO SISTEMA INA219 ---");
  
  // Iniciar INA219
  if (!ina219.begin()) {
    Serial.println("Error: No se detecta el módulo INA219. Revisa cables SDA y SCL.");
    while (1) { delay(10); } // Se detiene aquí si no encuentra el sensor
  }
  
  // Opcional: Configurar para mayor precisión en corrientes bajas (máx 1A)
  ina219.setCalibration_32V_1A();

  // Encender Wi-Fi
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
  float corriente_mA = ina219.getCurrent_mA();
  float potencia_mW = ina219.getPower_mW();
  float potencia_W = potencia_mW / 1000.0;

  // Filtro de ruido para oscuridad total (Cero absoluto)
  if (corriente_mA < 0.01) { 
    corriente_mA = 0.0; 
    potencia_mW = 0.0;
  }

  // --- 2. TEMPERATURA (LM35) ---
  int lecturaTemp = analogRead(pinTemp);
  float volts_temp = (lecturaTemp * 3.30) / 4095.0;
  float temp_C = volts_temp * 100.0; 

  // --- 3. LUZ (LDR) ---
  int lecturaL = analogRead(pinLDR);
  float luz_pct = (lecturaL / 4095.0) * 100.0;

  // ===================================================================
  // IMPRESIÓN EN EL MONITOR SERIE
  // ===================================================================
  Serial.println("-----------------------------------------");
  Serial.print(" Voltaje Panel   : "); Serial.print(v_panel, 3); Serial.println(" V");
  Serial.print(" Corriente Panel : "); Serial.print(corriente_mA, 2); Serial.println(" mA (Digital)");
  Serial.print(" Potencia        : "); Serial.print(potencia_mW, 2); Serial.println(" mW");
  Serial.print(" Temperatura     : "); Serial.print(temp_C, 1); Serial.println(" C");
  Serial.print(" Luz             : "); Serial.print(luz_pct, 1); Serial.println(" %");
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