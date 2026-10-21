#pragma once
// Dobles HAL: ejecutan el controlador real en el Mac; no simulan radio ni NVS física.
#include <algorithm>
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <functional>
#include <map>
#include <string>
#include <vector>

class String {
 public:
  std::string text;
  String() = default;
  String(const char *value) : text(value) {}
  String(std::string value) : text(std::move(value)) {}
  size_t length() const { return text.size(); }
  bool isEmpty() const { return text.empty(); }
  const char *c_str() const { return text.c_str(); }
  char operator[](size_t index) const { return text[index]; }
  String &operator+=(const String &value) { text += value.text; return *this; }
  String &operator+=(char value) { text += value; return *this; }
  bool equalsConstantTime(const String &value) const { return text == value.text; }
  void toCharArray(char *out, size_t size) const { std::snprintf(out, size, "%s", c_str()); }
  friend bool operator==(const String &left, const String &right) { return left.text == right.text; }
  friend bool operator!=(const String &left, const String &right) { return !(left == right); }
  friend String operator+(const String &left, const String &right) { return String(left.text + right.text); }
  friend bool operator<(const String &left, const String &right) { return left.text < right.text; }
};

class IPAddress {
 public:
  uint8_t octets[4];
  IPAddress(uint8_t a=0, uint8_t b=0, uint8_t c=0, uint8_t d=0) : octets{a,b,c,d} {}
  uint8_t operator[](int index) const { return octets[index]; }
  bool operator==(const IPAddress &other) const { return std::memcmp(octets, other.octets, 4) == 0; }
  bool operator!=(const IPAddress &other) const { return !(*this == other); }
  String toString() const {
    char text[16]; std::snprintf(text, sizeof(text), "%u.%u.%u.%u", octets[0],octets[1],octets[2],octets[3]);
    return String(text);
  }
};

namespace fake {
inline uint32_t now = 0;
inline bool bootDown = false, ledLow = false, ap = false, video = false, nvsWrite = true, nvsOpen = true;
inline int status = 0, connectCalls = 0, videoStarts = 0, legacyErases = 0;
inline String requestedSSID, requestedKey;
inline std::string serial;
inline std::map<std::string, std::vector<uint8_t>> nvs;
}
constexpr int LOW=0, HIGH=1, OUTPUT=2, INPUT_PULLUP=3;
constexpr int WIFI_STA=1, WIFI_AP_STA=3, WIFI_OFF=0, WL_CONNECTED=3, WIFI_SCAN_RUNNING=-1;
constexpr int HTTP_GET=0, HTTP_POST=1;
inline uint32_t millis() { return fake::now; }
inline void pinMode(int, int) {}
inline void digitalWrite(int, int value) { fake::ledLow = value == LOW; }
inline int digitalRead(int) { return fake::bootDown ? LOW : HIGH; }
struct FakeSerial {
  void println(const char *value) { fake::serial += std::string(value) + "\n"; }
  void printf(const char *format, ...) {
    char text[512]; va_list args; va_start(args,format); std::vsnprintf(text,sizeof(text),format,args); va_end(args);
    fake::serial += text;
  }
};
inline FakeSerial Serial;

class Preferences {
 public:
  bool begin(const char *, bool) { return fake::nvsOpen; }
  size_t getBytesLength(const char *key) { return fake::nvs[key].size(); }
  size_t getBytes(const char *key, void *value, size_t size) {
    size = std::min(size, fake::nvs[key].size()); std::memcpy(value, fake::nvs[key].data(), size); return size;
  }
  size_t putBytes(const char *key, const void *value, size_t size) {
    if (!fake::nvsWrite) return 0;
    auto bytes = static_cast<const uint8_t *>(value); fake::nvs[key] = {bytes, bytes+size}; return size;
  }
  bool clear() { if (!fake::nvsWrite) return false; fake::nvs.clear(); return true; }
};

struct FakeClient {
  IPAddress local{192,168,4,1}, remote{192,168,4,2};
  IPAddress localIP() { return local; }
  IPAddress remoteIP() { return remote; }
};

class WebServer {
 public:
  static inline WebServer *latest = nullptr;
  bool active = false;
  int code = 0;
  String body, host{"192.168.4.1"}, origin;
  std::map<String, String> arguments;
  std::map<std::string, std::string> headers;
  FakeClient connection;
  std::map<std::pair<std::string,int>, std::function<void()>> handlers;
  std::function<void()> missing;
  WebServer(IPAddress ip, int port) { assert(ip == IPAddress(192,168,4,1) && port == 80); latest = this; }
  void collectHeaders(const char **, int) {}
  void on(const char *path, int method, std::function<void()> callback) { handlers[{path,method}] = callback; }
  void onNotFound(std::function<void()> callback) { missing = callback; }
  void begin() { assert(fake::ap && !fake::video); active = true; }
  void stop() { active = false; }
  void handleClient() {}
  FakeClient &client() { return connection; }
  String hostHeader() { return host; }
  String header(const char *) { return origin; }
  String arg(const char *key) { return arguments[key]; }
  void sendHeader(const char *key, const String &value) { headers[key] = value.text; }
  void send(int status, const char *, const String &value) { code=status; body=value; }
  int request(const char *path, int method = HTTP_GET) {
    assert(active); code=0; auto found=handlers.find({path,method});
    if (found == handlers.end()) missing(); else found->second();
    return code;
  }
};

struct FakeWiFi {
  void persistent(bool value) { assert(!value); }
  void setAutoReconnect(bool value) { assert(!value); }
  void setHostname(const char *) {}
  bool mode(int mode) { if (mode == WIFI_STA || mode == WIFI_OFF) fake::ap=false; return true; }
  void disconnect(bool, bool) { fake::status = 0; }
  void begin(const char *ssid, const char *key) { ++fake::connectCalls; fake::requestedSSID=ssid; fake::requestedKey=key; }
  void setSleep(bool) {}
  void softAPdisconnect(bool) { fake::ap=false; }
  bool softAPConfig(IPAddress, IPAddress, IPAddress) { return true; }
  bool softAP(const char *name, const char *key, int, int, int) {
    assert(!fake::video && std::strcmp(name,"APC-Metro-Setup")==0 && std::strlen(key)==32);
    fake::ap = true; return true;
  }
  int status() { return fake::status; }
  IPAddress localIP() { return IPAddress(192,168,1,50); }
  void scanDelete() {}
  void scanNetworks(bool) {}
  int scanComplete() { return 1; }
  String SSID(int) { return String("\"><script>alert(1)</script>"); }
};
inline FakeWiFi WiFi;

struct FakeMDNS {
  bool begin(const char *) { return true; }
  void end() {}
  void addService(const char *, const char *, int) {}
  void addServiceTxt(const char *, const char *, const char *, const char *) {}
};
inline FakeMDNS MDNS;
inline void esp_fill_random(void *data, size_t size) { std::memset(data, 0xab, size); }
using esp_err_t = int;
constexpr int ESP_OK=0, WIFI_STORAGE_FLASH=1, WIFI_STORAGE_RAM=0, WIFI_IF_STA=0;
struct wifi_config_t { char unused[100]; };
inline int esp_wifi_scan_stop() { return ESP_OK; }
inline int esp_wifi_set_storage(int) { return ESP_OK; }
inline int esp_wifi_set_config(int, const wifi_config_t *) { ++fake::legacyErases; return ESP_OK; }
