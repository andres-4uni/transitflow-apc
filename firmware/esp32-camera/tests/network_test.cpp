#include "network_setup.h"
#include "fake_hal.h"
#include <iostream>

bool initCamera() { return true; }
bool startCameraServer() { assert(!fake::ap); fake::video=true; ++fake::videoStarts; return true; }
void stopCameraServer() { fake::video=false; }

String token(WebServer *portal) {
  assert(portal->request("/") == 200);
  std::string page = portal->body.text;
  std::string marker = "name=\"token\" value=\"";
  auto start = page.find(marker) + marker.size();
  return page.substr(start, page.find('"', start)-start);
}
void submit(WebServer *portal, const char *ssid, const char *key) {
  portal->arguments = {{"token",token(portal)}, {"ssid",ssid}, {"password",key}};
  assert(portal->request("/save", HTTP_POST) == 202);
}

void rejected(WebServer *portal, const char *path, int code, const char *reason) {
  size_t before=fake::serial.size();
  assert(portal->request(path,HTTP_POST)==code);
  assert(portal->body.text.find(std::string("[")+reason+"]")!=std::string::npos);
  assert(fake::serial.substr(before)==std::string("[portal] reject=")+reason+"\n" ||
         fake::serial.substr(before).find(std::string("reject=")+reason+"\n")!=std::string::npos);
}

int main(int argc, char **argv) {
  NetworkSetup network;
  network.begin();
  WebServer *portal = WebServer::latest;
  // HTML/cabeceras reales para probar un POST de navegador con datos sintéticos.
  if (argc == 2 && std::strcmp(argv[1], "--render-portal") == 0) {
    assert(portal->request("/") == 200);
    for (const auto &header : portal->headers) std::cout << header.first << ": " << header.second << "\r\n";
    std::cout << "\r\n" << portal->body.text;
    return 0;
  }
  assert(fake::ap && !fake::video && fake::connectCalls == 0);
  assert(portal->request("/") == 200);
  assert(portal->headers["Cache-Control"] == "no-store");
  assert(portal->headers["Referrer-Policy"] == "same-origin");
  assert(portal->collected==std::vector<std::string>({"Origin","Content-Type"}));
  assert(portal->body.text.find("<script>alert(1)") == std::string::npos);
  assert(portal->request("/scan") == 200);
  assert(portal->body.text.find("\\\"") != std::string::npos);
  // Portal inaccesible por la interfaz STA y ante Host ajeno/DNS rebinding.
  portal->connection.local=IPAddress(192,168,1,50);
  assert(portal->request("/") == 403);
  portal->connection.local=IPAddress(192,168,4,1);
  portal->host="evil.example";
  assert(portal->request("/") == 403);
  portal->host="192.168.4.1";
  String firstToken=token(portal);
  portal->arguments.clear();
  rejected(portal,"/save",403,"csrf_missing");
  portal->arguments={{"token",""}};
  rejected(portal,"/save",403,"csrf_length");
  portal->arguments={{"token","incorrecto"}};
  rejected(portal,"/save",403,"csrf_length");
  portal->arguments={{"token",String(std::string(32,'z'))}};
  rejected(portal,"/save",403,"csrf_mismatch");
  portal->arguments={{"token",firstToken}};
  // Reproduce el POST generado por la cabecera no-referrer anterior: token válido.
  portal->origin="null";
  rejected(portal,"/save",403,"origin_null");
  portal->origin="http://evil.example";
  rejected(portal,"/forget",403,"origin_foreign");
  portal->origin="http://192.168.4.1:81";
  rejected(portal,"/save",403,"origin_foreign");
  portal->origin="http://192.168.4.1";
  portal->contentType="text/plain";
  rejected(portal,"/save",415,"post_type");
  portal->contentType="application/x-www-form-urlencoded-malicioso";
  rejected(portal,"/save",415,"post_type");
  portal->contentType="";
  rejected(portal,"/save",415,"post_type");
  portal->contentType="Application/X-WWW-Form-Urlencoded; charset=UTF-8";
  rejected(portal,"/save",400,"fields_missing");
  assert(fake::serial.find("post=accepted origin=local csrf=ok form=urlencoded")!=std::string::npos);
  // Origin ausente conserva la compatibilidad previa: siempre exige CSRF/AP/Host.
  portal->origin="";
  rejected(portal,"/save",400,"fields_missing");
  assert(fake::serial.find("post=accepted origin=absent")!=std::string::npos);
  portal->host="192.168.4.1:80";
  portal->origin="http://192.168.4.1:80";
  rejected(portal,"/save",400,"fields_missing");
  portal->host="192.168.4.1";
  portal->contentType="application/x-www-form-urlencoded";
  portal->origin="http://192.168.4.1";
  assert(fake::connectCalls==0 && fake::nvs["credentials"].empty());
  // SSID binario con NUL, contraseña corta y longitudes inválidas no se truncan.
  portal->arguments={{"token",token(portal)}, {"ssid",String(std::string("ab\0cd",5))}, {"password",""}};
  assert(portal->request("/save",HTTP_POST)==400);
  portal->arguments["ssid"]="red-simulada";
  portal->arguments["password"]="short";
  assert(portal->request("/save",HTTP_POST)==400);
  submit(portal,"red-simulada","clave-simulada-123");
  fake::now=350;
  network.tick();
  assert(fake::ap && !fake::video && fake::connectCalls==1);
  assert(fake::nvs["credentials"].empty());
  fake::status=WL_CONNECTED;
  network.tick();
  assert(!fake::ap && !portal->active && fake::video && fake::ledLow);
  assert(fake::nvs["credentials"].size()==sizeof(apc::Credentials));
  auto previous=fake::nvs["credentials"];
  // Reinicio con NVS: conexión automática; ausencia => AP sin video.
  fake::status=0;
  NetworkSetup reboot;
  reboot.begin();
  assert(!fake::ap && fake::requestedSSID=="red-simulada");
  fake::now+=25000;
  reboot.tick();
  portal=WebServer::latest;
  assert(fake::ap && !fake::video);
  String currentToken=token(portal);
  assert(currentToken!=firstToken);
  portal->arguments={{"token",firstToken}};
  rejected(portal,"/save",403,"csrf_mismatch");  // Página de una sesión anterior.
  submit(portal,"otra-simulada","clave-simulada-456");
  fake::now+=350;
  reboot.tick();
  fake::now+=25000;
  reboot.tick();
  assert(fake::ap && fake::nvs["credentials"]==previous);  // Fallo de asociación.
  // Conexión lograda pero escritura NVS fallida: AP recuperable, red anterior intacta.
  submit(portal,"otra-simulada","clave-simulada-456");
  fake::now+=350;
  reboot.tick();
  fake::nvsWrite=false;
  fake::status=WL_CONNECTED;
  reboot.tick();
  assert(fake::ap && !fake::video && fake::nvs["credentials"]==previous);
  fake::nvsWrite=true;
  portal->arguments={{"token",token(portal)}};
  assert(portal->request("/forget",HTTP_POST)==202);
  fake::now+=350;
  reboot.tick();
  assert(fake::ap && fake::nvs.empty() && fake::legacyErases==1);
  // Logs nunca incluyen los nombres ni las claves de las redes probadas.
  for (auto secret : {"red-simulada","otra-simulada","clave-simulada-123","clave-simulada-456"})
    assert(fake::serial.find(secret)==std::string::npos);
  for (const auto &secret : {firstToken,currentToken,String(std::string(32,'z'))})
    assert(fake::serial.find(secret.text)==std::string::npos);
  for (auto header : {"http://evil.example","http://192.168.4.1:81","application/x-www-form-urlencoded-malicioso"})
    assert(fake::serial.find(header)==std::string::npos);
  std::cout << "Controlador real + HAL simulada: aislamiento AP, CSRF, persistencia y recuperación OK\n";
}
