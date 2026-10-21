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

int main() {
  NetworkSetup network;
  network.begin();
  WebServer *portal = WebServer::latest;
  assert(fake::ap && !fake::video && fake::connectCalls == 0);
  assert(portal->request("/") == 200);
  assert(portal->headers["Cache-Control"] == "no-store");
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
  portal->arguments={{"token","incorrecto"}};
  assert(portal->request("/save",HTTP_POST)==403);
  portal->arguments={{"token",token(portal)}};
  portal->origin="http://evil.example";
  assert(portal->request("/forget",HTTP_POST)==403);
  portal->origin="http://192.168.4.1";
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
  std::cout << "Controlador real + HAL simulada: aislamiento AP, CSRF, persistencia y recuperación OK\n";
}
