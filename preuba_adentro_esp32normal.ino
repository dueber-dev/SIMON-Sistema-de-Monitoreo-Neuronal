#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include "secrets.h"   // WIFI_SSID, WIFI_PASS, API_URL, API_TOKEN (copia secrets.example.h)

// --- INICIALIZAR SENSOR DIGITAL ---
Adafruit_INA219 ina219;
bool inaPresente = false;

// --- CONFIGURACIÓN WI-FI ---
// Primero intenta conectarse a WIFI_SSID para mandar los datos a la nube.
// Si no lo encuentra, crea su propia red como antes (modo local con el .bat).
const char* ssidLocal = "ESP32_Panel_Solar";
const char* passLocal = "";
const unsigned long ESPERA_WIFI_MS = 15000;
bool modoNube = false;
WiFiServer server(8080);
WiFiClient client;

// --- NUBE ---
const int LOTE = 5;          // se manda un POST cada 5 lecturas (5 s)
const int MAX_COLA = 60;     // si se cae internet, se guardan hasta 60 s de lecturas
struct Lectura { unsigned long seg; float v, i, p, t, luz; };
Lectura cola[MAX_COLA];
int nCola = 0;
String claveSesion;          // cada encendido es una sesión nueva en la nube
WiFiClientSecure clienteSeguro;

// --- PINES ANALÓGICOS RESTANTES ---
const int pinTemp = 33; // Pin central (OUT) del LM35
const int pinLDR  = 32; // Pin de la fotorresistencia

// --- FILTROS ---
const int MUESTRAS = 32;           // lecturas del ADC por cada dato
const int DESCARTE = 8;            // se tiran las 8 más bajas y las 8 más altas (quita los picos)
const float ZONA_MUERTA_mA = 0.1;  // ruido del INA219 con el panel a oscuras

unsigned long tiempoInicio = 0;
unsigned long proximaLectura = 0;

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

void iniciarWiFi() {
  Serial.print("Conectando a "); Serial.print(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < ESPERA_WIFI_MS) { delay(500); Serial.print("."); }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    modoNube = true;
    Serial.print("Modo NUBE. IP en la red: "); Serial.println(WiFi.localIP());
    Serial.println("Dashboard: https://dueber.dev/simon");
  } else {
    WiFi.disconnect(true);
    WiFi.mode(WIFI_AP);
    WiFi.softAP(ssidLocal, passLocal);
    Serial.print("Sin internet: modo LOCAL. Red "); Serial.print(ssidLocal);
    Serial.print(", IP: "); Serial.println(WiFi.softAPIP());
  }
}

// Manda las lecturas pendientes. Si falla, se quedan en la cola para el siguiente intento.
void enviarNube() {
  if (WiFi.status() != WL_CONNECTED) return;
  String json = "{\"clave\":\"" + claveSesion + "\",\"filas\":[";
  for (int k = 0; k < nCola; k++) {
    const Lectura& l = cola[k];
    if (k) json += ",";
    json += "[" + String(l.seg) + "," + String(l.v, 3) + "," + String(l.i, 2) + "," +
            String(l.p, 2) + "," + String(l.t, 1) + "," + String(l.luz, 1) + "]";
  }
  json += "]}";

  HTTPClient http;
  http.setTimeout(4000);
  http.begin(clienteSeguro, API_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + API_TOKEN);
  int codigo = http.POST(json);
  http.end();

  if (codigo == 200) {
    nCola = 0;
  } else {
    Serial.print("Error al enviar a la nube: "); Serial.println(codigo);
  }
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

  iniciarWiFi();
  server.begin();

  // El certificado no se valida: el Worker cambia de certificado y el ESP32 no tiene
  // dónde actualizarlo. El token protege la escritura.
  clienteSeguro.setInsecure();
  claveSesion = String(esp_random(), HEX) + String(esp_random(), HEX);
  tiempoInicio = millis();
}

void loop() {
  if (!client || !client.connected()) {
    client = server.available();
  }

  // Una lectura por segundo, contando el tiempo que tarda el envío a la nube
  if (millis() < proximaLectura) return;
  proximaLectura = millis() + 1000;

  unsigned long segundos = (millis() - tiempoInicio) / 1000;

  // --- 1. LECTURAS DEL INA219 (Voltaje, Corriente y Potencia) ---
  float v_panel = ina219.getBusVoltage_V();
  bool okV = ina219.success();
  float corriente_mA = ina219.getCurrent_mA();
  bool okI = ina219.success();
  // V x I en vez del registro de potencia: ese tiene pasos de 0.8 mW y bajo techo marca 0
  float potencia_mW = v_panel * corriente_mA;

  // Si la lectura I2C falló, la librería devuelve 0: no se manda un dato falso.
  if (!inaPresente || !okV || !okI) {
    Serial.println("Error: lectura I2C del INA219 fallida, se omite este dato.");
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
  // ENVÍO DE DATOS A PYTHON POR WI-FI (modo local)
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

  // ===================================================================
  // ENVÍO A LA NUBE (dashboard en dueber.dev/simon)
  // ===================================================================
  if (modoNube) {
    if (nCola == MAX_COLA) {   // cola llena: se pierde la lectura más vieja
      memmove(cola, cola + 1, sizeof(Lectura) * (MAX_COLA - 1));
      nCola--;
    }
    cola[nCola++] = { segundos, v_panel, corriente_mA, potencia_mW, temp_C, luz_pct };
    if (nCola >= LOTE) enviarNube();
  }
}
