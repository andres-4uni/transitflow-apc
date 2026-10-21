#pragma once
#include <cstdint>
#include <cstring>

namespace apc {
constexpr uint32_t kConnectTimeout = 25000;
constexpr uint32_t kSetupTimeout = 600000;
enum class State { Idle, Searching, Setup, Connecting, Online, Fault };
enum class Action { None, ConnectSaved, StartSetup, Connected, StopSetup };

// Todas las restas son modulares: millis() puede desbordarse cada ~49 días.
class Policy {
 public:
  State state = State::Idle;
  uint32_t since = 0;
  bool hasSaved = false;

  void enter(State next, uint32_t now) { state = next; since = now; }
  Action begin(uint32_t now, bool saved) {
    hasSaved = saved;
    enter(saved ? State::Searching : State::Setup, now);
    return saved ? Action::ConnectSaved : Action::StartSetup;
  }
  Action tick(uint32_t now, bool connected) {
    if ((state == State::Searching || state == State::Connecting) && connected) {
      enter(State::Online, now);
      return Action::Connected;
    }
    if ((state == State::Searching || state == State::Connecting) &&
        uint32_t(now - since) >= kConnectTimeout) {
      enter(State::Setup, now);
      return Action::StartSetup;
    }
    if (state == State::Online && !connected) {
      enter(State::Searching, now);
      return Action::ConnectSaved;
    }
    if (state == State::Setup && uint32_t(now - since) >= kSetupTimeout) {
      enter(hasSaved ? State::Searching : State::Idle, now);
      return hasSaved ? Action::ConnectSaved : Action::StopSetup;
    }
    return Action::None;
  }
  bool ledOn(uint32_t now) const {
    if (state == State::Online) return true;
    if (state == State::Idle || state == State::Fault) return false;
    uint32_t interval = (state == State::Setup || state == State::Connecting) ? 120 : 600;
    return ((uint32_t(now - since) / interval) % 2) == 0;
  }
};

enum class ButtonAction { None, Setup, Forget };
// Actúa al soltar; exige observar BOOT libre antes de aceptar pulsaciones.
class BootButton {
 public:
  ButtonAction tick(uint32_t now, bool down) {
    if (down != raw_) { raw_ = down; changed_ = now; }
    if (uint32_t(now - changed_) < 50) return ButtonAction::None;
    if (!armed_) {
      if (!down) armed_ = true;
      return ButtonAction::None;
    }
    if (down == stable_) return ButtonAction::None;
    stable_ = down;
    if (down) { pressed_ = now; return ButtonAction::None; }
    uint32_t held = now - pressed_;
    if (held >= 10000) return ButtonAction::Forget;
    return held >= 3000 ? ButtonAction::Setup : ButtonAction::None;
  }
 private:
  bool raw_ = false, stable_ = false, armed_ = false;
  uint32_t changed_ = 0, pressed_ = 0;
};

struct Credentials {
  uint32_t version = 1;
  char ssid[33] = {};
  char password[65] = {};
};

inline bool validCredentials(const Credentials &value) {
  if (value.version != 1 || value.ssid[32] != 0 || value.password[64] != 0) return false;
  size_t nameLength = std::strlen(value.ssid), keyLength = std::strlen(value.password);
  if (nameLength == 0 || nameLength > 32 || keyLength > 63) return false;
  // Se admiten redes abiertas de forma explícita, WPA2/3 personal con clave ASCII.
  if (keyLength != 0 && keyLength < 8) return false;
  for (size_t i = 0; i < keyLength; ++i)
    if (value.password[i] < 32 || value.password[i] > 126) return false;
  return true;
}
}  // namespace apc
