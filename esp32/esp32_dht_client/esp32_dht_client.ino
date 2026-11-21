#include <WiFi.h>
#include <HTTPClient.h>
#include "DHT.h"

// ====== CẦN SỬA CHO PHÙ HỢP ======
const char* WIFI_SSID  = "AP-CNTT-Free";
const char* WIFI_PASS  = "";
// IP của máy chạy Django (xem bằng lệnh ipconfig, mục IPv4 Address)
const char* SERVER_URL = "http://192.168.30.228:8000/api/ingest/";
const char* API_KEY    = "doi-khoa-nay";   // phải trùng INGEST_API_KEY trong settings.py
const char* DEVICE_ID  = "esp32-01";
// =================================

#define DHTPIN 4          // GPIO 4
#define DHTTYPE DHT11     // đổi thành DHT22 nếu dùng cảm biến trắng

const unsigned long READ_INTERVAL_MS = 2000;    // đọc cảm biến mỗi 2 giây
const unsigned long SEND_INTERVAL_MS = 10000;   // gửi lên web mỗi 10 giây

DHT dht(DHTPIN, DHTTYPE);
unsigned long lastRead = 0;
unsigned long lastSend = 0;
bool hasSent = false;

void scanNetworks() {
  Serial.println("Dang quet WiFi xung quanh...");
  int n = WiFi.scanNetworks();
  if (n <= 0) {
    Serial.println("Khong thay mang nao.");
    return;
  }
  for (int i = 0; i < n; i++) {
    Serial.print(i + 1);
    Serial.print(". ");
    Serial.print(WiFi.SSID(i));
    Serial.print("  (");
    Serial.print(WiFi.RSSI(i));
    Serial.println(" dBm)");
  }
  WiFi.scanDelete();
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print("Dang ket noi WiFi");
  WiFi.disconnect(true);   // huy lan ket noi dang do truoc do
  delay(100);
  WiFi.mode(WIFI_STA);
  if (strlen(WIFI_PASS) == 0) {
  WiFi.begin(WIFI_SSID);               // mạng mở
} else {
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print(" OK, IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.print(" that bai, ma trang thai: ");
    Serial.println(WiFi.status());
  }
}

void sendReading(float nhietDo, float doAm) {
  if (WiFi.status() != WL_CONNECTED) return;

  char body[96];
  snprintf(body, sizeof(body),
           "{\"temperature\":%.1f,\"humidity\":%.1f,\"device\":\"%s\"}",
           nhietDo, doAm, DEVICE_ID);

  HTTPClient http;
  http.begin(SERVER_URL);
  http.setTimeout(5000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);
  int code = http.POST(String(body));
  http.end();

  if (code == 201) {
    Serial.println("-> Da gui len web.");
  } else {
    Serial.print("-> Gui that bai, ma HTTP: ");
    Serial.println(code);   // 401: sai API key, 400: du lieu sai, so am: khong toi duoc server
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("Dang khoi dong cam bien DHT...");
  dht.begin();
  connectWiFi();
}

void loop() {
  unsigned long now = millis();
  if (now - lastRead < READ_INTERVAL_MS) return;
  lastRead = now;

  float doAm = dht.readHumidity();
  float nhietDo = dht.readTemperature();

  if (isnan(doAm) || isnan(nhietDo)) {
    Serial.println("Loi: Khong doc duoc du lieu tu cam bien! Kiem tra lai day noi.");
    return;
  }

  Serial.print("Do am: ");
  Serial.print(doAm);
  Serial.print("%  |  Nhiet do: ");
  Serial.print(nhietDo);
  Serial.println(" C");

  if (!hasSent || now - lastSend >= SEND_INTERVAL_MS) {
    connectWiFi();               // tự nối lại nếu mất Wi-Fi
    sendReading(nhietDo, doAm);
    lastSend = now;
    hasSent = true;
  }
}
