#include "runtime_policy.h"
#include <cassert>
#include <iostream>
#include <limits>

using namespace apc;

int main() {
  // Primer arranque: AP temporal, sin credenciales y sin bloqueo indefinido.
  Policy first;
  assert(first.begin(0, false) == Action::StartSetup);
  assert(first.ledOn(0) && !first.ledOn(120));
  assert(first.tick(kSetupTimeout - 1, false) == Action::None);
  assert(first.tick(kSetupTimeout, false) == Action::StopSetup);
  assert(first.state == State::Idle && !first.ledOn(kSetupTimeout));

  // Red guardada ausente: timeout exacto, portal y posterior reintento automático.
  Policy offline;
  assert(offline.begin(100, true) == Action::ConnectSaved);
  assert(offline.ledOn(100) && !offline.ledOn(700));
  assert(offline.tick(100 + kConnectTimeout - 1, false) == Action::None);
  assert(offline.tick(100 + kConnectTimeout, false) == Action::StartSetup);
  assert(offline.tick(100 + kConnectTimeout + kSetupTimeout, false) == Action::ConnectSaved);
  assert(offline.tick(100 + kConnectTimeout + kSetupTimeout + 1, true) == Action::Connected);
  assert(offline.ledOn(1234567));
  // Pérdida con streaming: reconexión una sola vez, conserva la red guardada.
  assert(offline.tick(700000, false) == Action::ConnectSaved);
  assert(offline.tick(700001, false) == Action::None);
  assert(offline.tick(700002, true) == Action::Connected);

  // Clave incorrecta de candidata: conservar hasSaved y reabrir portal.
  offline.enter(State::Connecting, 800000);
  assert(offline.tick(825000, false) == Action::StartSetup);
  assert(offline.hasSaved);
  offline.enter(State::Connecting, 850000);
  assert(offline.tick(850010, true) == Action::Connected);
  assert(offline.tick(850011, true) == Action::None);

  // Duraciones y LED siguen funcionando al desbordarse millis().
  constexpr uint32_t nearWrap = std::numeric_limits<uint32_t>::max() - 1000;
  Policy wrap;
  wrap.begin(nearWrap, true);
  assert(wrap.tick(nearWrap + kConnectTimeout - 1, false) == Action::None);
  assert(wrap.tick(nearWrap + kConnectTimeout, false) == Action::StartSetup);
  assert(!wrap.ledOn(nearWrap + kConnectTimeout + 120));
  wrap.enter(State::Fault, 0);
  assert(!wrap.ledOn(500));

  // BOOT ya pulsado al arrancar no dispara configuración ni borrado.
  BootButton boot;
  assert(boot.tick(0, true) == ButtonAction::None);
  assert(boot.tick(20000, true) == ButtonAction::None);
  assert(boot.tick(20001, false) == ButtonAction::None);
  assert(boot.tick(20060, false) == ButtonAction::None);
  // Rebote y pulsación corta: sin acción.
  boot.tick(21000, true);
  boot.tick(21010, false);
  boot.tick(21100, false);
  boot.tick(22000, true);
  boot.tick(22050, true);
  boot.tick(22100, false);
  assert(boot.tick(22150, false) == ButtonAction::None);
  // 3 s para abrir, 10 s para borrar, solo al soltar.
  boot.tick(23000, true);
  assert(boot.tick(23050, true) == ButtonAction::None);
  assert(boot.tick(26050, true) == ButtonAction::None);
  boot.tick(26051, false);
  assert(boot.tick(26101, false) == ButtonAction::Setup);
  assert(boot.tick(26151, false) == ButtonAction::None);
  boot.tick(30000, true);
  boot.tick(30050, true);
  boot.tick(40050, false);
  assert(boot.tick(40100, false) == ButtonAction::Forget);

  Credentials value;
  assert(!validCredentials(value));
  std::strcpy(value.ssid, "Red-sintetica");
  assert(validCredentials(value));  // Red abierta explícita.
  std::strcpy(value.password, "short");
  assert(!validCredentials(value));
  std::strcpy(value.password, "solo-prueba-123");
  assert(validCredentials(value));
  std::memset(value.ssid, 'x', 32);
  assert(validCredentials(value));
  value.ssid[32] = 'x';
  assert(!validCredentials(value));
  value.ssid[32] = 0;
  std::memset(value.password, 'x', 64);
  assert(!validCredentials(value));  // No truncar una PSK de 64 caracteres.
  value.password[63] = 0;
  assert(validCredentials(value));
  value.password[2] = '\n';
  assert(!validCredentials(value));
  value.password[2] = 'x';
  value.version = 2;
  assert(!validCredentials(value));
  std::cout << "Política: arranque, timeout, reconexión, LED, BOOT, NVS y overflow OK\n";
}
