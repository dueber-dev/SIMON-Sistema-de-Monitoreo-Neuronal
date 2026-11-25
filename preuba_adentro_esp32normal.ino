#include <WiFi.h>
#include <WiFiMulti.h>
#include <WiFiClientSecure.h>
#include <WiFiUdp.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "secrets.h"   // WIFI_SSID, WIFI_PASS, API_URL, API_TOKEN (copia secrets.example.h)

// --- INICIALIZAR SENSOR DIGITAL ---
Adafruit_INA219 ina219;
bool inaPresente = false;

// --- CONFIGURACIÓN WI-FI ---
// Intenta conectarse a las redes de secrets.h para mandar los datos a la nube.
// Si no hay ninguna al arrancar, levanta su propia red (modo local con el .bat)
// PERO sigue buscando las redes conocidas cada 20 s: nunca se rinde.
const char* ssidLocal = "ESP32_Panel_Solar";
const char* passLocal = "";
const unsigned long ESPERA_WIFI_MS = 20000;     // primer intento al encender
const unsigned long REINTENTO_WIFI_MS = 20000;  // cada cuánto reintenta si no hay red
const unsigned long SIN_ENVIO_REINICIO_MS = 5UL * 60UL * 1000UL; // 5 min sin enviar -> reinicio
bool modoNube = false;
unsigned long ultimoIntentoWiFi = 0;
unsigned long ultimoEnvioOk = 0;
WiFiMulti wifiMulti;

// LED azul de la placa: estado sin necesidad del monitor serie.
//   fijo = conectado | se apaga un instante = la nube recibió datos
//   parpadeo lento = buscando Wi-Fi | parpadeo rápido = no responde el INA219
const int pinLED = 2;

// --- ANTI-APAGADO DE LA POWERBANK ---
// Muchas powerbanks se apagan solas si el consumo baja de ~50-100 mA. Con la red propia
// encendida (AP) la placa nunca se apagaba, así que ahora el AP queda siempre activo y
// además se mandan ráfagas cortas de paquetes por esa red local: cada ráfaga enciende el
// transmisor (~200 mA) y la powerbank ve consumo todo el tiempo.
const bool ANTI_APAGADO = true;
const unsigned long RAFAGA_CADA_MS = 1000;
const int PAQUETES_POR_RAFAGA = 25;
// Opcional (hardware): transistor + resistencia de carga en este pin, se activa 1 s cada 10 s.
// Si no hay nada conectado, no pasa nada.
const int pinCarga = 25;
WiFiUDP udpCarga;
WiFiServer server(8080);
WiFiClient client;

// --- NUBE ---
const int LOTE = 5;          // se manda un POST cada 5 lecturas (5 s)
const int MAX_COLA = 300;    // si se cae internet, se guardan hasta 5 min de lecturas
const int MAX_POR_POST = 30; // al reconectar, la cola se vacía en trozos de 30
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

void avisarConexion() {
  Serial.print("Modo NUBE. Red: "); Serial.print(WiFi.SSID());
  Serial.print(", señal: "); Serial.print(WiFi.RSSI()); Serial.print(" dBm");
  Serial.print(", IP: "); Serial.println(WiFi.localIP());
  Serial.println("Dashboard: https://dueber.dev/simon");
}

// Prueba todas las redes de secrets.h (casa y universidad) y se queda con la de mejor señal.
void iniciarWiFi() {
  WiFi.persistent(false);
  // AP + STA desde el inicio: la red local siempre existe (y mantiene despierta la powerbank)
  // mientras se buscan o se usan las redes conocidas.
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(ssidLocal, passLocal);
  WiFi.setTxPower(WIFI_POWER_19_5dBm);
  WiFi.setSleep(false);          // sin ahorro de energía: conexión más estable y la powerbank
                                 // ve un consumo constante (muchas se apagan si el consumo es bajo)
  WiFi.setAutoReconnect(true);
  wifiMulti.addAP(WIFI_SSID, WIFI_PASS);
#ifdef WIFI_SSID_U
  if (strlen(WIFI_SSID_U) > 0) wifiMulti.addAP(WIFI_SSID_U, WIFI_PASS_U);
#endif
  Serial.print("Buscando redes conocidas");
  unsigned long t0 = millis();
  while (wifiMulti.run() != WL_CONNECTED && millis() - t0 < ESPERA_WIFI_MS) {
    digitalWrite(pinLED, !digitalRead(pinLED));
    delay(500); Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    modoNube = true;
    avisarConexion();
  } else {
    Serial.print("Sin internet por ahora: modo LOCAL. Red "); Serial.print(ssidLocal);
    Serial.print(", IP: "); Serial.println(WiFi.softAPIP());
    Serial.println("Se seguirá buscando la red conocida cada 20 s.");
  }
  ultimoIntentoWiFi = millis();
}

// En cada vuelta del loop: si se perdió la red (o nunca se tuvo), reintenta.
void vigilarWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!modoNube) { modoNube = true; avisarConexion(); }
    return;
  }
  if (modoNube) { modoNube = false; Serial.println("Se perdió el Wi-Fi, reintentando..."); }
  if (millis() - ultimoIntentoWiFi < REINTENTO_WIFI_MS) return;
  ultimoIntentoWiFi = millis();
  Serial.println("Buscando redes conocidas...");
  if (wifiMulti.run(8000) == WL_CONNECTED) { modoNube = true; avisarConexion(); }
}

// Manda las lecturas pendientes. Si falla, se quedan en la cola para el siguiente intento.
void enviarNube() {
  if (WiFi.status() != WL_CONNECTED || nCola == 0) return;
  int n = nCola < MAX_POR_POST ? nCola : MAX_POR_POST;
  String json = "{\"clave\":\"" + claveSesion + "\",\"filas\":[";
  for (int k = 0; k < n; k++) {
    const Lectura& l = cola[k];
    if (k) json += ",";
    json += "[" + String(l.seg) + "," + String(l.v, 3) + "," + String(l.i, 2) + "," +
            String(l.p, 2) + "," + String(l.t, 1) + "," + String(l.luz, 1) + "]";
  }
  json += "]}";

  HTTPClient http;
  http.setTimeout(4000);

  // Soporta tanto HTTPS (nube real dueber.dev) como HTTP (local en laptop)
  WiFiClient clientPlano;
  if (String(API_URL).startsWith("https://")) {
    http.begin(clienteSeguro, API_URL);
  } else {
    http.begin(clientPlano, API_URL);
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + API_TOKEN);
  int codigo = http.POST(json);
  http.end();

  if (codigo == 200) {
    nCola -= n;
    if (nCola > 0) memmove(cola, cola + n, sizeof(Lectura) * nCola);
    ultimoEnvioOk = millis();
    digitalWrite(pinLED, LOW);   // parpadeo corto: la nube recibió los datos
    delay(80);
    digitalWrite(pinLED, HIGH);
  } else {
    Serial.print("Error al enviar a la nube: "); Serial.println(codigo);
  }
}

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); // Evita apagados por caídas de voltaje con Power Bank o USB
  Serial.begin(115200);
  pinMode(pinLED, OUTPUT);
  pinMode(pinCarga, OUTPUT);
  digitalWrite(pinCarga, LOW);
  digitalWrite(pinLED, LOW);
  delay(500);   // con powerbank el voltaje tarda un poco en estabilizarse (y el INA219 también)
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
  ultimoEnvioOk = millis();
}

// Mantiene la powerbank encendida: ráfaga de paquetes por la red local + pulso en pinCarga.
void mantenerPowerbank() {
  if (!ANTI_APAGADO) return;
  static unsigned long ultimaRafaga = 0;
  if (millis() - ultimaRafaga >= RAFAGA_CADA_MS) {
    ultimaRafaga = millis();
    IPAddress bcast = WiFi.softAPIP();
    bcast[3] = 255;
    for (int k = 0; k < PAQUETES_POR_RAFAGA; k++) {
      udpCarga.beginPacket(bcast, 9999);
      udpCarga.print("SIMON keep-alive");
      udpCarga.endPacket();
    }
  }
  digitalWrite(pinCarga, (millis() % 10000) < 1000 ? HIGH : LOW);
}

// LED: fijo si hay red, parpadeo lento si la busca, rápido si falta el INA219.
void actualizarLED() {
  static unsigned long ultimo = 0;
  unsigned long periodo = !inaPresente ? 100 : (modoNube ? 0 : 500);
  if (periodo == 0) { digitalWrite(pinLED, HIGH); return; }
  if (millis() - ultimo >= periodo) { ultimo = millis(); digitalWrite(pinLED, !digitalRead(pinLED)); }
}

void loop() {
  if (!client || !client.connected()) {
    client = server.available();
  }

  vigilarWiFi();
  actualizarLED();
  mantenerPowerbank();

  // Red de seguridad: si pasan 5 min sin que la nube reciba nada (Wi-Fi colgado, DHCP,
  // TLS trabado), se reinicia la placa. No aplica si hay una laptop leyendo en modo local.
  bool laptopLocal = client && client.connected();
  if (laptopLocal) ultimoEnvioOk = millis();
  if (millis() - ultimoEnvioOk > SIN_ENVIO_REINICIO_MS) {
    Serial.println("5 min sin enviar a la nube: reiniciando...");
    delay(200);
    ESP.restart();
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

  // Si el INA219 no respondió al encender (pasa con powerbank), se vuelve a intentar.
  if (!inaPresente) {
    inaPresente = ina219.begin();
    if (inaPresente) { ina219.setCalibration_32V_1A(); Serial.println("INA219 detectado."); }
  }

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
  // Se encola siempre: si todavía no hay red, se manda apenas conecte.
  {
    if (nCola == MAX_COLA) {   // cola llena: se pierde la lectura más vieja
      memmove(cola, cola + 1, sizeof(Lectura) * (MAX_COLA - 1));
      nCola--;
    }
    cola[nCola++] = { segundos, v_panel, corriente_mA, potencia_mW, temp_C, luz_pct };
    if (modoNube && nCola >= LOTE) enviarNube();
  }
}
