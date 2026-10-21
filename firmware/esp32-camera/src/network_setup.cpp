#include "network_setup.h"
#include <ESPmDNS.h>
#include <WiFi.h>
#include "esp_system.h"
#include "esp_wifi.h"
#include "camera_runtime.h"
#include "setup_secret.h"  // Generado localmente; nunca versionado.

static_assert(sizeof(APC_SETUP_PASSWORD) == 33, "Se requiere clave aleatoria de 32 caracteres");
namespace {
constexpr int kLedPin = 21;  // Activo LOW; comparte CS con microSD (sin usar).
constexpr int kBootPin = 0;

String randomToken() {
  uint8_t bytes[16];
  esp_fill_random(bytes, sizeof(bytes));
  char token[33];
  for (size_t i = 0; i < sizeof(bytes); ++i) snprintf(token + i * 2, 3, "%02x", bytes[i]);
  return String(token);
}

String jsonString(const String &value) {
  String result = "\"";
  for (size_t i = 0; i < value.length(); ++i) {
    uint8_t character = value[i];
    if (character == '"' || character == '\\') { result += '\\'; result += char(character); }
    else if (character < 32) {
      char escape[7];
      snprintf(escape, sizeof(escape), "\\u%04x", character);
      result += escape;
    } else result += char(character);
  }
  return result + "\"";
}
}  // namespace

void NetworkSetup::begin() {
  digitalWrite(kLedPin, HIGH);
  pinMode(kLedPin, OUTPUT);
  pinMode(kBootPin, INPUT_PULLUP);
  Serial.println("APC Metro: iniciando; sin registro de SSID ni claves.");
  cameraReady_ = initCamera();
  storageReady_ = preferences_.begin("apc-network", false);
  bool hasSaved = false;
  if (storageReady_) {
    size_t size = preferences_.getBytesLength("credentials");
    if (size == sizeof(saved_)) {
      hasSaved = preferences_.getBytes("credentials", &saved_, sizeof(saved_)) == sizeof(saved_) &&
                 apc::validCredentials(saved_);
    }
    if (size && !hasSaved) Serial.println("ERROR: registro NVS inválido; configurar nuevamente.");
  } else Serial.println("ERROR: NVS no disponible; no se aceptarán cambios de red.");
  WiFi.persistent(false);
  WiFi.setAutoReconnect(false);
  WiFi.setHostname("apc-metro");  // Antes de iniciar Wi-Fi, como exige el core.
  const char *headers[] = {"Origin", "Content-Type"};
  portal_.collectHeaders(headers, 2);
  portal_.on("/", HTTP_GET, [this]() { showPortal(); });
  portal_.on("/scan", HTTP_GET, [this]() { scanNetworks(); });
  portal_.on("/save", HTTP_POST, [this]() { saveRequest(); });
  portal_.on("/forget", HTTP_POST, [this]() { forgetRequest(); });
  portal_.onNotFound([this]() { if (allowed()) reply(404, "Ruta no disponible."); });
  apply(policy_.begin(millis(), hasSaved));
}

void NetworkSetup::stopVideo() {
  stopCameraServer();
  cameraServing_ = false;
  if (mdnsActive_) { MDNS.end(); mdnsActive_ = false; }
}

void NetworkSetup::stopPortal() {
  if (portalActive_) {
    portal_.stop();
    esp_wifi_scan_stop();
    WiFi.scanDelete();
    WiFi.softAPdisconnect(true);
    portalActive_ = false;
    csrfToken_ = "";
  }
}

void NetworkSetup::connectSaved() {
  stopVideo();
  stopPortal();
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(false, false);
  WiFi.begin(saved_.ssid, saved_.password);
  WiFi.setSleep(false);  // Conserva el ajuste del CameraWebServer oficial.
  Serial.println("Wi-Fi: buscando red guardada (máximo 25 s).");
}

void NetworkSetup::startSetup() {
  // El video se detiene ANTES de que exista una interfaz AP.
  stopVideo();
  stopPortal();
  candidate_ = apc::Credentials{};
  pendingConnect_ = pendingForget_ = false;
  WiFi.disconnect(false, false);
  // STA desconectada, solo para escaneo/asociación posterior.
  if (!WiFi.mode(WIFI_AP_STA) ||
      !WiFi.softAPConfig(apIP_, apIP_, IPAddress(255, 255, 255, 0)) ||
      !WiFi.softAP("APC-Metro-Setup", APC_SETUP_PASSWORD, 1, 0, 2)) {
    Serial.println("ERROR: no se pudo iniciar AP protegido.");
    WiFi.mode(WIFI_OFF);
    policy_.enter(apc::State::Fault, millis());
    return;
  }
  // Con passphrase no vacía, softAP del core utiliza WPA2-PSK.
  csrfToken_ = randomToken();
  portalActive_ = true;
  portal_.begin();
  WiFi.scanNetworks(true);
  Serial.println("Configuración: AP WPA2 APC-Metro-Setup, http://192.168.4.1 (10 min).");
}

void NetworkSetup::apply(apc::Action action) {
  switch (action) {
    case apc::Action::ConnectSaved: connectSaved(); break;
    case apc::Action::StartSetup: startSetup(); break;
    case apc::Action::StopSetup:
      stopPortal();
      WiFi.mode(WIFI_OFF);
      Serial.println("Configuración expirada. Soltar BOOT tras 3 s para reabrir.");
      break;
    case apc::Action::Connected: {
      bool persisted = true;
      if (portalActive_) {
        // Un único blob NVS conserva la pareja completa ante cortes de energía.
        persisted = storageReady_ && preferences_.putBytes("credentials", &candidate_, sizeof(candidate_)) == sizeof(candidate_);
        if (persisted) { saved_ = candidate_; policy_.hasSaved = true; }
        candidate_ = apc::Credentials{};
      }
      if (!persisted) {
        Serial.println("ERROR: no se pudo guardar en NVS; se conserva la red anterior.");
        policy_.enter(apc::State::Setup, millis());
        startSetup();
        break;
      }
      stopPortal();
      WiFi.mode(WIFI_STA);
      WiFi.setSleep(false);
      Serial.printf("Wi-Fi conectado. IP: %s\n", WiFi.localIP().toString().c_str());
      if (MDNS.begin("apc-metro")) {
        mdnsActive_ = true;
        MDNS.addService("http", "tcp", 80);
        MDNS.addService("apc-camera", "tcp", 81);
        MDNS.addServiceTxt("apc-camera", "tcp", "path", "/stream");
        Serial.println("mDNS: apc-metro.local; respaldo: IP serial o DHCP del router.");
      } else Serial.println("Aviso: mDNS no disponible; usar IP.");
      cameraServing_ = cameraReady_ && startCameraServer();
      retryCameraAt_ = millis();
      if (cameraServing_) Serial.println("Cámara lista: panel :80/ y MJPEG :81/stream.");
      else Serial.println("ERROR: cámara/HTTP no disponible; revisar alimentación y PSRAM.");
      break;
    }
    case apc::Action::None: break;
  }
}

bool NetworkSetup::forget() {
  // Idempotente: no falla si ya no había registro.
  if (!storageReady_ || !preferences_.clear()) {
    Serial.println("ERROR: no se pudo borrar NVS; no se declara reseteado.");
    return false;
  }
  saved_ = apc::Credentials{};
  policy_.hasSaved = false;
  // persistent(false) usa RAM: limpiar FLASH explícitamente para retirar claves
  // que pudiera haber dejado el ejemplo oficial, y volver inmediatamente a RAM.
  WiFi.mode(WIFI_AP_STA);
  WiFi.disconnect(false, false);
  wifi_config_t empty = {};
  esp_err_t storageError = esp_wifi_set_storage(WIFI_STORAGE_FLASH);
  esp_err_t eraseError = storageError == ESP_OK ? esp_wifi_set_config(WIFI_IF_STA, &empty) : storageError;
  esp_err_t restoreError = esp_wifi_set_storage(WIFI_STORAGE_RAM);
  if (eraseError != ESP_OK || restoreError != ESP_OK) {
    Serial.println("ERROR: NVS propia borrada, limpieza de Wi-Fi anterior incompleta.");
    return false;
  }
  Serial.println("Credenciales borradas; firmware y clave del AP conservados.");
  return true;
}

void NetworkSetup::tick() {
  uint32_t now = millis();
  auto buttonAction = button_.tick(now, digitalRead(kBootPin) == LOW);
  if (buttonAction != apc::ButtonAction::None) {
    stopVideo();
    if (buttonAction == apc::ButtonAction::Forget) forget();
    policy_.enter(apc::State::Setup, millis());
    startSetup();
  }
  if (portalActive_) portal_.handleClient();
  now = millis();
  if ((pendingConnect_ || pendingForget_) && uint32_t(now - requestAt_) >= 300) {
    bool erase = pendingForget_;
    pendingConnect_ = pendingForget_ = false;
    if (erase) {
      forget();
      policy_.enter(apc::State::Setup, now);
      startSetup();
    } else {
      esp_wifi_scan_stop();
      WiFi.scanDelete();
      policy_.enter(apc::State::Connecting, now);
      WiFi.begin(candidate_.ssid, candidate_.password);
      Serial.println("Wi-Fi: probando nueva red; solo se guarda al obtener IP.");
    }
  }
  apply(policy_.tick(millis(), WiFi.status() == WL_CONNECTED));
  // Reintento acotado ante fallo de arranque HTTP, sin reinicializar el sensor.
  if (policy_.state == apc::State::Online && cameraReady_ && !cameraServing_ &&
      uint32_t(millis() - retryCameraAt_) >= 10000) {
    retryCameraAt_ = millis();
    cameraServing_ = startCameraServer();
    Serial.println(cameraServing_ ? "HTTP recuperado: :81/stream." : "ERROR: HTTP sigue sin iniciar.");
  }
  digitalWrite(kLedPin, policy_.ledOn(millis()) ? LOW : HIGH);
}

void NetworkSetup::reply(int code, const String &body, const char *type) {
  portal_.sendHeader("Cache-Control", "no-store");
  portal_.sendHeader("X-Content-Type-Options", "nosniff");
  // no-referrer convierte Origin a "null" en POST de formulario (Fetch).
  // same-origin conserva el origen local y no envía Referer a otros sitios.
  portal_.sendHeader("Referrer-Policy", "same-origin");
  portal_.sendHeader("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'; form-action 'self'");
  portal_.send(code, type, body);
}

bool NetworkSetup::rejectRequest(int code, const char *reason) {
  // reason siempre es un código estático: nunca registrar cabeceras/cuerpo.
  Serial.printf("[portal] reject=%s\n", reason);
  reply(code, String("Solicitud rechazada [") + reason +
        "]. Recargar http://192.168.4.1/ y enviar de nuevo.");
  return false;
}

bool NetworkSetup::allowed(bool mutation) {
  String host = portal_.hostHeader();
  IPAddress remote = portal_.client().remoteIP();
  bool apClient = remote[0] == 192 && remote[1] == 168 && remote[2] == 4 && remote[3] > 1 && remote[3] < 255;
  if (!portalActive_) return rejectRequest(403, "ap_inactive");
  if (portal_.client().localIP() != apIP_) return rejectRequest(403, "ap_interface");
  if (!apClient) return rejectRequest(403, "ap_client");
  if (host != "192.168.4.1" && host != "192.168.4.1:80") return rejectRequest(403, "host");
  if (!mutation) return true;

  String origin = portal_.header("Origin");
  if (origin == "null") return rejectRequest(403, "origin_null");
  if (!origin.isEmpty() && origin != "http://192.168.4.1" && origin != "http://192.168.4.1:80")
    return rejectRequest(403, "origin_foreign");

  // Los formularios usan el parser URL-encoded del core; no JSON/plaintext.
  String contentType = portal_.header("Content-Type");
  int separator = contentType.indexOf(';');
  if (separator >= 0) contentType = contentType.substring(0, separator);
  contentType.trim();
  if (!contentType.equalsIgnoreCase("application/x-www-form-urlencoded"))
    return rejectRequest(415, "post_type");

  if (csrfToken_.length() != 32) return rejectRequest(403, "csrf_session");
  if (!portal_.hasArg("token")) return rejectRequest(403, "csrf_missing");
  String submittedToken = portal_.arg("token");
  if (submittedToken.length() != 32) return rejectRequest(403, "csrf_length");
  if (!csrfToken_.equalsConstantTime(submittedToken)) return rejectRequest(403, "csrf_mismatch");
  Serial.printf("[portal] post=accepted origin=%s csrf=ok form=urlencoded\n", origin.isEmpty() ? "absent" : "local");
  return true;
}

void NetworkSetup::showPortal() {
  if (!allowed()) return;
  String page = R"HTML(<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>APC Metro · Wi-Fi</title><style>body{font:18px system-ui;max-width:34em;margin:2em auto;padding:1em}input,button{font:inherit;padding:.6em;margin:.4em 0;box-sizing:border-box;width:100%}</style>
<h1>APC Metro</h1><p>Configurar red Wi-Fi de 2,4 GHz. El video está detenido.</p>
<p id="status">Elegir red o escribir un SSID oculto. El AP expira en 10 minutos.</p>
<form action="/save" method="post" enctype="application/x-www-form-urlencoded" autocomplete="off">
<input type="hidden" name="token" value=")HTML";
  page += csrfToken_;
  page += R"HTML("><label>Red (SSID)<input name="ssid" list="networks" maxlength="32" required autocomplete="off"></label>
<datalist id="networks"></datalist><label>Contraseña de la red<input name="password" type="password" maxlength="63" autocomplete="new-password"></label>
<p>Dejar la contraseña vacía solo si la red es abierta. No se admite Wi-Fi empresarial.</p>
<button>Guardar y conectar</button></form>
<p>Al conectar, este AP desaparece. Volver a la red elegida en el Mac y buscar la cámara.</p>
<details><summary>Restablecer redes guardadas</summary><form action="/forget" method="post" enctype="application/x-www-form-urlencoded">
<input type="hidden" name="token" value=")HTML";
  page += csrfToken_;
  page += R"HTML("><button>Borrar credenciales Wi-Fi</button></form></details>
<script>async function scan(){try{const r=await fetch('/scan',{cache:'no-store'});if(r.status===202){setTimeout(scan,1000);return;}if(!r.ok)return;const names=await r.json();const list=document.getElementById('networks');for(const name of names){const option=document.createElement('option');option.value=name;list.appendChild(option);}}catch(e){document.getElementById('status').textContent='Escaneo no disponible; escribir SSID manualmente.';}}scan();</script></html>)HTML";
  reply(200, page);
}

void NetworkSetup::scanNetworks() {
  if (!allowed()) return;
  if (policy_.state != apc::State::Setup || pendingConnect_) { reply(409, "Conectando."); return; }
  int count = WiFi.scanComplete();
  if (count == WIFI_SCAN_RUNNING) { reply(202, "[]", "application/json"); return; }
  if (count < 0) { reply(503, "[]", "application/json"); return; }
  String names = "[";
  // Limitar memoria y nunca insertar SSID como HTML ejecutable.
  for (int i = 0; i < count && i < 30; ++i) {
    if (i) names += ',';
    names += jsonString(WiFi.SSID(i));
  }
  reply(200, names + "]", "application/json");
}

void NetworkSetup::saveRequest() {
  if (!allowed(true)) return;
  if (!storageReady_) { rejectRequest(503, "nvs_unavailable"); return; }
  if (policy_.state != apc::State::Setup || pendingConnect_ || pendingForget_) { rejectRequest(409, "busy"); return; }
  if (!portal_.hasArg("ssid") || !portal_.hasArg("password")) { rejectRequest(400, "fields_missing"); return; }
  String name = portal_.arg("ssid"), key = portal_.arg("password");
  apc::Credentials value;
  // No truncar ni modificar espacios de SSID/clave. Arduino String cuenta bytes UTF-8.
  if (name.length() > 32 || key.length() > 63 ||
      memchr(name.c_str(), 0, name.length()) || memchr(key.c_str(), 0, key.length())) {
    rejectRequest(400, "credentials_encoding"); return;
  }
  name.toCharArray(value.ssid, sizeof(value.ssid));
  key.toCharArray(value.password, sizeof(value.password));
  if (!apc::validCredentials(value)) { rejectRequest(400, "credentials_format"); return; }
  candidate_ = value;
  pendingConnect_ = true;
  requestAt_ = millis();
  reply(202, "<meta charset='utf-8'><meta http-equiv='refresh' content='30;url=/'><h1>Conectando</h1><p>Si conecta, el AP se cierra y se guarda la red. Volver a esa red en el Mac. Si falla, este portal vuelve a estar disponible tras 25 s; la red anterior se conserva.</p>");
}

void NetworkSetup::forgetRequest() {
  if (!allowed(true)) return;
  if (!storageReady_) { rejectRequest(503, "nvs_unavailable"); return; }
  if (pendingConnect_ || pendingForget_ || policy_.state != apc::State::Setup) { rejectRequest(409, "busy"); return; }
  pendingForget_ = true;
  requestAt_ = millis();
  reply(202, "<meta charset='utf-8'><h1>Borrado solicitado</h1><p>El resultado se informa por serial. Reconectar al AP y recargar el portal. La clave de configuración se conserva.</p>");
}
