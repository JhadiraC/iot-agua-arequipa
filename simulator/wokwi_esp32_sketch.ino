/*
 * Wokwi ESP32 Sketch - Monitoreo IoT de Calidad del Agua (Arequipa, Perú)
 *
 * Simula un nodo ESP32 (Estación QAñas1 - Cuenca Chili, Quebrada Añashuayco)
 * enviando lecturas reales del dataset Rymes et al. (2024) vía HTTP POST
 * hacia el backend serverless en Google Cloud Run.
 *
 * Instrucciones en Wokwi (https://wokwi.com):
 *  1. Crea un proyecto "ESP32" (Arduino).
 *  2. Copia este sketch en sketch.ino.
 *  3. Reemplaza API_ENDPOINT con tu URL pública de Cloud Run y
 *     IOT_API_KEY con la clave configurada en Secret Manager.
 *  4. Inicia la simulación y observa el Serial Monitor (115200 baudios).
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>

// Red WiFi virtual de Wokwi
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";

// Configurar antes de ejecutar (NUNCA subir claves reales a GitHub)
const char* API_ENDPOINT = "https://YOUR-CLOUD-RUN-SERVICE.run.app/api/v1/telemetry";
const char* IOT_API_KEY  = "REPLACE_WITH_YOUR_IOT_API_KEY";

const unsigned long SEND_INTERVAL_MS = 10000; // 10 segundos entre lecturas

struct WaterSample {
  const char* sample_date;
  float water_temp_c;
  float ph;
  float dissolved_oxygen_mg_l;
  float electrical_conductivity_us_cm;
};

// Lecturas reales de la estación QAñas1 (Cuenca Chili) de data/processed/arequipa_sample_15_stations.csv
// Incluye lecturas normales y una lectura con pH > 8.5 (alerta)
const WaterSample SAMPLES[] = {
  {"2010-10-21", 21.50f, 8.34f, 7.33f, 1350.0f},
  {"2011-12-07", 21.10f, 9.00f, 5.74f, 1373.0f}, // Alerta: pH alto (> 8.5)
  {"2013-03-06", 23.80f, 8.04f, 6.88f,  821.0f},
  {"2017-09-26", 18.80f, 9.01f, 7.28f, 1315.0f}, // Alerta: pH alto (> 8.5)
  {"2019-08-26", 18.90f, 8.21f, 7.90f, 1305.0f}
};
const size_t NUM_SAMPLES = sizeof(SAMPLES) / sizeof(SAMPLES[0]);
size_t currentIndex = 0;

void connectWiFi() {
  Serial.print("Conectando a WiFi ");
  Serial.print(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("WiFi conectado. IP local: ");
  Serial.println(WiFi.localIP());
}

String buildPayload(const WaterSample& s) {
  String json = "{";
  json += "\"watershed\":\"Chili\",";
  json += "\"station_id\":\"QAñas1\",";
  json += "\"location\":\"Quebrada Añashuayco\",";
  json += "\"latitude\":-16.42553,";
  json += "\"longitude\":-71.675134,";
  json += "\"sample_date\":\"" + String(s.sample_date) + "\",";
  json += "\"water_temp_c\":" + String(s.water_temp_c, 2) + ",";
  json += "\"ph\":" + String(s.ph, 2) + ",";
  json += "\"dissolved_oxygen_mg_l\":" + String(s.dissolved_oxygen_mg_l, 2) + ",";
  json += "\"electrical_conductivity_us_cm\":" + String(s.electrical_conductivity_us_cm, 2);
  json += "}";
  return json;
}

void sendTelemetry(const WaterSample& sample) {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  WiFiClientSecure client;
  // Para demostración educativa en Wokwi (en producción usar certificado CA raíz)
  client.setInsecure();

  HTTPClient http;
  if (!http.begin(client, API_ENDPOINT)) {
    Serial.println("[ERROR] No se pudo inicializar HTTPClient.");
    return;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-KEY", IOT_API_KEY);

  String payload = buildPayload(sample);
  unsigned long startMs = millis();
  int httpCode = http.POST(payload);
  unsigned long latencyMs = millis() - startMs;

  Serial.print("[ESP32 QAñas1] Fecha=");
  Serial.print(sample.sample_date);
  Serial.print(" | pH=");
  Serial.print(sample.ph, 2);
  Serial.print(" | HTTP=");
  Serial.print(httpCode);
  Serial.print(" | Latencia=");
  Serial.print(latencyMs);
  Serial.println(" ms");

  if (httpCode > 0) {
    Serial.print("Respuesta: ");
    Serial.println(http.getString());
  } else {
    Serial.print("Error HTTP: ");
    Serial.println(http.errorToString(httpCode));
  }

  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== Nodo ESP32 - Monitoreo Calidad de Agua Arequipa ===");
  connectWiFi();
}

void loop() {
  sendTelemetry(SAMPLES[currentIndex]);
  currentIndex = (currentIndex + 1) % NUM_SAMPLES;
  delay(SEND_INTERVAL_MS);
}
