#include "network_setup.h"

NetworkSetup network;

void setup() {
  Serial.begin(115200);
  // No esperar Serial: debe arrancar también alimentado con powerbank.
  Serial.setDebugOutput(false);
  network.begin();
}

void loop() {
  network.tick();
  // El core cede CPU a FreeRTOS; cámara/HTTP trabajan en tareas independientes.
  yield();
}
