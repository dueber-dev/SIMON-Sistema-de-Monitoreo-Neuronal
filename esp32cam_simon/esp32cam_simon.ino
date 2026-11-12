/*
 * ============================================================================
 * SIMON — Transmisor de Fotos e Inspección Local (ESP32-CAM + OV3660)
 * ============================================================================
 * Arquitectura de arranque:
 * 1. Inicialización limpia con memset(0) para evitar campos con basura (Core 2.x y 3.x).
 * 2. Prueba de perfiles de cámara escalonados (UXGA-Init -> VGA, y fallback 10MHz).
 * 3. Identificación precisa del sensor (PID: OV3660, OV2640, etc.).
 * 4. WiFiMulti (Casa / U) con AP fallback autónomo ("SIMON_CAM" en 192.168.4.1).
 * 5. Servidor Web local en puerto 80 ("/" y "/capture").
 * 6. Subida periódica a Cloudflare Worker cada 5 min (POST /simon/api/foto).
 * ============================================================================
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <WiFiMulti.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "esp_http_server.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "secrets.h"

// ================= CONFIGURACIÓN GENERAL =================
const unsigned long INTERVALO_FOTOS_MS = 15000; // 15 segundos (modo prueba rápida)
#define CAM_AP_SSID "SIMON_CAM"
#define CAM_AP_PASS ""  // Red abierta para fácil acceso en campo

// Pines AI-Thinker ESP32-CAM
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// Variables de estado
unsigned long ultimaFotoMs = 0;
bool modoAP = false;
bool camaraOK = false;
const char* perfilActivo = "Ninguno";
WiFiClientSecure clienteSeguro;
WiFiMulti wifiMulti;
httpd_handle_t servidorHTTP = NULL;

// ===============================================================
// 1. DIAGNÓSTICO DEL SISTEMA
// ===============================================================
void imprimirDiagnosticoSistema() {
  Serial.println("\n=======================================================");
  Serial.println("              DIAGNÓSTICO DEL SISTEMA                  ");
  Serial.println("=======================================================");
  Serial.printf("ESP-IDF:           %s\n", esp_get_idf_version());
#ifdef ESP_ARDUINO_VERSION_MAJOR
  Serial.printf("Arduino Core:      v%d.%d.%d\n", 
    ESP_ARDUINO_VERSION_MAJOR, ESP_ARDUINO_VERSION_MINOR, ESP_ARDUINO_VERSION_PATCH);
#else
  Serial.println("Arduino Core:      v1.x o no definido");
#endif
  Serial.printf("Modelo Chip:       %s Rev %d (%d núcleos)\n", 
    ESP.getChipModel(), ESP.getChipRevision(), ESP.getChipCores());
  Serial.printf("Frecuencia CPU:    %d MHz\n", ESP.getCpuFreqMHz());
  Serial.printf("Heap libre:        %u bytes\n", ESP.getFreeHeap());
  
  bool psram = psramFound();
  Serial.printf("PSRAM presente:    %s\n", psram ? "SÍ ✅" : "NO ❌");
  if (psram) {
    Serial.printf("PSRAM Total:       %u KB\n", ESP.getPsramSize() / 1024);
    Serial.printf("PSRAM Libre:       %u KB\n", ESP.getFreePsram() / 1024);
  }
  Serial.println("=======================================================\n");
}

// ===============================================================
// 2. DRENADO DE BÚFERES DMA (Evita frames viejos/corruptos)
// ===============================================================
void vaciarBuffersDMA(int cantidad) {
  for (int i = 0; i < cantidad; i++) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb) {
      esp_camera_fb_return(fb);
      delay(50);
    }
  }
}

// ===============================================================
// 3. INICIALIZACIÓN DE CÁMARA CON PERFILES ANTI FB-OVF
// ===============================================================
struct PerfilCamara {
  const char* nombre;
  int xclk_hz;
  framesize_t tamano_init;
  framesize_t tamano_operacion;
  int jpeg_quality;
  int fb_count;
  camera_grab_mode_t grab_mode;
};

// NOTA CLAVE: Inicializar en UXGA reserva búfer suficiente en PSRAM.
// Luego s->set_framesize(s, VGA) escala el sensor y NUNCA desborda el DMA.
const PerfilCamara PERFILES[] = {
  {
    .nombre = "Perfil 1: 20MHz UXGA-Init -> VGA (Estándar Óptimo)",
    .xclk_hz = 20000000,
    .tamano_init = FRAMESIZE_UXGA,
    .tamano_operacion = FRAMESIZE_VGA,
    .jpeg_quality = 12,
    .fb_count = 2,
    .grab_mode = CAMERA_GRAB_LATEST
  },
  {
    .nombre = "Perfil 2: 10MHz UXGA-Init -> VGA (Reloj Conservador)",
    .xclk_hz = 10000000,
    .tamano_init = FRAMESIZE_UXGA,
    .tamano_operacion = FRAMESIZE_VGA,
    .jpeg_quality = 14,
    .fb_count = 2,
    .grab_mode = CAMERA_GRAB_LATEST
  },
  {
    .nombre = "Perfil 3: 10MHz VGA Directo (Bajo Consumo)",
    .xclk_hz = 10000000,
    .tamano_init = FRAMESIZE_VGA,
    .tamano_operacion = FRAMESIZE_VGA,
    .jpeg_quality = 16,
    .fb_count = 1,
    .grab_mode = CAMERA_GRAB_WHEN_EMPTY
  }
};

bool probarPerfil(int indicePerfil) {
  const PerfilCamara &p = PERFILES[indicePerfil];
  Serial.printf("\n>>> Intentando: %s <<<\n", p.nombre);
  
  camera_config_t config;
  memset(&config, 0, sizeof(camera_config_t)); // ¡CRÍTICO! Limpia basura de memoria

  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;

  config.xclk_freq_hz = p.xclk_hz;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = p.tamano_init;
  config.jpeg_quality = p.jpeg_quality;
  config.fb_count     = p.fb_count;
  config.grab_mode    = p.grab_mode;
  config.fb_location  = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("❌ esp_camera_init falló con código de error: 0x%x\n", err);
    return false;
  }

  sensor_t *s = esp_camera_sensor_get();
  if (!s) {
    Serial.println("❌ No se pudo obtener el puntero del sensor (sensor_t == NULL)");
    esp_camera_deinit();
    return false;
  }

  // Identificación del sensor por PID
  Serial.printf("Sensor detectado con PID: 0x%04X -> ", s->id.PID);
  if (s->id.PID == OV3660_PID) {
    Serial.println("OmniVision OV3660 (3 MP) ✅");
    s->set_vflip(s, 1);       // Corregir orientación habitual
    s->set_brightness(s, 1);  // Calibración ligera para panel exterior
    s->set_saturation(s, 0);
  } else if (s->id.PID == OV2640_PID) {
    Serial.println("OmniVision OV2640 (2 MP)");
    s->set_vflip(s, 1);
  } else {
    Serial.println("Sensor desconocido o no estándar");
  }

  // Si se inicializó en UXGA, cambiar a la resolución final de operación (VGA)
  if (p.tamano_init != p.tamano_operacion) {
    Serial.println("Ajustando resolución de operación a VGA (640x480)...");
    s->set_framesize(s, p.tamano_operacion);
    delay(200);
  }

  // Drenar cuadros iniciales que puedan tener ruido o sincronización incompleta
  vaciarBuffersDMA(3);
  delay(300);

  // Probar 3 capturas reales
  Serial.println("Validando captura de cuadros de prueba:");
  int capturasExitosas = 0;
  for (int i = 1; i <= 3; i++) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb && fb->len > 0) {
      Serial.printf("  ✓ Cuadro %d: %u bytes, resolución %dx%d (Formato JPEG OK)\n", 
                    i, fb->len, fb->width, fb->height);
      esp_camera_fb_return(fb);
      capturasExitosas++;
    } else {
      Serial.printf("  ✗ Cuadro %d: Fallo (puntero nulo o longitud 0)\n", i);
    }
    delay(250);
  }

  if (capturasExitosas >= 2) {
    Serial.println("✅ ¡Perfil validado y estable!");
    perfilActivo = p.nombre;
    return true;
  } else {
    Serial.println("⚠️ Perfil inestable. Desinicializando para probar siguiente opción...");
    esp_camera_deinit();
    delay(500);
    return false;
  }
}

void configurarCamara() {
  const int totalPerfiles = sizeof(PERFILES) / sizeof(PERFILES[0]);
  for (int i = 0; i < totalPerfiles; i++) {
    if (probarPerfil(i)) {
      camaraOK = true;
      return;
    }
  }
  camaraOK = false;
  Serial.println("\n❌❌ NINGÚN PERFIL DE CÁMARA LOGRÓ CAPTURAR ❌❌");
}

// ===============================================================
// 4. CAPTURA SEGURA DE CUADRO (CON REINTENTOS)
// ===============================================================
camera_fb_t* obtenerFotoFresca() {
  if (!camaraOK) return NULL;
  
  // Drenar cualquier cuadro viejo en cola
  vaciarBuffersDMA(1);
  delay(100);

  camera_fb_t *fb = NULL;
  for (int i = 0; i < 4; i++) {
    fb = esp_camera_fb_get();
    if (fb && fb->len > 0) return fb;
    delay(200);
  }
  return NULL;
}

// ===============================================================
// 5. SERVIDOR WEB LOCAL (PUERTO 80)
// ===============================================================
esp_err_t capture_handler(httpd_req_t *req) {
  camera_fb_t *fb = obtenerFotoFresca();
  if (!fb) {
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }
  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Cache-Control", "no-cache, no-store, must-revalidate");
  esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
  return res;
}

esp_err_t index_handler(httpd_req_t *req) {
  const char* html = 
    "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<title>SIMON - Inspección Solar</title><style>"
    "body{background:#121212;color:#eee;text-align:center;font-family:sans-serif;margin:0;padding:16px;}"
    "h2{margin:8px 0;font-size:20px;color:#ff9800;}"
    ".wrap{max-width:540px;margin:0 auto;background:#1e1e1e;padding:16px;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,0.6);}"
    "img{width:100%;height:auto;border-radius:8px;display:block;margin:12px auto;background:#000;min-height:220px;}"
    "button{background:#ff9800;border:none;color:#fff;font-weight:bold;padding:12px 24px;font-size:15px;border-radius:6px;cursor:pointer;margin:8px;}"
    "button:active{transform:scale(0.97);}"
    "a{color:#4fc3f7;text-decoration:none;display:inline-block;margin-top:12px;font-size:14px;}"
    "</style></head><body>"
    "<div class='wrap'>"
    "<h2>☀️ SIMON · ESP32-CAM</h2>"
    "<p style='color:#bbb;font-size:13px;margin:4px 0;'>Inspección visual del panel solar (soporte a 50°)</p>"
    "<img id='foto' src='/capture' alt='Cargando imagen...'>"
    "<button onclick=\"document.getElementById('foto').src='/capture?t='+Date.now()\">🔄 Actualizar foto</button><br>"
    "<a href='https://dueber.dev/simon' target='_blank'>Abrir Dashboard en la Nube ↗</a>"
    "</div></body></html>";
  httpd_resp_set_type(req, "text/html");
  return httpd_resp_send(req, html, strlen(html));
}

void iniciarServidorWeb() {
  if (servidorHTTP != NULL) return;
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 80;
  if (httpd_start(&servidorHTTP, &config) == ESP_OK) {
    httpd_uri_t index_uri = { .uri = "/", .method = HTTP_GET, .handler = index_handler, .user_ctx = NULL };
    httpd_uri_t cap_uri   = { .uri = "/capture", .method = HTTP_GET, .handler = capture_handler, .user_ctx = NULL };
    httpd_register_uri_handler(servidorHTTP, &index_uri);
    httpd_register_uri_handler(servidorHTTP, &cap_uri);
    Serial.println("🌐 Servidor web local activo en el puerto 80.");
  }
}

// ===============================================================
// 6. GESTIÓN WI-FI (Casa / Universidad / AP Fallback)
// ===============================================================
void conectarRed() {
  Serial.println("\n-------------------------------------------");
  Serial.println("Buscando red Wi-Fi configurada...");
  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);

  // Reducir ligeramente la potencia máxima de TX para mitigar picos bruscos de corriente
  // que ocasionan caídas de tensión (brownout/reset). 17 dBm sigue teniendo excelente cobertura.
  WiFi.setTxPower(WIFI_POWER_17dBm);

  wifiMulti.addAP(WIFI_SSID_CASA, WIFI_PASS_CASA);
  wifiMulti.addAP(WIFI_SSID_U, WIFI_PASS_U);

  unsigned long t0 = millis();
  int segundos = 0;
  while (wifiMulti.run() != WL_CONNECTED && (millis() - t0 < 12000)) {
    delay(1000);
    segundos++;
    Serial.printf("  Conectando Wi-Fi... (%d s)\n", segundos);
  }

  if (WiFi.status() == WL_CONNECTED) {
    modoAP = false;
    Serial.println("\n=======================================================");
    Serial.printf("✅ ¡CONECTADO A INTERNET!: %s\n", WiFi.SSID().c_str());
    Serial.printf("IP Asignada: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("👉 VISOR LOCAL: http://%s\n", WiFi.localIP().toString().c_str());
    Serial.println("=======================================================\n");
  } else {
    modoAP = true;
    WiFi.disconnect(true);
    WiFi.mode(WIFI_AP);
    IPAddress ipLocal(192, 168, 4, 1);
    IPAddress gateway(192, 168, 4, 1);
    IPAddress subnet(255, 255, 255, 0);
    WiFi.softAPConfig(ipLocal, gateway, subnet);
    WiFi.softAP(CAM_AP_SSID, CAM_AP_PASS);
    Serial.println("\n=======================================================");
    Serial.println("📡 MODO AUTÓNOMO ACTIVADO (Sin Wi-Fi de Casa ni U)");
    Serial.printf("Red Wi-Fi creada:  %s\n", CAM_AP_SSID);
    Serial.println("👉 VISOR LOCAL:     http://192.168.4.1");
    Serial.println("=======================================================\n");
  }
  iniciarServidorWeb();
}

// ===============================================================
// 7. SUBIDA A LA NUBE (Cloudflare Worker)
// ===============================================================
void capturarYSubirNube() {
  if (WiFi.status() != WL_CONNECTED || !camaraOK) return;

  Serial.println("\n[NUBE] Capturando foto para transmitir a dueber.dev...");
  camera_fb_t *fb = obtenerFotoFresca();
  if (!fb) {
    Serial.println("❌ [NUBE] Error: no se pudo obtener cuadro de la cámara");
    return;
  }

  Serial.printf("✓ [NUBE] Foto lista: %u bytes. Conectando al endpoint...\n", fb->len);

  // Pequeña pausa para permitir que el carril de 3.3V se recupere del DMA antes del burst de radio Wi-Fi
  delay(80);

  bool esHttps = String(API_FOTO_URL).startsWith("https://");
  HTTPClient http;
  http.setConnectTimeout(esHttps ? 15000 : 4000); // Para IP local 4s es suficiente
  http.setTimeout(esHttps ? 15000 : 5000);
  
  WiFiClient clientPlano;
  if (esHttps) {
    http.begin(clienteSeguro, API_FOTO_URL);
  } else {
    http.begin(clientPlano, API_FOTO_URL);
  }
  
  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("Authorization", String("Bearer ") + API_TOKEN);

  int codigo = http.POST(fb->buf, fb->len);
  if (codigo == 200) {
    Serial.println("✅ [NUBE] ¡Foto subida exitosamente con código HTTP 200!");
  } else {
    Serial.printf("⚠️ [NUBE] Respuesta del servidor: código HTTP %d\n", codigo);
    if (codigo < 0) {
      // Si hubo un microcorte o congestión en la red de la U, refrescar Wi-Fi
      Serial.println("  (Refrescando conexión Wi-Fi...)");
      wifiMulti.run();
    }
  }

  http.end();
  esp_camera_fb_return(fb);
}

// ===============================================================
// 8. SETUP Y LOOP
// ===============================================================
void setup() {
  // Deshabilitar detector brownout por software (permite sobrevivir caídas transitorias cortas)
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
  
  Serial.begin(115200);
  delay(1200);

  Serial.println("\n\n#######################################################");
  Serial.println("       SIMON · SISTEMA DE MONITOREO NEURONAL           ");
  Serial.println("           Módulo ESP32-CAM (OV3660)                   ");
  Serial.println("#######################################################");

  imprimirDiagnosticoSistema();
  clienteSeguro.setInsecure(); // Acepta TLS del worker
  clienteSeguro.setTimeout(15000); // 15 segundos para handshake SSL en redes lentas

  configurarCamara();
  conectarRed();

  if (WiFi.status() == WL_CONNECTED && camaraOK) {
    delay(1000);
    capturarYSubirNube();
    ultimaFotoMs = millis();
  }
}

void loop() {
  // Si está en modo AP autónomo, cada 30 segundos comprueba si reaparece el Wi-Fi
  if (modoAP) {
    static unsigned long ultimoCheck = 0;
    if (millis() - ultimoCheck >= 30000) {
      ultimoCheck = millis();
      if (wifiMulti.run() == WL_CONNECTED) {
        modoAP = false;
        Serial.printf("\nWi-Fi recuperado: http://%s\n", WiFi.localIP().toString().c_str());
      }
    }
    delay(100);
    return;
  }

  // En modo estación conectado:
  if (WiFi.status() == WL_CONNECTED) {
    if (millis() - ultimaFotoMs >= INTERVALO_FOTOS_MS) {
      capturarYSubirNube();
      ultimaFotoMs = millis(); // Cooldown inicia DESPUÉS de que termina la subida
    }
  } else {
    wifiMulti.run();
    delay(1000);
  }
}
